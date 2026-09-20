import json
import shutil
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
        outside = Path("/tmp/main-outside.json")
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


if __name__ == "__main__":
    unittest.main()
