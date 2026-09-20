from __future__ import annotations

import argparse
import json
import os
from abc import ABC, abstractmethod
from json import JSONDecodeError
from pathlib import Path
from typing import Any
from urllib import error, request

ROOT = Path(__file__).resolve().parent
DEFAULT_SCENE_SPEC = ROOT / "animal_travel_preparation_scene.json"
DEFAULT_OUTPUT_DIR = ROOT / "output" / "video_generation_package"


def load_env_file(env_file: Path) -> None:
    if not env_file.exists():
        return
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), parse_env_value(value))


def parse_env_value(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    if value[0] in {'"', "'"}:
        quote = value[0]
        if len(value) >= 2 and value[-1] == quote:
            inner = value[1:-1]
            return bytes(inner, "utf-8").decode("unicode_escape")
        return value

    comment_index = None
    for index, char in enumerate(value):
        if char == "#" and index > 0 and value[index - 1].isspace():
            comment_index = index
            break
    if comment_index is not None:
        value = value[:comment_index]
    return value.strip()


def load_scene_spec(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def validate_scene_spec(spec: dict[str, Any]) -> None:
    required_keys = [
        "scene_id",
        "title",
        "master_prompt",
        "negative_prompt",
        "character_bible",
        "shots",
    ]
    missing = [key for key in required_keys if key not in spec]
    if missing:
        raise ValueError(f"Scene spec is missing required keys: {', '.join(missing)}")

    characters = spec["character_bible"]
    if not isinstance(characters, list):
        raise ValueError("Scene spec character_bible must be a list.")
    if len(characters) != 5:
        raise ValueError("Scene spec must define exactly five characters.")

    shots = spec["shots"]
    if not isinstance(shots, list):
        raise ValueError("Scene spec shots must be a list.")
    if len(shots) != 4:
        raise ValueError("Scene spec must define exactly four shots.")

    expected_duration = float(spec.get("duration_seconds", 15))
    total_duration = 0.0
    running_offset = 0.0
    for shot in shots:
        missing_shot_keys = [
            key for key in ("id", "start_seconds", "duration_seconds") if key not in shot
        ]
        if missing_shot_keys:
            raise ValueError(
                f"Each shot must include {', '.join(missing_shot_keys)}; "
                f"missing in shot: {shot!r}"
            )
        start_seconds = float(shot["start_seconds"])
        duration_seconds = float(shot["duration_seconds"])
        if duration_seconds <= 0:
            raise ValueError(f"Shot {shot['id']} must have a duration greater than 0 seconds.")
        if abs(start_seconds - running_offset) > 1e-6:
            raise ValueError(
                f"Shot {shot['id']} must start at {running_offset} seconds, got {start_seconds}."
            )
        total_duration += duration_seconds
        running_offset += duration_seconds
    if abs(total_duration - expected_duration) > 1e-6:
        raise ValueError(
            f"Shot durations must total {expected_duration} seconds, got {total_duration}."
        )

    expected_names = {"dog", "cat", "red panda", "giant panda", "fennec fox"}
    actual_names = {character["name"] for character in characters}
    if actual_names != expected_names:
        raise ValueError("Character bible must match the required five characters exactly.")

    for character in characters:
        accessories = str(character.get("accessories", "")).lower()
        if "bag" not in accessories and "backpack" not in accessories and "satchel" not in accessories:
            raise ValueError(f"{character['name']} must have a travel bag or backpack.")


def build_character_consistency_block(spec: dict[str, Any]) -> str:
    character_lines = []
    for character in spec["character_bible"]:
        character_lines.append(
            f"{character['name']}: {character['appearance']}; accessories: {character['accessories']}; behavior: {character['behavior']}"
        )
    return "Character bible (preserve exactly across all shots): " + " | ".join(character_lines)


def build_shot_prompt(spec: dict[str, Any], shot: dict[str, Any]) -> str:
    consistency_block = build_character_consistency_block(spec)
    rules = " ".join(spec.get("consistency_rules", []))
    return (
        f"{spec['master_prompt']} "
        f"{consistency_block} "
        f"Consistency requirements: {rules} "
        f"Shot plan: {shot['camera']}. Focus: {shot['focus']}. Action: {shot['action']}. "
        f"Target shot length: {shot['duration_seconds']} seconds."
    )


def build_scene_package(spec: dict[str, Any]) -> dict[str, Any]:
    return {
        "scene_id": spec["scene_id"],
        "title": spec["title"],
        "aspect_ratio": spec.get("aspect_ratio", "16:9"),
        "duration_seconds": spec.get("duration_seconds", 15),
        "master_prompt": spec["master_prompt"],
        "negative_prompt": spec["negative_prompt"],
        "consistency_rules": spec.get("consistency_rules", []),
        "character_bible": spec["character_bible"],
        "shots": [
            {
                **shot,
                "prompt": build_shot_prompt(spec, shot),
                "negative_prompt": spec["negative_prompt"],
            }
            for shot in spec["shots"]
        ],
    }


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_timeout(timeout_value: str) -> int:
    try:
        timeout = int(timeout_value)
    except ValueError as exc:
        raise ValueError("VIDEO_API_TIMEOUT must be an integer number of seconds.") from exc
    if timeout <= 0:
        raise ValueError("VIDEO_API_TIMEOUT must be greater than 0 seconds.")
    return timeout


def decode_provider_response(response_text: str) -> dict[str, Any]:
    if not response_text:
        return {}
    try:
        payload = json.loads(response_text)
    except JSONDecodeError:
        return {"raw_response": response_text}
    if isinstance(payload, dict):
        return payload
    return {"parsed_response": payload}


def import_runway_client():
    try:
        from runwayml import RunwayML
    except ImportError as exc:
        raise RuntimeError(
            "Runway SDK is not installed. Run `pip install -r requirements.txt` first."
        ) from exc
    return RunwayML


def parse_runway_duration(duration_value: str) -> str | int:
    value = duration_value.strip().lower()
    if value == "auto":
        return "auto"
    try:
        duration = int(value)
    except ValueError as exc:
        raise ValueError("RUNWAY_DURATION must be 'auto' or an integer number of seconds.") from exc
    if duration <= 0:
        raise ValueError("RUNWAY_DURATION must be greater than 0 seconds.")
    return duration


def resolve_runway_ratio(package: dict[str, Any]) -> str:
    ratio_value = os.environ.get("RUNWAY_RATIO", "").strip()
    if ratio_value:
        return ratio_value
    aspect_ratio = str(package.get("aspect_ratio", "16:9")).strip()
    aspect_to_ratio = {
        "16:9": "1280:720",
        "9:16": "720:1280",
        "1:1": "960:960",
    }
    return aspect_to_ratio.get(aspect_ratio, "1280:720")


def serialize_runway_task(task: Any) -> dict[str, Any]:
    if hasattr(task, "model_dump"):
        payload = task.model_dump()
        if isinstance(payload, dict):
            return payload
    if hasattr(task, "to_dict"):
        payload = task.to_dict()
        if isinstance(payload, dict):
            return payload
    return {"id": getattr(task, "id", None)}


class ProviderAdapter(ABC):
    @abstractmethod
    def run(self, package: dict[str, Any], output_dir: Path) -> dict[str, Any]:
        raise NotImplementedError


class DryRunAdapter(ProviderAdapter):
    def run(self, package: dict[str, Any], output_dir: Path) -> dict[str, Any]:
        request_payload = {
            "provider": "dry-run",
            "mode": "package-only",
            "scene_package": package,
        }
        write_json(output_dir / "scene_package.json", package)
        write_json(output_dir / "provider_request.json", request_payload)
        result = {
            "provider": "dry-run",
            "status": "package_created",
            "output_dir": str(output_dir),
            "scene_package": str(output_dir / "scene_package.json"),
            "request_payload": str(output_dir / "provider_request.json"),
        }
        write_json(output_dir / "run_summary.json", result)
        return result


class GenericWebhookAdapter(ProviderAdapter):
    def __init__(self, api_url: str, api_key: str | None, timeout: int) -> None:
        self.api_url = api_url
        self.api_key = api_key
        self.timeout = timeout

    def run(self, package: dict[str, Any], output_dir: Path) -> dict[str, Any]:
        request_payload = {
            "provider": "generic-webhook",
            "scene_package": package,
        }
        write_json(output_dir / "scene_package.json", package)
        write_json(output_dir / "provider_request.json", request_payload)

        data = json.dumps(request_payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = "Bearer " + self.api_key

        http_request = request.Request(self.api_url, data=data, headers=headers, method="POST")
        try:
            with request.urlopen(http_request, timeout=self.timeout) as response:
                response_text = response.read().decode("utf-8")
                response_payload = decode_provider_response(response_text)
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Provider request failed with HTTP {exc.code}: {detail}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"Provider request failed: {exc.reason}") from exc

        result = {
            "provider": "generic-webhook",
            "status": "submitted",
            "output_dir": str(output_dir),
            "scene_package": str(output_dir / "scene_package.json"),
            "request_payload": str(output_dir / "provider_request.json"),
            "response_payload": str(output_dir / "submission_response.json"),
        }
        write_json(output_dir / "submission_response.json", response_payload)
        write_json(output_dir / "run_summary.json", result)
        return result


class RunwayAdapter(ProviderAdapter):
    def __init__(
        self,
        api_key: str,
        model: str,
        generation_mode: str,
        duration: str | int,
        prompt_image: str | None,
        client_factory: Any | None = None,
    ) -> None:
        if generation_mode not in {"text_to_video", "image_to_video"}:
            raise ValueError("RUNWAY_GENERATION_MODE must be text_to_video or image_to_video.")
        self.api_key = api_key
        self.model = model
        self.generation_mode = generation_mode
        self.duration = duration
        self.prompt_image = prompt_image
        self.client_factory = client_factory or import_runway_client()

    def run(self, package: dict[str, Any], output_dir: Path) -> dict[str, Any]:
        ratio = resolve_runway_ratio(package)
        prompt_image = self.prompt_image.strip() if self.prompt_image else None
        if self.generation_mode == "image_to_video" and not prompt_image:
            raise ValueError(
                "RUNWAY_PROMPT_IMAGE is required when RUNWAY_GENERATION_MODE=image_to_video."
            )
        client = self.client_factory(api_key=self.api_key)
        tasks = []

        write_json(output_dir / "scene_package.json", package)

        for shot in package["shots"]:
            create_kwargs = {
                "model": self.model,
                "prompt_text": shot["prompt"],
                "ratio": ratio,
                "duration": self.duration,
                "negative_prompt": shot["negative_prompt"],
            }
            if self.generation_mode == "image_to_video":
                create_kwargs["prompt_image"] = prompt_image
                try:
                    task = client.image_to_video.create(**create_kwargs)
                except Exception as exc:
                    raise RuntimeError(
                        f"Runway submission failed for shot {shot['id']}: {exc}"
                    ) from exc
            else:
                try:
                    task = client.text_to_video.create(**create_kwargs)
                except Exception as exc:
                    raise RuntimeError(
                        f"Runway submission failed for shot {shot['id']}: {exc}"
                    ) from exc

            tasks.append(
                {
                    "shot_id": shot["id"],
                    "task_id": getattr(task, "id", None),
                    "request": create_kwargs,
                    "response": serialize_runway_task(task),
                }
            )

        response_payload = {
            "provider": "runway",
            "generation_mode": self.generation_mode,
            "model": self.model,
            "ratio": ratio,
            "tasks": tasks,
        }
        result = {
            "provider": "runway",
            "status": "submitted",
            "output_dir": str(output_dir),
            "scene_package": str(output_dir / "scene_package.json"),
            "response_payload": str(output_dir / "submission_response.json"),
        }
        write_json(output_dir / "submission_response.json", response_payload)
        write_json(output_dir / "run_summary.json", result)
        return result


def build_adapter(provider: str, dry_run: bool) -> ProviderAdapter:
    provider = provider.strip().lower()
    if dry_run or provider == "dry-run":
        return DryRunAdapter()
    if provider == "runway":
        api_key = (
            os.environ.get("RUNWAYML_API_SECRET")
            or os.environ.get("RUNWAY_API_KEY")
            or os.environ.get("VIDEO_API_KEY")
            or ""
        ).strip()
        if not api_key:
            raise ValueError(
                "RUNWAYML_API_SECRET, RUNWAY_API_KEY, or VIDEO_API_KEY is required when VIDEO_PROVIDER=runway."
            )
        generation_mode = os.environ.get("RUNWAY_GENERATION_MODE", "text_to_video").strip().lower()
        if generation_mode not in {"text_to_video", "image_to_video"}:
            raise ValueError("RUNWAY_GENERATION_MODE must be text_to_video or image_to_video.")
        return RunwayAdapter(
            api_key=api_key,
            model=os.environ.get("RUNWAY_MODEL", "gen4_turbo").strip() or "gen4_turbo",
            generation_mode=generation_mode,
            duration=parse_runway_duration(os.environ.get("RUNWAY_DURATION", "auto")),
            prompt_image=os.environ.get("RUNWAY_PROMPT_IMAGE"),
        )
    if provider == "generic-webhook":
        api_url = os.environ.get("VIDEO_API_URL", "").strip()
        if not api_url:
            raise ValueError("VIDEO_API_URL is required when VIDEO_PROVIDER=generic-webhook.")
        timeout = parse_timeout(os.environ.get("VIDEO_API_TIMEOUT", "120"))
        return GenericWebhookAdapter(
            api_url=api_url,
            api_key=os.environ.get("VIDEO_API_KEY"),
            timeout=timeout,
        )
    raise ValueError(f"Unsupported VIDEO_PROVIDER: {provider}")


def resolve_config_path(value: str | None, default_path: Path, base_dir: Path) -> Path:
    if value is None:
        return default_path
    path = Path(value)
    if path.is_absolute():
        return path
    return base_dir / path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate or submit a packaged AI video workflow.")
    parser.add_argument(
        "--spec",
        default=None,
        help="Path to the scene specification JSON file.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory where the generated package or provider response will be written.",
    )
    parser.add_argument(
        "--provider",
        default=None,
        help="Provider adapter name. Supported: dry-run, generic-webhook, runway.",
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Optional env file to preload before reading configuration.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Force package generation without submitting to a provider.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cwd = Path.cwd()
    env_file_path = resolve_config_path(args.env_file, cwd / ".env", cwd)
    load_env_file(env_file_path)

    spec_env_value = os.environ.get("VIDEO_SCENE_SPEC")
    output_dir_env_value = os.environ.get("VIDEO_OUTPUT_DIR")
    provider_value = args.provider or os.environ.get("VIDEO_PROVIDER", "dry-run")

    spec_path = (
        resolve_config_path(args.spec, DEFAULT_SCENE_SPEC, cwd)
        if args.spec is not None
        else resolve_config_path(spec_env_value, DEFAULT_SCENE_SPEC, ROOT)
    )
    output_dir = (
        resolve_config_path(args.output_dir, DEFAULT_OUTPUT_DIR, cwd)
        if args.output_dir is not None
        else resolve_config_path(output_dir_env_value, DEFAULT_OUTPUT_DIR, ROOT)
    )

    spec = load_scene_spec(spec_path)
    validate_scene_spec(spec)
    package = build_scene_package(spec)
    adapter = build_adapter(provider_value, args.dry_run)
    result = adapter.run(package, output_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
