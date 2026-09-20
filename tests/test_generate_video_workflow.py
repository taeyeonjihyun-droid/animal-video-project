import io
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
from urllib import error

from generate_video_workflow import (
    DEFAULT_SCENE_SPEC,
    GenericWebhookAdapter,
    build_scene_package,
    build_shot_prompt,
    decode_provider_response,
    load_scene_spec,
    parse_timeout,
    validate_scene_spec,
)


class GenerateVideoWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = load_scene_spec(Path(DEFAULT_SCENE_SPEC))

    def test_scene_spec_is_valid(self):
        validate_scene_spec(self.spec)

    def test_scene_spec_rejects_invalid_character_count(self):
        invalid_spec = deepcopy(self.spec)
        invalid_spec["character_bible"] = invalid_spec["character_bible"][:-1]
        with self.assertRaisesRegex(ValueError, "exactly five characters"):
            validate_scene_spec(invalid_spec)

    def test_scene_spec_rejects_invalid_shot_count(self):
        invalid_spec = deepcopy(self.spec)
        invalid_spec["shots"] = invalid_spec["shots"][:-1]
        with self.assertRaisesRegex(ValueError, "exactly four shots"):
            validate_scene_spec(invalid_spec)

    def test_scene_spec_rejects_invalid_shot_sequence(self):
        invalid_spec = deepcopy(self.spec)
        invalid_spec["shots"][1]["start_seconds"] = 99
        with self.assertRaisesRegex(ValueError, "must start at"):
            validate_scene_spec(invalid_spec)

    def test_scene_spec_rejects_non_positive_shot_duration(self):
        invalid_spec = deepcopy(self.spec)
        invalid_spec["shots"][0]["duration_seconds"] = 0
        with self.assertRaisesRegex(ValueError, "greater than 0 seconds"):
            validate_scene_spec(invalid_spec)

    def test_scene_package_contains_four_consistent_shots(self):
        package = build_scene_package(self.spec)

        self.assertEqual(package["scene_id"], "animal-travel-preparation")
        self.assertEqual(len(package["shots"]), 4)
        self.assertAlmostEqual(
            sum(shot["duration_seconds"] for shot in package["shots"]),
            15.0,
        )
        for shot in package["shots"]:
            self.assertEqual(shot["negative_prompt"], package["negative_prompt"])
            self.assertIn("Character bible (preserve exactly across all shots):", shot["prompt"])
            self.assertIn("dog:", shot["prompt"])
            self.assertIn("cat:", shot["prompt"])
            self.assertIn("red panda:", shot["prompt"])
            self.assertIn("giant panda:", shot["prompt"])
            self.assertIn("fennec fox:", shot["prompt"])

    def test_first_shot_prompt_preserves_required_scene_details(self):
        first_shot = self.spec["shots"][0]
        prompt = build_shot_prompt(self.spec, first_shot)

        self.assertIn("cozy house", prompt)
        self.assertIn("warm early-morning sunlight", prompt)
        self.assertIn("All five wear the same small travel bags or backpacks", prompt)
        self.assertIn("dog wags tail", prompt)
        self.assertIn("cat checks the stacked luggage", prompt)
        self.assertIn("giant panda", prompt)
        self.assertIn("fennec fox", prompt)

    def test_parse_timeout_rejects_non_positive_values(self):
        self.assertEqual(parse_timeout("120"), 120)
        with self.assertRaisesRegex(ValueError, "integer number of seconds"):
            parse_timeout("abc")
        with self.assertRaisesRegex(ValueError, "greater than 0"):
            parse_timeout("0")
        with self.assertRaisesRegex(ValueError, "greater than 0"):
            parse_timeout("-3")

    def test_decode_provider_response_supports_plain_text(self):
        self.assertEqual(decode_provider_response(""), {})
        self.assertEqual(decode_provider_response('{"job_id":"abc"}'), {"job_id": "abc"})
        self.assertEqual(
            decode_provider_response("job-12345"),
            {"raw_response": "job-12345"},
        )
        self.assertEqual(
            decode_provider_response('["job-1", "job-2"]'),
            {"parsed_response": ["job-1", "job-2"]},
        )
        self.assertEqual(
            decode_provider_response('"job-12345"'),
            {"parsed_response": "job-12345"},
        )

    def test_generic_webhook_adapter_persists_plain_text_success(self):
        adapter = GenericWebhookAdapter("https://example.test/generate", "token", 30)
        package = build_scene_package(self.spec)

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b"job-12345"

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("generate_video_workflow.request.urlopen", return_value=FakeResponse()):
                result = adapter.run(package, Path(temp_dir))

            self.assertEqual(result["status"], "submitted")
            response_path = Path(result["response_payload"])
            self.assertEqual(
                load_scene_spec(response_path),
                {"raw_response": "job-12345"},
            )

    def test_generic_webhook_adapter_surfaces_http_error(self):
        adapter = GenericWebhookAdapter("https://example.test/generate", None, 30)
        package = build_scene_package(self.spec)
        http_error = error.HTTPError(
            url="https://example.test/generate",
            code=400,
            msg="Bad Request",
            hdrs=None,
            fp=io.BytesIO(b'{"error":"bad request"}'),
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("generate_video_workflow.request.urlopen", side_effect=http_error):
                with self.assertRaisesRegex(RuntimeError, "HTTP 400"):
                    adapter.run(package, Path(temp_dir))

    def test_generic_webhook_adapter_surfaces_url_error(self):
        adapter = GenericWebhookAdapter("https://example.test/generate", None, 30)
        package = build_scene_package(self.spec)

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch(
                "generate_video_workflow.request.urlopen",
                side_effect=error.URLError("connection refused"),
            ):
                with self.assertRaisesRegex(RuntimeError, "connection refused"):
                    adapter.run(package, Path(temp_dir))


if __name__ == "__main__":
    unittest.main()
