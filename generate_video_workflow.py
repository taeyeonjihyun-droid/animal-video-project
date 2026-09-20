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
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ.setdefault(key.strip(), value)


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
    if len(characters) != 5:
        raise ValueError("Scene spec must define exactly five characters.")

    shots = spec["shots"]
    if len(shots) != 4:
        raise ValueError("Scene spec must define exactly four shots.")

    expected_duration = float(spec.get("duration_seconds", 15))
    total_duration = sum(float(shot["duration_seconds"]) for shot in shots)
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


def build_adapter(provider: str, dry_run: bool) -> ProviderAdapter:
    provider = provider.strip().lower()
    if dry_run or provider == "dry-run":
        return DryRunAdapter()
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
        help="Provider adapter name. Supported: dry-run, generic-webhook.",
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
    env_file_path = Path(args.env_file)
    if not env_file_path.is_absolute():
        env_file_path = ROOT / env_file_path
    load_env_file(env_file_path)

    spec_value = args.spec or os.environ.get("VIDEO_SCENE_SPEC", str(DEFAULT_SCENE_SPEC))
    output_dir_value = args.output_dir or os.environ.get("VIDEO_OUTPUT_DIR", str(DEFAULT_OUTPUT_DIR))
    provider_value = args.provider or os.environ.get("VIDEO_PROVIDER", "dry-run")

    spec_path = Path(spec_value)
    if not spec_path.is_absolute():
        spec_path = ROOT / spec_path

    output_dir = Path(output_dir_value)
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir

    spec = load_scene_spec(spec_path)
    validate_scene_spec(spec)
    package = build_scene_package(spec)
    adapter = build_adapter(provider_value, args.dry_run)
    result = adapter.run(package, output_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
