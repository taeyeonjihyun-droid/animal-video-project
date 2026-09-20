from __future__ import annotations

import argparse
import copy
import json
import math
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

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"


def load_config() -> dict:
    return load_config_from_path(CONFIG_PATH)


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_config_from_path(path: Path) -> dict:
    data = load_json(path)
    if not isinstance(data, dict):
        raise ValueError(f"설정 파일 최상위는 객체(dict)여야 합니다: {path}")
    return data


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


def parse_args() -> argparse.Namespace:
    """Parse CLI flags and return an argparse.Namespace for execution mode selection."""
    parser = argparse.ArgumentParser(description="Animal video renderer / scene prompt generator")
    parser.add_argument(
        "--generate-image-prompts",
        action="store_true",
        help="config.json의 scenes를 기반으로 AI 이미지 프롬프트를 생성합니다.",
    )
    parser.add_argument(
        "--prompts-output",
        type=str,
        default=None,
        help="프롬프트 JSON 출력 경로 (프로젝트 내부 경로, 기본: output/scene_image_prompts.json)",
    )
    parser.add_argument(
        "--batch-render",
        action="store_true",
        help="배치 설정 파일을 읽어 여러 편 영상을 순차 렌더링합니다.",
    )
    parser.add_argument(
        "--batch-file",
        type=str,
        default=None,
        help="배치 설정 JSON 경로 (현재 디렉터리 기준 상대 경로 또는 절대 경로, 기본: batch_config.json)",
    )
    args = parser.parse_args()
    if args.prompts_output and not args.generate_image_prompts:
        parser.error("--prompts-output는 --generate-image-prompts와 함께 사용해야 합니다.")
    if args.batch_file and not args.batch_render:
        parser.error("--batch-file은 --batch-render와 함께 사용해야 합니다.")
    if args.batch_render and args.generate_image_prompts:
        parser.error("--batch-render와 --generate-image-prompts는 동시에 사용할 수 없습니다.")
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


def generate_image_prompts(output_override: str | None = None) -> None:
    cfg = load_config()
    generate_image_prompts_from_config(
        cfg=cfg,
        output_override=output_override,
    )


def generate_image_prompts_from_config(
    cfg: dict,
    *,
    output_override: str | None = None,
) -> None:
    vcfg = cfg.get("video", {})
    width = int(vcfg.get("width", 1280))
    height = int(vcfg.get("height", 720))
    if width <= 0 or height <= 0:
        raise ValueError("video.width와 video.height는 1 이상의 값이어야 합니다.")

    scenes = cfg.get("scenes", [])
    if not isinstance(scenes, list) or not all(isinstance(scene, dict) for scene in scenes):
        raise ValueError("config.json의 scenes는 장면 객체(dict) 목록(list)이어야 합니다.")
    if not scenes:
        raise ValueError("config.json의 scenes가 비어 있습니다. 최소 1개 장면이 필요합니다.")
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
        base_dir=Path.cwd().resolve() if output_override else ROOT,
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


def build_video():
    cfg = load_config()
    build_video_from_config(cfg)


def build_video_from_config(cfg: dict) -> None:
    vcfg = cfg["video"]
    size = (int(vcfg["width"]), int(vcfg["height"]))
    fps = int(vcfg.get("fps", 30))
    fade_seconds = float(vcfg.get("fade_seconds", 0.35))

    clips = []
    for i, scene in enumerate(cfg["scenes"], start=1):
        source = ROOT / scene["source"]
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
    bgm_path = ROOT / cfg.get("bgm", "")
    if bgm_path.exists():
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
        print(f"[안내] BGM 없음: {bgm_path}. 무음 영상으로 생성합니다.")

    out = ROOT / cfg.get("output", "output/animal_trip.mp4")
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


def build_batch_videos(batch_file_override: str | None = None) -> None:
    batch_file = batch_file_override or "batch_config.json"
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

    print(f"[배치 시작] {batch_path} / 총 {len(jobs)}개")
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
        has_overrides = "overrides" in job
        overrides = job.get("overrides", {})
        if has_overrides and not isinstance(overrides, dict):
            raise ValueError(f"jobs[{index}].overrides는 객체(dict)여야 합니다.")
        if isinstance(overrides, dict) and overrides:
            cfg = deep_merge_dict(cfg, overrides)

        name = str(job.get("name", f"batch-{index:02d}"))
        print(f"[배치 작업 {index}/{len(jobs)}] {name} ({config_path})")
        build_video_from_config(cfg)
    print("[배치 완료] 모든 영상 렌더링이 끝났습니다.")


if __name__ == "__main__":
    args = parse_args()
    if args.batch_render:
        build_batch_videos(args.batch_file)
    elif args.generate_image_prompts:
        generate_image_prompts(args.prompts_output)
    else:
        build_video()
