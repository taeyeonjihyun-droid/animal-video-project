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
    RunwayAdapter,
    build_scene_package,
    build_shot_prompt,
    decode_provider_response,
    load_scene_spec,
    load_env_file,
    parse_env_value,
    parse_optional_runway_duration,
    parse_runway_duration,
    parse_timeout,
    resolve_runway_ratio,
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

    def test_parse_runway_duration_supports_auto_and_ints(self):
        self.assertEqual(parse_runway_duration("auto"), "auto")
        self.assertEqual(parse_runway_duration("6"), 6)
        with self.assertRaisesRegex(ValueError, "integer number of seconds"):
            parse_runway_duration("bad")
        with self.assertRaisesRegex(ValueError, "greater than 0"):
            parse_runway_duration("0")

    def test_parse_optional_runway_duration_supports_blank_override(self):
        self.assertIsNone(parse_optional_runway_duration(None))
        self.assertIsNone(parse_optional_runway_duration(""))
        self.assertEqual(parse_optional_runway_duration("auto"), "auto")

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

    @patch.dict("os.environ", {}, clear=True)
    def test_resolve_runway_ratio_uses_scene_aspect_ratio(self):
        package = build_scene_package(self.spec)
        self.assertEqual(resolve_runway_ratio(package), "1280:720")

    @patch.dict("os.environ", {"RUNWAY_RATIO": "720:1280"}, clear=True)
    def test_resolve_runway_ratio_prefers_env_override(self):
        package = build_scene_package(self.spec)
        self.assertEqual(resolve_runway_ratio(package), "720:1280")

    @patch.dict("os.environ", {}, clear=True)
    def test_resolve_runway_ratio_maps_supported_aspect_ratios(self):
        tall_package = build_scene_package({**self.spec, "aspect_ratio": "9:16"})
        square_package = build_scene_package({**self.spec, "aspect_ratio": "1:1"})
        self.assertEqual(resolve_runway_ratio(tall_package), "720:1280")
        self.assertEqual(resolve_runway_ratio(square_package), "960:960")

    def test_parse_env_value_supports_quotes_and_inline_comments(self):
        self.assertEqual(parse_env_value(" plain "), "plain")
        self.assertEqual(parse_env_value('"quoted value"'), "quoted value")
        self.assertEqual(parse_env_value("value # comment"), "value")

    @patch.dict("os.environ", {}, clear=True)
    def test_load_env_file_with_blank_runway_ratio_keeps_scene_mapping(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text("RUNWAY_RATIO=\n", encoding="utf-8")
            load_env_file(env_path)
            package = build_scene_package({**self.spec, "aspect_ratio": "9:16"})
            self.assertEqual(resolve_runway_ratio(package), "720:1280")

    def test_runway_adapter_submits_all_shots(self):
        package = build_scene_package(self.spec)

        class FakeTask:
            def __init__(self, task_id):
                self.id = task_id

            def model_dump(self):
                return {"id": self.id, "status": "queued"}

        class FakeTextToVideo:
            def __init__(self):
                self.calls = []

            def create(self, **kwargs):
                self.calls.append(kwargs)
                return FakeTask(f"task-{len(self.calls)}")

        class FakeClient:
            def __init__(self, api_key):
                self.api_key = api_key
                self.text_to_video = FakeTextToVideo()

        created_clients = []

        def factory(api_key):
            client = FakeClient(api_key)
            created_clients.append(client)
            return client

        adapter = RunwayAdapter(
            api_key="secret",
            model="gen4_turbo",
            generation_mode="text_to_video",
            duration=None,
            prompt_image=None,
            client_factory=factory,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            result = adapter.run(package, Path(temp_dir))
            self.assertEqual(result["status"], "submitted")
            response_payload = load_scene_spec(Path(result["response_payload"]))

        self.assertEqual(len(response_payload["tasks"]), 4)
        self.assertEqual(created_clients[0].api_key, "secret")
        self.assertEqual(len(created_clients[0].text_to_video.calls), 4)
        self.assertEqual(created_clients[0].text_to_video.calls[0]["model"], "gen4_turbo")
        self.assertEqual(created_clients[0].text_to_video.calls[0]["duration"], 4)
        self.assertEqual(created_clients[0].text_to_video.calls[-1]["duration"], 3)

    def test_runway_adapter_honors_explicit_duration_override(self):
        package = build_scene_package(self.spec)

        class FakeTask:
            def __init__(self, task_id):
                self.id = task_id

        class FakeTextToVideo:
            def __init__(self):
                self.calls = []

            def create(self, **kwargs):
                self.calls.append(kwargs)
                return FakeTask(f"task-{len(self.calls)}")

        class FakeClient:
            def __init__(self, api_key):
                self.api_key = api_key
                self.text_to_video = FakeTextToVideo()

        created_clients = []

        def factory(api_key):
            client = FakeClient(api_key)
            created_clients.append(client)
            return client

        adapter = RunwayAdapter(
            api_key="secret",
            model="gen4_turbo",
            generation_mode="text_to_video",
            duration="auto",
            prompt_image=None,
            client_factory=factory,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            adapter.run(package, Path(temp_dir))

        self.assertEqual(created_clients[0].text_to_video.calls[0]["duration"], "auto")

    def test_runway_adapter_requires_prompt_image_for_image_mode(self):
        package = build_scene_package(self.spec)

        class FakeClient:
            def __init__(self, api_key):
                self.image_to_video = object()

        adapter = RunwayAdapter(
            api_key="secret",
            model="gen4_turbo",
            generation_mode="image_to_video",
            duration="auto",
            prompt_image=None,
            client_factory=lambda api_key: FakeClient(api_key),
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(ValueError, "RUNWAY_PROMPT_IMAGE is required"):
                adapter.run(package, Path(temp_dir))

    def test_runway_adapter_rejects_invalid_generation_mode(self):
        with self.assertRaisesRegex(ValueError, "RUNWAY_GENERATION_MODE must be"):
            RunwayAdapter(
                api_key="secret",
                model="gen4_turbo",
                generation_mode="bad-mode",
                duration="auto",
                prompt_image=None,
                client_factory=lambda api_key: None,
            )

    def test_runway_adapter_wraps_submission_errors(self):
        package = build_scene_package(self.spec)

        class FakeTextToVideo:
            def create(self, **kwargs):
                raise RuntimeError("boom")

        class FakeClient:
            def __init__(self, api_key):
                self.text_to_video = FakeTextToVideo()

        adapter = RunwayAdapter(
            api_key="secret",
            model="gen4_turbo",
            generation_mode="text_to_video",
            duration="auto",
            prompt_image=None,
            client_factory=lambda api_key: FakeClient(api_key),
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(RuntimeError, "Runway submission failed for shot shot_01"):
                adapter.run(package, Path(temp_dir))


if __name__ == "__main__":
    unittest.main()
