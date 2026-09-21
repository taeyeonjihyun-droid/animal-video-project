import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import main


class BatchFeatureTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = main.ROOT / "tmp_test_batch"
        self.tmp_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _write_json(self, path: Path, payload):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def test_resolve_repo_path_allows_absolute_inside_repo(self):
        config_path = (main.ROOT / "config.json").resolve()
        resolved = main.resolve_repo_relative_path(
            str(config_path),
            base_dir=Path.cwd(),
            must_exist=True,
        )
        self.assertEqual(resolved, config_path)

    def test_resolve_repo_path_rejects_absolute_outside_repo(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            outside = Path(tmp_dir) / "main-outside.json"
            outside.write_text("{}", encoding="utf-8")
            with self.assertRaises(ValueError):
                main.resolve_repo_relative_path(
                    str(outside),
                    base_dir=Path.cwd(),
                    must_exist=True,
                )

    def test_batch_config_path_is_relative_to_batch_file(self):
        batch_dir = self.tmp_dir / "nested"
        cfg_path = batch_dir / "episode.json"
        batch_path = batch_dir / "batch.json"
        self._write_json(
            cfg_path,
            {
                "project_title": "테스트",
                "subtitle": "테스트",
                "video": {"width": 320, "height": 180, "fps": 12, "fade_seconds": 0.1},
                "output": "output/test.mp4",
                "scenes": [{"source": "assets/images/x.png", "caption": "x", "duration": 0.3, "zoom": 1.0}],
            },
        )
        self._write_json(
            batch_path,
            {"jobs": [{"name": "ep1", "config": "episode.json", "overrides": {"video": {"fps": 10}}}]},
        )

        rel_batch_path = batch_path.relative_to(main.ROOT).as_posix()
        with patch("main.build_video_from_config") as mocked_build:
            main.build_batch_videos(rel_batch_path)

        self.assertEqual(mocked_build.call_count, 1)
        rendered_cfg = mocked_build.call_args.args[0]
        self.assertEqual(rendered_cfg["video"]["fps"], 10)
        self.assertEqual(rendered_cfg["video"]["width"], 320)

    def test_invalid_overrides_type_is_rejected_even_when_empty(self):
        batch_dir = self.tmp_dir / "shape"
        cfg_path = batch_dir / "episode.json"
        batch_path = batch_dir / "batch_bad.json"
        self._write_json(
            cfg_path,
            {
                "project_title": "테스트",
                "subtitle": "테스트",
                "video": {"width": 320, "height": 180, "fps": 12, "fade_seconds": 0.1},
                "output": "output/test.mp4",
                "scenes": [{"source": "assets/images/x.png", "caption": "x", "duration": 0.3, "zoom": 1.0}],
            },
        )
        self._write_json(
            batch_path,
            {"jobs": [{"config": "episode.json", "overrides": []}]},
        )

        rel_batch_path = batch_path.relative_to(main.ROOT).as_posix()
        with self.assertRaises(ValueError):
            main.build_batch_videos(rel_batch_path)

    def test_batch_jobs_without_output_override_get_unique_outputs(self):
        batch_dir = self.tmp_dir / "multi"
        cfg_path = batch_dir / "episode.json"
        batch_path = batch_dir / "batch.json"
        self._write_json(
            cfg_path,
            {
                "project_title": "테스트",
                "subtitle": "테스트",
                "video": {"width": 320, "height": 180, "fps": 12, "fade_seconds": 0.1},
                "output": "output/test.mp4",
                "scenes": [{"source": "assets/images/x.png", "caption": "x", "duration": 0.3, "zoom": 1.0}],
            },
        )
        self._write_json(
            batch_path,
            {
                "jobs": [
                    {"name": "ep1", "config": "episode.json"},
                    {"name": "ep2", "config": "episode.json"},
                ]
            },
        )

        rel_batch_path = batch_path.relative_to(main.ROOT).as_posix()
        with patch("main.build_video_from_config") as mocked_build:
            main.build_batch_videos(rel_batch_path)

        self.assertEqual(mocked_build.call_count, 2)
        first_output = mocked_build.call_args_list[0].args[0]["output"]
        second_output = mocked_build.call_args_list[1].args[0]["output"]
        expected_first = Path("output/test.mp4")
        expected_second = Path("output/test_02.mp4")
        self.assertEqual(Path(first_output), expected_first)
        self.assertEqual(Path(second_output), expected_second)

    def test_explicit_output_override_is_preserved(self):
        batch_dir = self.tmp_dir / "explicit"
        cfg_path = batch_dir / "episode.json"
        batch_path = batch_dir / "batch.json"
        self._write_json(
            cfg_path,
            {
                "project_title": "테스트",
                "subtitle": "테스트",
                "video": {"width": 320, "height": 180, "fps": 12, "fade_seconds": 0.1},
                "output": "output/test.mp4",
                "scenes": [{"source": "assets/images/x.png", "caption": "x", "duration": 0.3, "zoom": 1.0}],
            },
        )
        self._write_json(
            batch_path,
            {
                "jobs": [
                    {"name": "ep1", "config": "episode.json", "overrides": {"output": "output/test.mp4"}},
                    {"name": "ep2", "config": "episode.json"},
                ]
            },
        )

        rel_batch_path = batch_path.relative_to(main.ROOT).as_posix()
        with patch("main.build_video_from_config") as mocked_build:
            main.build_batch_videos(rel_batch_path)

        self.assertEqual(mocked_build.call_count, 2)
        first_output = mocked_build.call_args_list[0].args[0]["output"]
        second_output = mocked_build.call_args_list[1].args[0]["output"]
        expected_first = Path("output/test.mp4")
        expected_second = Path("output/test_02.mp4")
        self.assertEqual(Path(first_output), expected_first)
        self.assertEqual(Path(second_output), expected_second)

    def test_duplicate_explicit_outputs_are_renamed_for_uniqueness(self):
        batch_dir = self.tmp_dir / "explicit-dup"
        cfg_path = batch_dir / "episode.json"
        batch_path = batch_dir / "batch.json"
        self._write_json(
            cfg_path,
            {
                "project_title": "테스트",
                "subtitle": "테스트",
                "video": {"width": 320, "height": 180, "fps": 12, "fade_seconds": 0.1},
                "output": "output/test.mp4",
                "scenes": [{"source": "assets/images/x.png", "caption": "x", "duration": 0.3, "zoom": 1.0}],
            },
        )
        self._write_json(
            batch_path,
            {
                "jobs": [
                    {"name": "ep1", "config": "episode.json", "overrides": {"output": "output/same.mp4"}},
                    {"name": "ep2", "config": "episode.json", "overrides": {"output": "output/same.mp4"}},
                ]
            },
        )

        rel_batch_path = batch_path.relative_to(main.ROOT).as_posix()
        with patch("main.build_video_from_config") as mocked_build:
            main.build_batch_videos(rel_batch_path)

        self.assertEqual(mocked_build.call_count, 2)
        first_output = mocked_build.call_args_list[0].args[0]["output"]
        second_output = mocked_build.call_args_list[1].args[0]["output"]
        expected_first = Path("output/same.mp4")
        expected_second = Path("output/same_02.mp4")
        self.assertEqual(Path(first_output), expected_first)
        self.assertEqual(Path(second_output), expected_second)

    def test_invalid_output_type_is_rejected(self):
        batch_dir = self.tmp_dir / "bad-output"
        cfg_path = batch_dir / "episode.json"
        batch_path = batch_dir / "batch.json"
        self._write_json(
            cfg_path,
            {
                "project_title": "테스트",
                "subtitle": "테스트",
                "video": {"width": 320, "height": 180, "fps": 12, "fade_seconds": 0.1},
                "output": None,
                "scenes": [{"source": "assets/images/x.png", "caption": "x", "duration": 0.3, "zoom": 1.0}],
            },
        )
        self._write_json(batch_path, {"jobs": [{"config": "episode.json"}]})

        rel_batch_path = batch_path.relative_to(main.ROOT).as_posix()
        with self.assertRaises(ValueError):
            main.build_batch_videos(rel_batch_path)

    def test_whitespace_output_string_is_rejected(self):
        batch_dir = self.tmp_dir / "bad-output-space"
        cfg_path = batch_dir / "episode.json"
        batch_path = batch_dir / "batch.json"
        self._write_json(
            cfg_path,
            {
                "project_title": "테스트",
                "subtitle": "테스트",
                "video": {"width": 320, "height": 180, "fps": 12, "fade_seconds": 0.1},
                "output": "   ",
                "scenes": [{"source": "assets/images/x.png", "caption": "x", "duration": 0.3, "zoom": 1.0}],
            },
        )
        self._write_json(batch_path, {"jobs": [{"config": "episode.json"}]})

        rel_batch_path = batch_path.relative_to(main.ROOT).as_posix()
        with self.assertRaises(ValueError):
            main.build_batch_videos(rel_batch_path)

    def test_non_mp4_output_is_rejected(self):
        batch_dir = self.tmp_dir / "bad-output-ext"
        cfg_path = batch_dir / "episode.json"
        batch_path = batch_dir / "batch.json"
        self._write_json(
            cfg_path,
            {
                "project_title": "테스트",
                "subtitle": "테스트",
                "video": {"width": 320, "height": 180, "fps": 12, "fade_seconds": 0.1},
                "output": "output/test.mov",
                "scenes": [{"source": "assets/images/x.png", "caption": "x", "duration": 0.3, "zoom": 1.0}],
            },
        )
        self._write_json(batch_path, {"jobs": [{"config": "episode.json"}]})

        rel_batch_path = batch_path.relative_to(main.ROOT).as_posix()
        with self.assertRaises(ValueError):
            main.build_batch_videos(rel_batch_path)

    def test_existing_output_file_gets_suffix_to_avoid_overwrite(self):
        batch_dir = self.tmp_dir / "existing-output"
        cfg_path = batch_dir / "episode.json"
        batch_path = batch_dir / "batch.json"
        existing_output = batch_dir / "output" / "test.mp4"
        existing_output.parent.mkdir(parents=True, exist_ok=True)
        existing_output.write_text("existing", encoding="utf-8")
        self._write_json(
            cfg_path,
            {
                "project_title": "테스트",
                "subtitle": "테스트",
                "video": {"width": 320, "height": 180, "fps": 12, "fade_seconds": 0.1},
                "output": "output/test.mp4",
                "scenes": [{"source": "assets/images/x.png", "caption": "x", "duration": 0.3, "zoom": 1.0}],
            },
        )
        self._write_json(batch_path, {"jobs": [{"config": "episode.json"}]})

        rel_batch_path = batch_path.relative_to(main.ROOT).as_posix()
        with patch("main.build_video_from_config") as mocked_build:
            main.build_batch_videos(rel_batch_path)

        rendered_cfg = mocked_build.call_args.args[0]
        self.assertEqual(Path(rendered_cfg["output"]), Path("output/test_02.mp4"))

    def test_nested_config_relative_output_is_resolved_from_config_dir(self):
        batch_dir = self.tmp_dir / "nested-output"
        cfg_path = batch_dir / "episode.json"
        batch_path = batch_dir / "batch.json"
        self._write_json(
            cfg_path,
            {
                "project_title": "테스트",
                "subtitle": "테스트",
                "video": {"width": 320, "height": 180, "fps": 12, "fade_seconds": 0.1},
                "output": "local.mp4",
                "scenes": [{"source": "assets/images/x.png", "caption": "x", "duration": 0.3, "zoom": 1.0}],
            },
        )
        self._write_json(batch_path, {"jobs": [{"config": "episode.json"}]})

        rel_batch_path = batch_path.relative_to(main.ROOT).as_posix()
        with patch("main.build_video_from_config") as mocked_build:
            main.build_batch_videos(rel_batch_path)

        rendered_cfg = mocked_build.call_args.args[0]
        expected = Path("local.mp4")
        self.assertEqual(Path(rendered_cfg["output"]), expected)
        expected_output_path = (batch_dir / "local.mp4").resolve()
        self.assertEqual(mocked_build.call_args.kwargs["output_path"], expected_output_path)
        self.assertEqual(
            mocked_build.call_args.kwargs["output_base_dir"],
            batch_dir.resolve(),
        )

    def test_batch_prompt_generation_calls_each_job_with_unique_outputs(self):
        batch_dir = self.tmp_dir / "batch-prompts"
        cfg_path = batch_dir / "episode.json"
        batch_path = batch_dir / "batch.json"
        self._write_json(
            cfg_path,
            {
                "project_title": "테스트",
                "subtitle": "테스트",
                "video": {"width": 320, "height": 180, "fps": 12, "fade_seconds": 0.1},
                "image_prompt_output": "output/prompts.json",
                "scenes": [{"source": "assets/images/x.png", "caption": "x", "duration": 0.3, "zoom": 1.0}],
            },
        )
        self._write_json(
            batch_path,
            {"jobs": [{"config": "episode.json"}, {"config": "episode.json"}]},
        )

        rel_batch_path = batch_path.relative_to(main.ROOT).as_posix()
        with patch("main.generate_image_prompts_from_config") as mocked_prompts:
            main.build_batch_image_prompts(rel_batch_path)

        self.assertEqual(mocked_prompts.call_count, 2)
        first_output = mocked_prompts.call_args_list[0].kwargs["output_override"]
        second_output = mocked_prompts.call_args_list[1].kwargs["output_override"]
        self.assertEqual(Path(first_output).name, "prompts.json")
        self.assertEqual(Path(second_output).name, "prompts_02.json")

    def test_batch_prompt_output_extension_must_be_json(self):
        batch_dir = self.tmp_dir / "batch-prompts-bad-ext"
        cfg_path = batch_dir / "episode.json"
        batch_path = batch_dir / "batch.json"
        self._write_json(
            cfg_path,
            {
                "project_title": "테스트",
                "subtitle": "테스트",
                "video": {"width": 320, "height": 180, "fps": 12, "fade_seconds": 0.1},
                "image_prompt_output": "output/prompts.txt",
                "scenes": [{"source": "assets/images/x.png", "caption": "x", "duration": 0.3, "zoom": 1.0}],
            },
        )
        self._write_json(batch_path, {"jobs": [{"config": "episode.json"}]})

        rel_batch_path = batch_path.relative_to(main.ROOT).as_posix()
        with self.assertRaises(ValueError):
            main.build_batch_image_prompts(rel_batch_path)

    def test_batch_prompt_filename_pattern_is_applied(self):
        batch_dir = self.tmp_dir / "batch-prompts-pattern"
        cfg_path = batch_dir / "episode.json"
        batch_path = batch_dir / "batch.json"
        self._write_json(
            cfg_path,
            {
                "project_title": "테스트",
                "subtitle": "테스트",
                "video": {"width": 320, "height": 180, "fps": 12, "fade_seconds": 0.1},
                "image_prompt_output": "output/prompts.json",
                "scenes": [{"source": "assets/images/x.png", "caption": "x", "duration": 0.3, "zoom": 1.0}],
            },
        )
        self._write_json(
            batch_path,
            {
                "prompt_filename_pattern": "{index2}_{job_slug}_{config}",
                "jobs": [{"name": "Episode 01!", "config": "episode.json"}],
            },
        )

        rel_batch_path = batch_path.relative_to(main.ROOT).as_posix()
        with patch("main.generate_image_prompts_from_config") as mocked_prompts:
            main.build_batch_image_prompts(rel_batch_path)

        output_override = mocked_prompts.call_args.kwargs["output_override"]
        self.assertEqual(Path(output_override).name, "01_Episode_01_episode.json")

    def test_batch_prompt_filename_pattern_invalid_placeholder_is_rejected(self):
        batch_dir = self.tmp_dir / "batch-prompts-pattern-invalid"
        cfg_path = batch_dir / "episode.json"
        batch_path = batch_dir / "batch.json"
        self._write_json(
            cfg_path,
            {
                "project_title": "테스트",
                "subtitle": "테스트",
                "video": {"width": 320, "height": 180, "fps": 12, "fade_seconds": 0.1},
                "image_prompt_output": "output/prompts.json",
                "scenes": [{"source": "assets/images/x.png", "caption": "x", "duration": 0.3, "zoom": 1.0}],
            },
        )
        self._write_json(
            batch_path,
            {"prompt_filename_pattern": "{unknown}", "jobs": [{"config": "episode.json"}]},
        )

        rel_batch_path = batch_path.relative_to(main.ROOT).as_posix()
        with self.assertRaises(ValueError):
            main.build_batch_image_prompts(rel_batch_path)

    def test_batch_render_retries_failed_job(self):
        batch_dir = self.tmp_dir / "batch-retry-render"
        cfg_path = batch_dir / "episode.json"
        batch_path = batch_dir / "batch.json"
        self._write_json(
            cfg_path,
            {
                "project_title": "테스트",
                "subtitle": "테스트",
                "video": {"width": 320, "height": 180, "fps": 12, "fade_seconds": 0.1},
                "output": "output/test.mp4",
                "scenes": [{"source": "assets/images/x.png", "caption": "x", "duration": 0.3, "zoom": 1.0}],
            },
        )
        self._write_json(batch_path, {"jobs": [{"config": "episode.json"}]})

        rel_batch_path = batch_path.relative_to(main.ROOT).as_posix()
        with patch("main.build_video_from_config") as mocked_build:
            mocked_build.side_effect = [RuntimeError("first fail"), None]
            main.build_batch_videos(rel_batch_path, retry_failed=1)

        self.assertEqual(mocked_build.call_count, 2)

    def test_batch_prompts_retries_failed_job(self):
        batch_dir = self.tmp_dir / "batch-retry-prompts"
        cfg_path = batch_dir / "episode.json"
        batch_path = batch_dir / "batch.json"
        self._write_json(
            cfg_path,
            {
                "project_title": "테스트",
                "subtitle": "테스트",
                "video": {"width": 320, "height": 180, "fps": 12, "fade_seconds": 0.1},
                "image_prompt_output": "output/prompts.json",
                "scenes": [{"source": "assets/images/x.png", "caption": "x", "duration": 0.3, "zoom": 1.0}],
            },
        )
        self._write_json(batch_path, {"jobs": [{"config": "episode.json"}]})

        rel_batch_path = batch_path.relative_to(main.ROOT).as_posix()
        with patch("main.generate_image_prompts_from_config") as mocked_prompts:
            mocked_prompts.side_effect = [RuntimeError("first fail"), None]
            main.build_batch_image_prompts(rel_batch_path, retry_failed=1)

        self.assertEqual(mocked_prompts.call_count, 2)


if __name__ == "__main__":
    unittest.main()
