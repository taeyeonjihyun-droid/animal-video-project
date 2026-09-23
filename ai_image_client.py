from __future__ import annotations

import base64
import json
from urllib import error, request
from urllib.parse import urlparse

DEFAULT_OPENAI_IMAGE_BASE_URL = "https://api.openai.com/v1"


class AIImageGenerationError(RuntimeError):
    pass


def validate_generated_image_url(image_url: str, base_url: str) -> None:
    parsed_image = urlparse(image_url)
    parsed_base = urlparse(base_url)
    if parsed_image.scheme not in {"http", "https"}:
        raise AIImageGenerationError("생성된 이미지 URL은 http/https만 허용됩니다.")
    if not parsed_image.hostname or not parsed_base.hostname:
        raise AIImageGenerationError("생성된 이미지 URL 또는 API base URL 호스트 검증에 실패했습니다.")
    if parsed_image.hostname != parsed_base.hostname:
        raise AIImageGenerationError("생성된 이미지 URL 호스트가 허용된 API 호스트와 다릅니다.")


def generate_openai_compatible_image(
    *,
    prompt: str,
    model: str,
    size: str,
    api_key: str,
    base_url: str = DEFAULT_OPENAI_IMAGE_BASE_URL,
    timeout_seconds: int = 180,
) -> bytes:
    endpoint = f"{base_url.rstrip('/')}/images/generations"
    payload = {
        "model": model,
        "prompt": prompt,
        "size": size,
        "response_format": "b64_json",
    }
    req = request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + api_key,
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=timeout_seconds) as response:
            body = response.read()
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise AIImageGenerationError(f"이미지 생성 API 요청이 실패했습니다: {exc.code} {detail}") from exc
    except error.URLError as exc:
        raise AIImageGenerationError(f"이미지 생성 API에 연결할 수 없습니다: {exc.reason}") from exc

    try:
        payload_json = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise AIImageGenerationError("이미지 생성 API 응답이 올바른 JSON이 아닙니다.") from exc

    data = payload_json.get("data")
    if not isinstance(data, list) or not data:
        raise AIImageGenerationError("이미지 생성 API 응답에 data 항목이 없습니다.")

    item = data[0]
    if not isinstance(item, dict):
        raise AIImageGenerationError("이미지 생성 API 응답 형식이 올바르지 않습니다.")

    b64_value = item.get("b64_json")
    if isinstance(b64_value, str) and b64_value:
        try:
            return base64.b64decode(b64_value)
        except (ValueError, TypeError) as exc:
            raise AIImageGenerationError("이미지 생성 API의 b64_json 디코딩에 실패했습니다.") from exc

    image_url = item.get("url")
    if isinstance(image_url, str) and image_url:
        validate_generated_image_url(image_url, base_url)
        try:
            with request.urlopen(image_url, timeout=timeout_seconds) as response:
                return response.read()
        except error.URLError as exc:
            raise AIImageGenerationError(f"생성된 이미지 다운로드에 실패했습니다: {exc.reason}") from exc

    raise AIImageGenerationError("이미지 생성 API 응답에 b64_json 또는 url이 없습니다.")
