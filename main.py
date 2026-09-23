from __future__ import annotations

import argparse
import copy
import json
import math
import os
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy import (
    ImageClip,
    VideoFileClip,
    CompositeVideoClip,
    AudioFileClip,
    CompositeAudioClip,
    concatenate_videoclips,
    vfx,
    afx,
)

from ai_image_client import (
    AIImageGenerationError,
    DEFAULT_OPENAI_IMAGE_BASE_URL,
    generate_openai_compatible_image,
)

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"
DEFAULT_BATCH_CONFIG_PATH = ROOT / "batch.json"
LEGACY_BATCH_CONFIG_PATH = ROOT / "batch_config.json"
BATCH_SUMMARY_SCHEMA_VERSION = "1.2"
DEFAULT_AI_IMAGE_MODEL = "gpt-image-1"


def load_config() -> dict:
    return load_config_from_path(CONFIG_PATH)


def default_batch_file_value() -> str:
    if DEFAULT_BATCH_CONFIG_PATH.exists():
        return DEFAULT_BATCH_CONFIG_PATH.relative_to(ROOT).as_posix()
    if LEGACY_BATCH_CONFIG_PATH.exists():
        return LEGACY_BATCH_CONFIG_PATH.relative_to(ROOT).as_posix()
    return DEFAULT_BATCH_CONFIG_PATH.name


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_config_from_path(path: Path) -> dict:
    data = load_json(path)
    if not isinstance(data, dict):
        raise ValueError(f"설정 파일 최상위는 객체(dict)여야 합니다: {path}")
    return data


def load_config_for_cli(config_path_override: str | None = None) -> tuple[dict, Path]:
    if config_path_override:
        try:
            config_path = resolve_repo_relative_path(
                config_path_override,
                base_dir=Path.cwd().resolve(),
                must_exist=True,
            )
        except ValueError:
            if config_path_override.strip() != CONFIG_PATH.name:
                raise
            config_path = resolve_repo_relative_path(
                CONFIG_PATH.name,
                base_dir=ROOT,
                must_exist=True,
            )
    else:
        config_path = CONFIG_PATH
    return load_config_from_path(config_path), config_path


def resolve_repo_relative_path(
    path_value: str,
    *,
    base_dir: Path,
    must_exist: bool,
    allow_parent_create: bool = False,
) -> Path:
    raw_path = Path(path_value)
    target = raw_path if raw_path.is_absolute() else (base_dir / raw_path)
    resolved_target = target.resolve()
    resolved_root = ROOT.resolve()
    try:
        resolved_target.relative_to(resolved_root)
    except ValueError:
        raise ValueError("경로는 프로젝트 폴더 내부여야 합니다.")

    if allow_parent_create:
        resolved_target.parent.mkdir(parents=True, exist_ok=True)
    if must_exist and not resolved_target.exists():
        raise ValueError(f"파일을 찾을 수 없습니다: {path_value}")
    return resolved_target


def deep_merge_dict(base: dict, overrides: dict) -> dict:
    merged = copy.deepcopy(base)
    for key, value in overrides.items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(value, dict)
        ):
            merged[key] = deep_merge_dict(merged[key], value)
        else:
            merged[key] = value
    return merged


def with_batch_index_suffix(
    output_path: Path,
    index: int,
    *,
    default_suffix: str = ".mp4",
) -> Path:
    base_output = output_path
    suffix = base_output.suffix or default_suffix
    stem = base_output.stem or "animal_trip"
    return base_output.with_name(f"{stem}_{index:02d}{suffix}")


def validate_output_value(cfg: dict, *, base_dir: Path) -> Path:
    output_value = cfg.get("output", "output/animal_trip.mp4")
    if not isinstance(output_value, str) or not output_value.strip():
        raise ValueError("output은 비어 있지 않은 문자열 경로여야 합니다.")
    output_path = resolve_repo_relative_path(
        output_value,
        base_dir=base_dir,
        must_exist=False,
    )
    if output_path.suffix.lower() != ".mp4":
        raise ValueError("output 파일 확장자는 .mp4여야 합니다.")
    return output_path


def validate_prompt_output_value(cfg: dict, *, base_dir: Path) -> Path:
    output_value = cfg.get("image_prompt_output", "output/scene_image_prompts.json")
    if not isinstance(output_value, str) or not output_value.strip():
        raise ValueError("image_prompt_output은 비어 있지 않은 문자열 경로여야 합니다.")
    output_path = resolve_repo_relative_path(
        output_value,
        base_dir=base_dir,
        must_exist=False,
    )
    if output_path.suffix.lower() != ".json":
        raise ValueError("image_prompt_output 파일 확장자는 .json이어야 합니다.")
    return output_path


def validate_json_output_path(path_value: str, *, base_dir: Path) -> Path:
    if not isinstance(path_value, str) or not path_value.strip():
        raise ValueError("출력 JSON 경로는 비어 있지 않은 문자열이어야 합니다.")
    output_path = resolve_repo_relative_path(
        path_value,
        base_dir=base_dir,
        must_exist=False,
        allow_parent_create=True,
    )
    if output_path.suffix.lower() != ".json":
        raise ValueError("출력 JSON 파일 확장자는 .json이어야 합니다.")
    return output_path


def validate_output_directory_path(path_value: str, *, base_dir: Path) -> Path:
    if not isinstance(path_value, str) or not path_value.strip():
        raise ValueError("출력 디렉터리 경로는 비어 있지 않은 문자열이어야 합니다.")
    output_path = resolve_repo_relative_path(
        path_value,
        base_dir=base_dir,
        must_exist=False,
        allow_parent_create=True,
    )
    output_path.mkdir(parents=True, exist_ok=True)
    return output_path


def slugify_filename_token(value: str) -> str:
    token = re.sub(r"[^0-9A-Za-z가-힣._-]+", "_", value.strip())
    token = token.strip("._")
    return token or "job"


def build_prompt_filename_from_pattern(
    pattern: str,
    *,
    index: int,
    job_name: str,
    config_stem: str,
    default_stem: str,
) -> str:
    try:
        rendered = pattern.format(
            index=index,
            index2=f"{index:02d}",
            job=job_name,
            job_slug=slugify_filename_token(job_name),
            config=config_stem,
            stem=default_stem,
        ).strip()
    except KeyError as exc:
        raise ValueError(
            "prompt_filename_pattern에는 {index}, {index2}, {job}, {job_slug}, {config}, {stem}만 사용할 수 있습니다."
        ) from exc

    if not rendered:
        raise ValueError("prompt_filename_pattern 결과 파일명이 비어 있습니다.")
    if "/" in rendered or "\\" in rendered:
        raise ValueError("prompt_filename_pattern 결과는 파일명만 허용됩니다(경로 구분자 불가).")
    if rendered.startswith("."):
        raise ValueError("prompt_filename_pattern 결과는 숨김 파일명으로 시작할 수 없습니다.")
    return rendered if rendered.lower().endswith(".json") else f"{rendered}.json"


def resolve_summary_report_path(path_value: str, *, base_dir: Path) -> Path:
    report_path = resolve_repo_relative_path(
        path_value,
        base_dir=base_dir,
        must_exist=False,
        allow_parent_create=True,
    )
    if report_path.suffix.lower() != ".json":
        raise ValueError("summary_report 경로는 .json 파일이어야 합니다.")
    return report_path


def validate_scene_entry(scene: Any, *, index: int) -> None:
    if not isinstance(scene, dict):
        raise ValueError(f"scenes[{index}]는 객체(dict)여야 합니다.")
    source = scene.get("source")
    if not isinstance(source, str) or not source.strip():
        raise ValueError(f"scenes[{index}].source는 비어 있지 않은 문자열이어야 합니다.")
    caption = scene.get("caption", "")
    if not isinstance(caption, str):
        raise ValueError(f"scenes[{index}].caption은 문자열이어야 합니다.")
    duration = scene.get("duration", 7.5)
    try:
        duration_value = float(duration)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"scenes[{index}].duration은 숫자여야 합니다.") from exc
    if duration_value <= 0:
        raise ValueError(f"scenes[{index}].duration은 0보다 커야 합니다.")
    zoom = scene.get("zoom", 1.04)
    try:
        zoom_value = float(zoom)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"scenes[{index}].zoom은 숫자여야 합니다.") from exc
    if zoom_value <= 0:
        raise ValueError(f"scenes[{index}].zoom은 0보다 커야 합니다.")


def validate_video_config(cfg: dict, *, config_path: Path | None = None) -> None:
    config_label = str(config_path) if config_path is not None else "config.json"
    if not isinstance(cfg, dict):
        raise ValueError(f"설정 파일 최상위는 객체(dict)여야 합니다: {config_label}")

    video_cfg = cfg.get("video")
    if not isinstance(video_cfg, dict):
        raise ValueError(f"{config_label}의 video는 객체(dict)여야 합니다.")

    for key in ("width", "height"):
        if key not in video_cfg:
            raise ValueError(f"{config_label}의 video.{key} 값이 필요합니다.")
        try:
            numeric_value = int(video_cfg[key])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{config_label}의 video.{key}는 정수여야 합니다.") from exc
        if numeric_value <= 0:
            raise ValueError(f"{config_label}의 video.{key}는 1 이상의 값이어야 합니다.")

    if "fps" in video_cfg:
        try:
            fps_value = int(video_cfg["fps"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{config_label}의 video.fps는 정수여야 합니다.") from exc
        if fps_value <= 0:
            raise ValueError(f"{config_label}의 video.fps는 1 이상의 값이어야 합니다.")

    scenes = cfg.get("scenes")
    if not isinstance(scenes, list):
        raise ValueError(f"{config_label}의 scenes는 장면 객체(dict) 목록(list)이어야 합니다.")
    if not scenes:
        raise ValueError(f"{config_label}의 scenes가 비어 있습니다. 최소 1개 장면이 필요합니다.")
    for index, scene in enumerate(scenes):
        validate_scene_entry(scene, index=index)


def resolve_path_value_for_base(
    path_value: str,
    *,
    from_base_dir: Path,
    to_base_dir: Path,
) -> str:
    resolved = resolve_repo_relative_path(
        path_value,
        base_dir=from_base_dir,
        must_exist=False,
    )
    try:
        return str(resolved.relative_to(to_base_dir))
    except ValueError:
        return str(resolved)


def normalize_batch_overrides(
    overrides: dict,
    *,
    batch_base_dir: Path,
    config_base_dir: Path,
) -> dict:
    normalized = copy.deepcopy(overrides)

    for key in ("output", "image_prompt_output", "bgm"):
        value = normalized.get(key)
        if isinstance(value, str) and value.strip():
            normalized[key] = resolve_path_value_for_base(
                value,
                from_base_dir=batch_base_dir,
                to_base_dir=config_base_dir,
            )

    scenes = normalized.get("scenes")
    if isinstance(scenes, list):
        for scene in scenes:
            if not isinstance(scene, dict):
                continue
            source = scene.get("source")
            if isinstance(source, str) and source.strip():
                scene["source"] = resolve_path_value_for_base(
                    source,
                    from_base_dir=batch_base_dir,
                    to_base_dir=config_base_dir,
                )

    return normalized


def print_batch_summary_lines(title: str, job_results: list[dict[str, Any]]) -> None:
    print(title)
    for result in job_results:
        status_label = "성공" if result["status"] == "success" else "실패"
        output_path = result.get("output_path") or "-"
        error = result.get("error")
        if error:
            print(f"- {status_label}: {result['job']} -> {output_path} ({error})")
        else:
            print(f"- {status_label}: {result['job']} -> {output_path}")


def choose_ai_image_size(width: int, height: int) -> str:
    if width <= 0 or height <= 0:
        raise ValueError("이미지 크기 계산을 위해 video.width와 video.height는 1 이상이어야 합니다.")
    if height > width:
        return "1024x1536"
    if width > height:
        return "1536x1024"
    return "1024x1024"


def build_image_generation_prompt(scene_prompt: str, negative_prompt: str) -> str:
    negative = negative_prompt.strip()
    if not negative:
        return scene_prompt
    return f"{scene_prompt}\n\nAvoid: {negative}"


def relative_path_text(from_dir: Path, to_path: Path) -> str:
    return Path(os.path.relpath(to_path, from_dir)).as_posix()


def generate_ai_image_bytes(
    *,
    prompt: str,
    model: str,
    size: str,
    api_key: str,
    base_url: str,
) -> bytes:
    return generate_openai_compatible_image(
        prompt=prompt,
        model=model,
        size=size,
        api_key=api_key,
        base_url=base_url,
    )


def write_batch_summary_report(
    *,
    report_path: Path | None,
    mode: str,
    batch_path: Path,
    total_jobs: int,
    success_count: int,
    failure_count: int,
    failed_jobs: list[str],
    retry_successes: list[dict[str, Any]],
    job_results: list[dict[str, Any]],
    stopped_on_failure: bool,
    duration_seconds: float,
) -> None:
    print(
        f"[배치 요약] mode={mode}, total={total_jobs}, success={success_count}, "
        f"failure={failure_count}, duration={duration_seconds:.2f}s"
    )
    if report_path is None:
        return
    payload = {
        "schema_version": BATCH_SUMMARY_SCHEMA_VERSION,
        "mode": mode,
        "batch_file": str(batch_path),
        "total_jobs": total_jobs,
        "success_count": success_count,
        "failure_count": failure_count,
        "failed_jobs": failed_jobs,
        "retry_successes": retry_successes,
        "job_results": job_results,
        "stopped_on_failure": stopped_on_failure,
        "duration_seconds": round(duration_seconds, 3),
        "generated_at": datetime.now(UTC).isoformat(),
    }
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[배치 요약 저장] {report_path}")


def parse_args() -> argparse.Namespace:
    """Parse CLI flags and return an argparse.Namespace for execution mode selection."""
    parser = argparse.ArgumentParser(description="Animal video renderer / scene prompt generator")
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="렌더링 또는 프롬프트 생성에 사용할 설정 JSON 경로 (기본: config.json)",
    )
    parser.add_argument(
        "--generate-image-prompts",
        action="store_true",
        help="config.json의 scenes를 기반으로 AI 이미지 프롬프트를 생성합니다.",
    )
    parser.add_argument(
        "--generate-ai-images",
        action="store_true",
        help="장면 프롬프트를 사용해 AI 이미지를 생성하고 파생 config.json을 저장합니다.",
    )
    parser.add_argument(
        "--prompts-output",
        type=str,
        default=None,
        help="프롬프트 JSON 출력 경로 (프로젝트 내부 경로, 기본: output/scene_image_prompts.json)",
    )
    parser.add_argument(
        "--generated-images-dir",
        type=str,
        default=None,
        help="생성된 AI 이미지 저장 디렉터리 (기본: output/generated_ai_images)",
    )
    parser.add_argument(
        "--generated-config-output",
        type=str,
        default=None,
        help="생성된 이미지 경로를 반영한 파생 config JSON 경로 (기본: output/generated_ai_config.json)",
    )
    parser.add_argument(
        "--image-model",
        type=str,
        default=None,
        help=f"이미지 생성 모델명 (기본: {DEFAULT_AI_IMAGE_MODEL})",
    )
    parser.add_argument(
        "--batch-render",
        action="store_true",
        help="배치 설정 파일을 읽어 여러 편 영상을 순차 렌더링합니다.",
    )
    parser.add_argument(
        "--batch-generate-image-prompts",
        action="store_true",
        help="배치 설정 파일을 읽어 각 작업별 장면 프롬프트 JSON을 순차 생성합니다.",
    )
    parser.add_argument(
        "--batch-file",
        type=str,
        default=None,
        help="배치 설정 JSON 경로 (현재 디렉터리 기준 상대 경로, 프로젝트 내부 파일만 허용, 기본: batch.json / batch_config.json)",
    )
    parser.add_argument(
        "--retry-failed",
        type=int,
        default=0,
        help="배치 작업 실패 시 job별 재시도 횟수 (기본: 0)",
    )
    parser.add_argument(
        "--summary-report",
        type=str,
        default=None,
        help="배치 실행 요약(JSON) 저장 경로 (batch/batch-prompts 모드에서만 사용)",
    )
    args = parser.parse_args()
    if args.prompts_output and not args.generate_image_prompts:
        parser.error("--prompts-output는 --generate-image-prompts와 함께 사용해야 합니다.")
    if args.generated_images_dir and not args.generate_ai_images:
        parser.error("--generated-images-dir는 --generate-ai-images와 함께 사용해야 합니다.")
    if args.generated_config_output and not args.generate_ai_images:
        parser.error("--generated-config-output은 --generate-ai-images와 함께 사용해야 합니다.")
    if args.image_model and not args.generate_ai_images:
        parser.error("--image-model은 --generate-ai-images와 함께 사용해야 합니다.")
    if args.batch_file and not (args.batch_render or args.batch_generate_image_prompts):
        parser.error("--batch-file은 --batch-render 또는 --batch-generate-image-prompts와 함께 사용해야 합니다.")
    if args.batch_render and args.generate_image_prompts:
        parser.error("--batch-render와 --generate-image-prompts는 동시에 사용할 수 없습니다.")
    if args.generate_ai_images and args.generate_image_prompts:
        parser.error("--generate-ai-images와 --generate-image-prompts는 동시에 사용할 수 없습니다.")
    if args.generate_ai_images and args.batch_render:
        parser.error("--generate-ai-images와 --batch-render는 동시에 사용할 수 없습니다.")
    if args.generate_ai_images and args.batch_generate_image_prompts:
        parser.error("--generate-ai-images와 --batch-generate-image-prompts는 동시에 사용할 수 없습니다.")
    if args.batch_generate_image_prompts and args.generate_image_prompts:
        parser.error("--batch-generate-image-prompts와 --generate-image-prompts는 동시에 사용할 수 없습니다.")
    if args.batch_generate_image_prompts and args.batch_render:
        parser.error("--batch-generate-image-prompts와 --batch-render는 동시에 사용할 수 없습니다.")
    if args.retry_failed < 0:
        parser.error("--retry-failed는 0 이상의 정수여야 합니다.")
    if args.retry_failed > 0 and not (args.batch_render or args.batch_generate_image_prompts):
        parser.error("--retry-failed는 --batch-render 또는 --batch-generate-image-prompts와 함께 사용해야 합니다.")
    if args.summary_report and not (args.batch_render or args.batch_generate_image_prompts):
        parser.error("--summary-report는 --batch-render 또는 --batch-generate-image-prompts와 함께 사용해야 합니다.")
    return args


def aspect_ratio_label(width: int, height: int) -> str:
    g = math.gcd(width, height)
    return f"{width//g}:{height//g}"


def build_scene_prompt(
    scene: dict,
    scene_index: int,
    total_scenes: int,
    project_title: str,
    subtitle: str,
    width: int,
    height: int,
) -> str:
    caption = str(scene.get("caption", "")).strip()
    source = Path(str(scene.get("source", ""))).stem.replace("_", " ").strip()
    ratio = aspect_ratio_label(width, height)
    details = caption if caption else f"scene concept: {source or f'scene {scene_index}'}"

    return (
        f"Korean animation style, bright family-friendly colors, cinematic composition, "
        f"consistent characters (puppy, cat, panda, rabbit), scene {scene_index}/{total_scenes}. "
        f"Story title: {project_title}. Subtitle context: {subtitle}. "
        f"Visual direction: {details}. "
        f"high detail, clean background separation, soft lighting, no text, no logo, no watermark, "
        f"aspect ratio {ratio} ({width}x{height})."
    )


def generate_image_prompts(
    output_override: str | None = None,
    *,
    config_path_override: str | None = None,
) -> None:
    cfg, config_path = load_config_for_cli(config_path_override)
    generate_image_prompts_from_config(
        cfg=cfg,
        config_path=config_path,
        output_override=output_override,
    )


def generate_image_prompts_from_config(
    cfg: dict,
    *,
    config_path: Path | None = None,
    output_override: str | None = None,
) -> None:
    validate_video_config(cfg, config_path=config_path)
    vcfg = cfg.get("video", {})
    width = int(vcfg.get("width", 1280))
    height = int(vcfg.get("height", 720))
    if width <= 0 or height <= 0:
        raise ValueError("video.width와 video.height는 1 이상의 값이어야 합니다.")

    scenes = cfg.get("scenes", [])
    project_title = str(cfg.get("project_title", ""))
    subtitle = str(cfg.get("subtitle", ""))
    total = max(1, len(scenes))

    prompt_items = []
    for i, scene in enumerate(scenes, start=1):
        prompt_items.append(
            {
                "scene_index": i,
                "source": scene.get("source", ""),
                "caption": scene.get("caption", ""),
                "duration": scene.get("duration", 7.5),
                "prompt": build_scene_prompt(
                    scene=scene,
                    scene_index=i,
                    total_scenes=total,
                    project_title=project_title,
                    subtitle=subtitle,
                    width=width,
                    height=height,
                ),
                "negative_prompt": "blurry, low quality, noisy, distorted anatomy, deformed face, extra limbs, text, logo, watermark",
            }
        )

    selected_output = (
        output_override
        if output_override
        else cfg.get("image_prompt_output", "output/scene_image_prompts.json")
    )
    if not isinstance(selected_output, str) or not selected_output.strip():
        raise ValueError("프롬프트 출력 경로는 비어 있을 수 없습니다.")
    out = resolve_repo_relative_path(
        selected_output,
        base_dir=Path.cwd().resolve() if output_override else (config_path.parent if config_path else ROOT),
        must_exist=False,
        allow_parent_create=True,
    )
    payload = {
        "project_title": project_title,
        "subtitle": subtitle,
        "aspect_ratio": aspect_ratio_label(width, height),
        "resolution": {"width": width, "height": height},
        "scene_prompt_count": len(prompt_items),
        "scene_prompts": prompt_items,
    }

    with out.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"[완료] 장면 프롬프트 저장: {out}")
    for item in prompt_items:
        print(f"- Scene {item['scene_index']:02d}: {item['prompt']}")


def resolve_ai_image_generation_settings(
    cfg: dict,
    *,
    config_path: Path,
    images_dir_override: str | None,
    generated_config_override: str | None,
    model_override: str | None,
) -> tuple[Path, Path, str]:
    image_cfg = cfg.get("image_generation", {})
    if image_cfg is not None and not isinstance(image_cfg, dict):
        raise ValueError("image_generation 설정은 객체(dict)여야 합니다.")

    images_dir_value = (
        images_dir_override
        if images_dir_override
        else image_cfg.get("output_dir", "output/generated_ai_images")
    )
    generated_config_value = (
        generated_config_override
        if generated_config_override
        else image_cfg.get("generated_config_output", "output/generated_ai_config.json")
    )
    model_value = (
        model_override
        if model_override
        else image_cfg.get("model", DEFAULT_AI_IMAGE_MODEL)
    )

    images_dir = validate_output_directory_path(images_dir_value, base_dir=Path.cwd().resolve() if images_dir_override else config_path.parent)
    generated_config_path = validate_json_output_path(
        generated_config_value,
        base_dir=Path.cwd().resolve() if generated_config_override else config_path.parent,
    )
    if not isinstance(model_value, str) or not model_value.strip():
        raise ValueError("이미지 생성 모델명은 비어 있지 않은 문자열이어야 합니다.")
    return images_dir, generated_config_path, model_value.strip()


def generate_ai_images(
    *,
    config_path_override: str | None = None,
    images_dir_override: str | None = None,
    generated_config_override: str | None = None,
    model_override: str | None = None,
) -> None:
    cfg, config_path = load_config_for_cli(config_path_override)
    validate_video_config(cfg, config_path=config_path)

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("OPENAI_API_KEY 환경변수가 필요합니다. 코드에 키를 넣지 말고 환경변수로 설정하세요.")
    base_url = os.environ.get("OPENAI_IMAGE_BASE_URL", DEFAULT_OPENAI_IMAGE_BASE_URL).strip() or DEFAULT_OPENAI_IMAGE_BASE_URL

    images_dir, generated_config_path, model_name = resolve_ai_image_generation_settings(
        cfg,
        config_path=config_path,
        images_dir_override=images_dir_override,
        generated_config_override=generated_config_override,
        model_override=model_override,
    )

    prompt_items = []
    vcfg = cfg.get("video", {})
    width = int(vcfg.get("width", 1280))
    height = int(vcfg.get("height", 720))
    size = choose_ai_image_size(width, height)
    project_title = str(cfg.get("project_title", ""))
    subtitle = str(cfg.get("subtitle", ""))
    scenes = cfg.get("scenes", [])
    total = max(1, len(scenes))
    generated_cfg = copy.deepcopy(cfg)

    print(f"[AI 이미지 생성 시작] config={config_path} model={model_name} size={size}")
    for scene_index, scene in enumerate(scenes, start=1):
        scene_prompt = build_scene_prompt(
            scene=scene,
            scene_index=scene_index,
            total_scenes=total,
            project_title=project_title,
            subtitle=subtitle,
            width=width,
            height=height,
        )
        negative_prompt = "blurry, low quality, noisy, distorted anatomy, deformed face, extra limbs, text, logo, watermark"
        prompt_items.append(
            {
                "scene_index": scene_index,
                "prompt": scene_prompt,
                "negative_prompt": negative_prompt,
            }
        )
        output_path = images_dir / f"scene_{scene_index:02d}.png"
        try:
            image_bytes = generate_ai_image_bytes(
                prompt=build_image_generation_prompt(scene_prompt, negative_prompt),
                model=model_name,
                size=size,
                api_key=api_key,
                base_url=base_url,
            )
        except AIImageGenerationError as exc:
            raise RuntimeError(f"{scene_index}번 장면 AI 이미지 생성 실패: {exc}") from exc
        output_path.write_bytes(image_bytes)
        generated_cfg["scenes"][scene_index - 1]["source"] = relative_path_text(
            generated_config_path.parent,
            output_path,
        )
        print(f"[AI 이미지 저장] scene={scene_index:02d} path={output_path}")

    generated_config_path.write_text(
        json.dumps(generated_cfg, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    report_path = generated_config_path.with_name(f"{generated_config_path.stem}_prompts.json")
    report_payload = {
        "config": str(config_path),
        "generated_config": str(generated_config_path),
        "images_dir": str(images_dir),
        "model": model_name,
        "size": size,
        "scene_count": len(prompt_items),
        "scene_prompts": prompt_items,
    }
    report_path.write_text(json.dumps(report_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[AI 이미지 파생 설정 저장] {generated_config_path}")
    print(f"[AI 이미지 프롬프트 리포트 저장] {report_path}")


def find_font(bold: bool = True) -> str | None:
    candidates = [
        ROOT / "assets/fonts/NanumGothicBold.ttf",
        ROOT / "assets/fonts/NanumGothic.ttf",
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf"),
        Path("/usr/share/fonts/truetype/nanum/NanumGothic.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ]
    if not bold:
        candidates = [p for p in candidates if "Bold" not in p.name] + candidates
    for p in candidates:
        if p.exists():
            return str(p)
    return None


def load_font(size: int, bold: bool = True):
    path = find_font(bold=bold)
    if path:
        return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def fit_cover(img: Image.Image, size: Tuple[int, int]) -> Image.Image:
    target_w, target_h = size
    src_w, src_h = img.size
    scale = max(target_w / src_w, target_h / src_h)
    new_w = int(src_w * scale)
    new_h = int(src_h * scale)
    img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    left = max(0, (new_w - target_w) // 2)
    top = max(0, (new_h - target_h) // 2)
    return img.crop((left, top, left + target_w, top + target_h))


def placeholder_scene(index: int, caption: str, size: Tuple[int, int]) -> Image.Image:
    """이미지 파일이 없을 때도 프로젝트가 바로 실행되도록 임시 장면 생성."""
    w, h = size
    # 장면마다 밝기가 조금씩 다른 배경
    base = 54 + (index * 17) % 120
    img = Image.new("RGB", size, (base, min(180, base + 35), min(210, base + 70)))
    draw = ImageDraw.Draw(img)

    # 하늘/들판 느낌의 단순 도형
    draw.rectangle((0, int(h * 0.62), w, h), fill=(80, 135, 74))
    draw.ellipse((int(w * 0.76), int(h * 0.08), int(w * 0.88), int(h * 0.25)), fill=(250, 220, 110))

    # 동물 네 마리를 기호적인 원형 캐릭터로 표시
    centers = [
        (int(w * 0.30), int(h * 0.56)),
        (int(w * 0.43), int(h * 0.59)),
        (int(w * 0.56), int(h * 0.55)),
        (int(w * 0.69), int(h * 0.60)),
    ]
    colors = [(205, 150, 95), (115, 115, 125), (235, 235, 235), (220, 205, 190)]
    for (cx, cy), color in zip(centers, colors):
        r = int(h * 0.075)
        draw.ellipse((cx-r, cy-r, cx+r, cy+r), fill=color, outline=(35, 35, 35), width=4)
        eye = max(3, r // 10)
        draw.ellipse((cx-r//3-eye, cy-r//5-eye, cx-r//3+eye, cy-r//5+eye), fill=(20, 20, 20))
        draw.ellipse((cx+r//3-eye, cy-r//5-eye, cx+r//3+eye, cy-r//5+eye), fill=(20, 20, 20))

    font_big = load_font(max(36, int(h * 0.065)))
    font_small = load_font(max(22, int(h * 0.038)), bold=False)
    title = f"SCENE {index:02d}"
    box = draw.textbbox((0, 0), title, font=font_big)
    draw.text(((w - (box[2]-box[0]))/2, h*0.11), title, font=font_big, fill="white",
              stroke_width=3, stroke_fill=(0,0,0))
    short = caption[:34]
    box2 = draw.textbbox((0, 0), short, font=font_small)
    draw.text(((w - (box2[2]-box2[0]))/2, h*0.25), short, font=font_small, fill="white",
              stroke_width=2, stroke_fill=(0,0,0))
    return img


def caption_overlay(text: str, size: Tuple[int, int]) -> np.ndarray:
    w, h = size
    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = load_font(max(30, int(h * 0.052)))

    max_width = int(w * 0.82)
    words = text.split(" ")
    lines, current = [], ""
    for word in words:
        trial = word if not current else f"{current} {word}"
        bb = draw.textbbox((0,0), trial, font=font, stroke_width=2)
        if bb[2] - bb[0] <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)

    line_h = int(h * 0.072)
    total_h = line_h * len(lines) + int(h * 0.045)
    y0 = h - total_h - int(h * 0.06)

    draw.rounded_rectangle(
        (int(w*0.07), y0, int(w*0.93), h-int(h*0.045)),
        radius=24,
        fill=(0, 0, 0, 150),
    )

    y = y0 + int(h * 0.018)
    for line in lines:
        bb = draw.textbbox((0,0), line, font=font, stroke_width=2)
        tw = bb[2] - bb[0]
        draw.text(
            ((w - tw) / 2, y),
            line,
            font=font,
            fill=(255, 255, 255, 255),
            stroke_width=2,
            stroke_fill=(0,0,0,220),
        )
        y += line_h
    return np.array(overlay)


def title_overlay(title: str, subtitle: str, size: Tuple[int, int]) -> np.ndarray:
    w, h = size
    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    title_font = load_font(max(48, int(h*0.085)))
    sub_font = load_font(max(24, int(h*0.040)), bold=False)

    # 상단 타이틀
    bb = draw.textbbox((0,0), title, font=title_font, stroke_width=3)
    tw = bb[2] - bb[0]
    draw.text(
        ((w-tw)/2, int(h*0.10)),
        title,
        font=title_font,
        fill=(255,255,255,255),
        stroke_width=3,
        stroke_fill=(0,0,0,210),
    )

    bb2 = draw.textbbox((0,0), subtitle, font=sub_font, stroke_width=2)
    sw = bb2[2]-bb2[0]
    draw.text(
        ((w-sw)/2, int(h*0.22)),
        subtitle,
        font=sub_font,
        fill=(255,255,255,245),
        stroke_width=2,
        stroke_fill=(0,0,0,200),
    )
    return np.array(overlay)


def make_image_scene(
    path: Path,
    duration: float,
    caption: str,
    zoom: float,
    size: Tuple[int, int],
    scene_index: int,
    fade_seconds: float,
):
    if path.exists():
        img = Image.open(path).convert("RGB")
        img = fit_cover(img, size)
    else:
        print(f"[안내] 이미지 없음: {path.name} -> 임시 장면으로 대체")
        img = placeholder_scene(scene_index, caption, size)

    base = ImageClip(np.array(img)).with_duration(duration)

    # 1.00 -> zoom 배율로 아주 천천히 확대
    if zoom and zoom > 1.0:
        base = base.with_effects([
            vfx.Resize(lambda t: 1.0 + (zoom - 1.0) * min(1.0, t / max(duration, 0.01)))
        ])

    base = base.with_position(("center", "center"))
    canvas = CompositeVideoClip([base], size=size).with_duration(duration)

    caption_img = caption_overlay(caption, size)
    cap = ImageClip(caption_img, is_mask=False).with_duration(duration)
    canvas = CompositeVideoClip([canvas, cap], size=size).with_duration(duration)

    if fade_seconds > 0:
        canvas = canvas.with_effects([
            vfx.FadeIn(min(fade_seconds, duration/3)),
            vfx.FadeOut(min(fade_seconds, duration/3)),
        ])
    return canvas


def make_video_scene(
    path: Path,
    duration: float,
    caption: str,
    size: Tuple[int, int],
    fade_seconds: float,
):
    clip = VideoFileClip(str(path))
    if clip.duration >= duration:
        clip = clip.subclipped(0, duration)
    else:
        clip = clip.with_effects([vfx.Loop(duration=duration)])

    w, h = clip.size
    target_w, target_h = size
    scale = max(target_w / w, target_h / h)
    clip = clip.resized(scale)
    clip = CompositeVideoClip([clip.with_position(("center", "center"))], size=size).with_duration(duration)

    cap = ImageClip(caption_overlay(caption, size)).with_duration(duration)
    clip = CompositeVideoClip([clip, cap], size=size).with_duration(duration)

    if fade_seconds > 0:
        clip = clip.with_effects([
            vfx.FadeIn(min(fade_seconds, duration/3)),
            vfx.FadeOut(min(fade_seconds, duration/3)),
        ])
    return clip


def build_video(config_path_override: str | None = None):
    cfg, config_path = load_config_for_cli(config_path_override)
    build_video_from_config(cfg, config_path=config_path)


def build_video_from_config(
    cfg: dict,
    *,
    config_path: Path | None = None,
    output_base_dir: Path | None = None,
    output_path: Path | None = None,
) -> None:
    validate_video_config(cfg, config_path=config_path)
    config_base_dir = config_path.parent if config_path is not None else ROOT
    resolved_output_base_dir = output_base_dir or config_base_dir
    vcfg = cfg["video"]
    size = (int(vcfg["width"]), int(vcfg["height"]))
    fps = int(vcfg.get("fps", 30))
    fade_seconds = float(vcfg.get("fade_seconds", 0.35))

    clips = []
    for i, scene in enumerate(cfg["scenes"], start=1):
        source = resolve_repo_relative_path(
            str(scene["source"]),
            base_dir=config_base_dir,
            must_exist=False,
        )
        duration = float(scene.get("duration", 7.5))
        caption = scene.get("caption", "")
        zoom = float(scene.get("zoom", 1.04))

        if source.suffix.lower() in {".mp4", ".mov", ".mkv", ".webm", ".m4v"} and source.exists():
            clip = make_video_scene(source, duration, caption, size, fade_seconds)
        else:
            clip = make_image_scene(source, duration, caption, zoom, size, i, fade_seconds)
        clips.append(clip)

    final = concatenate_videoclips(clips, method="compose")

    # 첫 장면 상단 타이틀
    title_duration = min(4.5, final.duration)
    title = ImageClip(
        title_overlay(cfg.get("project_title", ""), cfg.get("subtitle", ""), size)
    ).with_duration(title_duration)
    title = title.with_effects([vfx.FadeIn(0.5), vfx.FadeOut(0.7)])
    final = CompositeVideoClip([final, title], size=size).with_duration(final.duration)

    # BGM이 있으면 전체 길이에 맞춰 반복 후 믹싱
    bgm_value = cfg.get("bgm", "")
    bgm_path = None
    if isinstance(bgm_value, str) and bgm_value.strip():
        bgm_path = resolve_repo_relative_path(
            str(bgm_value),
            base_dir=config_base_dir,
            must_exist=False,
        )
    if bgm_path is not None and bgm_path.exists():
        bgm = AudioFileClip(str(bgm_path))
        bgm = bgm.with_effects([
            afx.AudioLoop(duration=final.duration),
            afx.MultiplyVolume(float(vcfg.get("bgm_volume", 0.16))),
            afx.AudioFadeIn(1.0),
            afx.AudioFadeOut(1.5),
        ])
        if final.audio is not None:
            final = final.with_audio(CompositeAudioClip([final.audio, bgm]))
        else:
            final = final.with_audio(bgm)
    else:
        missing_bgm = bgm_path if bgm_path is not None else "설정 없음"
        print(f"[안내] BGM 없음: {missing_bgm}. 무음 영상으로 생성합니다.")

    if output_path is not None:
        out = resolve_repo_relative_path(
            str(output_path),
            base_dir=resolved_output_base_dir,
            must_exist=False,
        )
    else:
        out = validate_output_value(cfg, base_dir=resolved_output_base_dir)
    if out.suffix.lower() != ".mp4":
        raise ValueError("output 파일 확장자는 .mp4여야 합니다.")
    out.parent.mkdir(parents=True, exist_ok=True)
    print(f"[렌더링 시작] {out}")
    final.write_videofile(
        str(out),
        fps=fps,
        codec="libx264",
        audio_codec="aac",
        preset="medium",
        threads=4,
        ffmpeg_params=["-pix_fmt", "yuv420p", "-movflags", "+faststart"],
    )
    print(f"[완료] {out}")


def build_batch_videos(
    batch_file_override: str | None = None,
    *,
    retry_failed: int = 0,
    summary_report_path: str | None = None,
) -> None:
    batch_file = batch_file_override or default_batch_file_value()
    batch_path = resolve_repo_relative_path(
        batch_file,
        base_dir=Path.cwd().resolve(),
        must_exist=True,
    )
    batch_cfg = load_json(batch_path)
    if not isinstance(batch_cfg, dict):
        raise ValueError("배치 설정 파일 최상위는 객체(dict)여야 합니다.")
    jobs = batch_cfg.get("jobs")
    if not isinstance(jobs, list) or not jobs:
        raise ValueError("배치 설정 파일에는 1개 이상의 jobs 목록이 필요합니다.")
    report_path = (
        resolve_summary_report_path(summary_report_path, base_dir=Path.cwd().resolve())
        if summary_report_path
        else None
    )

    print(f"[배치 시작] {batch_path} / 총 {len(jobs)}개")
    reserved_outputs: set[Path] = set()
    planned_jobs: list[tuple[str, Path, dict, Path, Path]] = []
    for index, job in enumerate(jobs, start=1):
        if not isinstance(job, dict):
            raise ValueError(f"jobs[{index}]는 객체(dict)여야 합니다.")
        config_rel = job.get("config")
        if not isinstance(config_rel, str) or not config_rel.strip():
            raise ValueError(f"jobs[{index}].config는 필수 문자열입니다.")

        config_path = resolve_repo_relative_path(
            config_rel,
            base_dir=batch_path.parent,
            must_exist=True,
        )
        cfg = load_config_from_path(config_path)
        validate_video_config(cfg, config_path=config_path)
        has_overrides = "overrides" in job
        overrides = job.get("overrides", {})
        if has_overrides and not isinstance(overrides, dict):
            raise ValueError(f"jobs[{index}].overrides는 객체(dict)여야 합니다.")
        if isinstance(overrides, dict) and overrides:
            normalized_overrides = normalize_batch_overrides(
                overrides,
                batch_base_dir=batch_path.parent,
                config_base_dir=config_path.parent,
            )
            cfg = deep_merge_dict(cfg, normalized_overrides)
            validate_video_config(cfg, config_path=config_path)
        base_output = validate_output_value(cfg, base_dir=config_path.parent)
        final_output_value = base_output
        suffix_index = 2
        while final_output_value in reserved_outputs or final_output_value.exists():
            final_output_value = with_batch_index_suffix(base_output, suffix_index)
            suffix_index += 1
        reserved_outputs.add(final_output_value)
        name = str(job.get("name", f"batch-{index:02d}"))
        planned_jobs.append((name, config_path, cfg, config_path.parent, final_output_value))

    success_count = 0
    failure_count = 0
    failed_jobs: list[str] = []
    retry_successes: list[dict[str, Any]] = []
    job_results: list[dict[str, Any]] = []
    start_time = time.perf_counter()
    for index, (name, config_path, cfg, output_base_dir, final_output_value) in enumerate(planned_jobs, start=1):
        try:
            cfg["output"] = str(final_output_value.relative_to(output_base_dir))
        except ValueError:
            cfg["output"] = str(final_output_value)
        print(f"[배치 작업 {index}/{len(jobs)}] {name} ({config_path})")
        print(f"[배치 출력 예정] {final_output_value}")
        max_attempts = retry_failed + 1
        attempts_used = 0
        job_succeeded = False
        for attempt in range(1, max_attempts + 1):
            attempts_used = attempt
            print(f"[배치 시도] {name} attempt {attempt}/{max_attempts}")
            try:
                build_video_from_config(
                    cfg,
                    config_path=config_path,
                    output_base_dir=output_base_dir,
                    output_path=final_output_value,
                )
                if attempt > 1:
                    retry_successes.append({
                        "job": name,
                        "succeeded_on_attempt": attempt,
                    })
                job_results.append({
                    "job": name,
                    "status": "success",
                    "attempts_used": attempts_used,
                    "max_attempts": max_attempts,
                    "retried": attempts_used > 1,
                    "succeeded_on_attempt": attempts_used,
                    "output_path": str(final_output_value),
                    "error": None,
                })
                job_succeeded = True
                break
            except Exception as exc:
                if attempt >= max_attempts:
                    failure_count += 1
                    failed_jobs.append(name)
                    print(f"[배치 실패] {name}: {exc}")
                    job_results.append({
                        "job": name,
                        "status": "failure",
                        "attempts_used": attempts_used,
                        "max_attempts": max_attempts,
                        "retried": max_attempts > 1,
                        "succeeded_on_attempt": None,
                        "output_path": str(final_output_value),
                        "error": str(exc),
                    })
                    break
                print(f"[배치 재시도] {name}: {exc}")
        if job_succeeded:
            print(f"[배치 출력] {final_output_value}")
            success_count += 1
    duration_seconds = time.perf_counter() - start_time
    print_batch_summary_lines("[배치 작업 요약]", job_results)
    write_batch_summary_report(
        report_path=report_path,
        mode="batch-render",
        batch_path=batch_path,
        total_jobs=len(jobs),
        success_count=success_count,
        failure_count=failure_count,
        failed_jobs=failed_jobs,
        retry_successes=retry_successes,
        job_results=job_results,
        stopped_on_failure=False,
        duration_seconds=duration_seconds,
    )
    if failure_count > 0:
        raise SystemExit(1)
    print("[배치 완료] 모든 영상 렌더링이 끝났습니다.")


def build_batch_image_prompts(
    batch_file_override: str | None = None,
    *,
    retry_failed: int = 0,
    summary_report_path: str | None = None,
) -> None:
    batch_file = batch_file_override or default_batch_file_value()
    batch_path = resolve_repo_relative_path(
        batch_file,
        base_dir=Path.cwd().resolve(),
        must_exist=True,
    )
    batch_cfg = load_json(batch_path)
    if not isinstance(batch_cfg, dict):
        raise ValueError("배치 설정 파일 최상위는 객체(dict)여야 합니다.")
    jobs = batch_cfg.get("jobs")
    if not isinstance(jobs, list) or not jobs:
        raise ValueError("배치 설정 파일에는 1개 이상의 jobs 목록이 필요합니다.")
    report_path = (
        resolve_summary_report_path(summary_report_path, base_dir=Path.cwd().resolve())
        if summary_report_path
        else None
    )
    filename_pattern = batch_cfg.get("prompt_filename_pattern")
    if filename_pattern is not None and (not isinstance(filename_pattern, str) or not filename_pattern.strip()):
        raise ValueError("prompt_filename_pattern은 비어 있지 않은 문자열이어야 합니다.")

    print(f"[배치 프롬프트 시작] {batch_path} / 총 {len(jobs)}개")
    reserved_outputs: set[Path] = set()
    planned_jobs: list[tuple[str, Path, dict, Path, Path]] = []
    for index, job in enumerate(jobs, start=1):
        if not isinstance(job, dict):
            raise ValueError(f"jobs[{index}]는 객체(dict)여야 합니다.")
        config_rel = job.get("config")
        if not isinstance(config_rel, str) or not config_rel.strip():
            raise ValueError(f"jobs[{index}].config는 필수 문자열입니다.")

        config_path = resolve_repo_relative_path(
            config_rel,
            base_dir=batch_path.parent,
            must_exist=True,
        )
        cfg = load_config_from_path(config_path)
        validate_video_config(cfg, config_path=config_path)
        has_overrides = "overrides" in job
        overrides = job.get("overrides", {})
        if has_overrides and not isinstance(overrides, dict):
            raise ValueError(f"jobs[{index}].overrides는 객체(dict)여야 합니다.")
        if isinstance(overrides, dict) and overrides:
            normalized_overrides = normalize_batch_overrides(
                overrides,
                batch_base_dir=batch_path.parent,
                config_base_dir=config_path.parent,
            )
            cfg = deep_merge_dict(cfg, normalized_overrides)
            validate_video_config(cfg, config_path=config_path)
        base_output = validate_prompt_output_value(cfg, base_dir=config_path.parent)
        if filename_pattern:
            custom_name = build_prompt_filename_from_pattern(
                filename_pattern,
                index=index,
                job_name=str(job.get("name", f"batch-{index:02d}")),
                config_stem=config_path.stem,
                default_stem=base_output.stem or "scene_image_prompts",
            )
            desired_output_base = base_output.with_name(custom_name)
        else:
            desired_output_base = base_output
        final_output_value = desired_output_base
        suffix_index = 2
        while final_output_value in reserved_outputs or final_output_value.exists():
            final_output_value = with_batch_index_suffix(desired_output_base, suffix_index, default_suffix=".json")
            suffix_index += 1
        reserved_outputs.add(final_output_value)
        name = str(job.get("name", f"batch-{index:02d}"))
        planned_jobs.append((name, config_path, cfg, config_path.parent, final_output_value))

    success_count = 0
    failure_count = 0
    failed_jobs: list[str] = []
    retry_successes: list[dict[str, Any]] = []
    job_results: list[dict[str, Any]] = []
    start_time = time.perf_counter()
    for index, (name, config_path, cfg, output_base_dir, final_output_value) in enumerate(planned_jobs, start=1):
        try:
            cfg["image_prompt_output"] = str(final_output_value.relative_to(output_base_dir))
        except ValueError:
            cfg["image_prompt_output"] = str(final_output_value)
        print(f"[배치 프롬프트 작업 {index}/{len(jobs)}] {name} ({config_path})")
        print(f"[배치 프롬프트 출력 예정] {final_output_value}")
        max_attempts = retry_failed + 1
        attempts_used = 0
        job_succeeded = False
        for attempt in range(1, max_attempts + 1):
            attempts_used = attempt
            print(f"[배치 프롬프트 시도] {name} attempt {attempt}/{max_attempts}")
            try:
                generate_image_prompts_from_config(
                    cfg,
                    config_path=config_path,
                    output_override=str(final_output_value),
                )
                if attempt > 1:
                    retry_successes.append({
                        "job": name,
                        "succeeded_on_attempt": attempt,
                    })
                job_results.append({
                    "job": name,
                    "status": "success",
                    "attempts_used": attempts_used,
                    "max_attempts": max_attempts,
                    "retried": attempts_used > 1,
                    "succeeded_on_attempt": attempts_used,
                    "output_path": str(final_output_value),
                    "error": None,
                })
                job_succeeded = True
                break
            except Exception as exc:
                if attempt >= max_attempts:
                    failure_count += 1
                    failed_jobs.append(name)
                    print(f"[배치 프롬프트 실패] {name}: {exc}")
                    job_results.append({
                        "job": name,
                        "status": "failure",
                        "attempts_used": attempts_used,
                        "max_attempts": max_attempts,
                        "retried": max_attempts > 1,
                        "succeeded_on_attempt": None,
                        "output_path": str(final_output_value),
                        "error": str(exc),
                    })
                    break
                print(f"[배치 프롬프트 재시도] {name}: {exc}")
        if job_succeeded:
            print(f"[배치 프롬프트 출력] {final_output_value}")
            success_count += 1
    duration_seconds = time.perf_counter() - start_time
    print_batch_summary_lines("[배치 프롬프트 작업 요약]", job_results)
    write_batch_summary_report(
        report_path=report_path,
        mode="batch-prompts",
        batch_path=batch_path,
        total_jobs=len(jobs),
        success_count=success_count,
        failure_count=failure_count,
        failed_jobs=failed_jobs,
        retry_successes=retry_successes,
        job_results=job_results,
        stopped_on_failure=False,
        duration_seconds=duration_seconds,
    )
    if failure_count > 0:
        raise SystemExit(1)
    print("[배치 프롬프트 완료] 모든 프롬프트 생성이 끝났습니다.")


if __name__ == "__main__":
    args = parse_args()
    if args.batch_render:
        build_batch_videos(
            args.batch_file,
            retry_failed=args.retry_failed,
            summary_report_path=args.summary_report,
        )
    elif args.batch_generate_image_prompts:
        build_batch_image_prompts(
            args.batch_file,
            retry_failed=args.retry_failed,
            summary_report_path=args.summary_report,
        )
    elif args.generate_ai_images:
        generate_ai_images(
            config_path_override=args.config,
            images_dir_override=args.generated_images_dir,
            generated_config_override=args.generated_config_output,
            model_override=args.image_model,
        )
    elif args.generate_image_prompts:
        generate_image_prompts(args.prompts_output, config_path_override=args.config)
    else:
        build_video(args.config)
