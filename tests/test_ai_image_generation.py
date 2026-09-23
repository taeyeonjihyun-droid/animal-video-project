import base64
import json
import os
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

import ai_image_client
import main


class _FakeResponse:
    def __init__(self, payload: bytes):
        self.payload = payload

    def read(self):
        return self.payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class AIImageGenerationTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = main.ROOT / "tmp_test_ai_images"
        self.tmp_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _write_json(self, path: Path, payload):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def _png_bytes(self, color=(255, 0, 0)):
        image = Image.new("RGB", (8, 8), color)
        path = self.tmp_dir / "sample.png"
        image.save(path, format="PNG")
        return path.read_bytes()

    def test_choose_ai_image_size_matches_orientation(self):
        self.assertEqual(main.choose_ai_image_size(1080, 1920), "1024x1536")
        self.assertEqual(main.choose_ai_image_size(1920, 1080), "1536x1024")
        self.assertEqual(main.choose_ai_image_size(1024, 1024), "1024x1024")

    def test_generate_ai_images_writes_images_and_generated_config(self):
        config_path = self.tmp_dir / "episode.json"
        self._write_json(
            config_path,
            {
                "project_title": "테스트",
                "subtitle": "이미지 생성",
                "video": {"width": 1080, "height": 1920, "fps": 30, "fade_seconds": 0.1},
                "output": "output/test.mp4",
                "scenes": [
                    {"source": "assets/images/one.png", "caption": "첫 장면", "duration": 0.5, "zoom": 1.0},
                    {"source": "assets/images/two.png", "caption": "둘째 장면", "duration": 0.5, "zoom": 1.0},
                ],
            },
        )

        rel_config_path = config_path.relative_to(main.ROOT).as_posix()
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False):
            with patch("main.generate_ai_image_bytes", return_value=self._png_bytes()) as mocked_generate:
                main.generate_ai_images(config_path_override=rel_config_path)

        self.assertEqual(mocked_generate.call_count, 2)
        generated_dir = self.tmp_dir / "output" / "generated_ai_images"
        generated_config_path = self.tmp_dir / "output" / "generated_ai_config.json"
        prompts_report_path = self.tmp_dir / "output" / "generated_ai_config_prompts.json"
        self.assertTrue((generated_dir / "scene_01.png").exists())
        self.assertTrue((generated_dir / "scene_02.png").exists())
        self.assertTrue(generated_config_path.exists())
        self.assertTrue(prompts_report_path.exists())

        generated_cfg = json.loads(generated_config_path.read_text(encoding="utf-8"))
        self.assertEqual(generated_cfg["scenes"][0]["source"], "generated_ai_images/scene_01.png")
        self.assertEqual(generated_cfg["scenes"][1]["source"], "generated_ai_images/scene_02.png")

    def test_generate_ai_images_requires_api_key(self):
        config_path = self.tmp_dir / "episode.json"
        self._write_json(
            config_path,
            {
                "project_title": "테스트",
                "subtitle": "이미지 생성",
                "video": {"width": 1080, "height": 1920, "fps": 30, "fade_seconds": 0.1},
                "output": "output/test.mp4",
                "scenes": [{"source": "assets/images/one.png", "caption": "첫 장면", "duration": 0.5, "zoom": 1.0}],
            },
        )

        rel_config_path = config_path.relative_to(main.ROOT).as_posix()
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                main.generate_ai_images(config_path_override=rel_config_path)

    def test_validate_video_config_rejects_missing_video_source(self):
        config_path = self.tmp_dir / "episode.json"
        self._write_json(
            config_path,
            {
                "project_title": "테스트",
                "subtitle": "비디오 검증",
                "video": {"width": 1080, "height": 1920, "fps": 30, "fade_seconds": 0.1},
                "output": "output/test.mp4",
                "scenes": [{"source": "assets/clips/missing.mp4", "caption": "첫 장면", "duration": 0.5, "zoom": 1.0}],
            },
        )

        cfg = main.load_config_from_path(config_path)
        with self.assertRaises(ValueError):
            main.validate_video_config(cfg, config_path=config_path)

    def test_openai_compatible_image_decodes_b64_json(self):
        png_bytes = self._png_bytes(color=(0, 0, 255))
        payload = json.dumps(
            {"data": [{"b64_json": base64.b64encode(png_bytes).decode("ascii")}]}
        ).encode("utf-8")

        with patch("ai_image_client.request.urlopen", return_value=_FakeResponse(payload)) as mocked_urlopen:
            result = ai_image_client.generate_openai_compatible_image(
                prompt="test prompt",
                model="gpt-image-1",
                size="1024x1024",
                api_key="dummy-key",
            )

        self.assertEqual(result, png_bytes)
        request_arg = mocked_urlopen.call_args.args[0]
        self.assertEqual(request_arg.full_url, "https://api.openai.com/v1/images/generations")


if __name__ == "__main__":
    unittest.main()
