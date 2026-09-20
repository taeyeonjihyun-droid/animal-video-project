import unittest
from PIL import Image, ImageDraw

from main import validate_config, wrap_text, load_font


class MainValidationTests(unittest.TestCase):
    def test_validate_config_rejects_non_object_root(self):
        with self.assertRaisesRegex(ValueError, "JSON 객체 형태여야 합니다"):
            validate_config([])

    def test_validate_config_rejects_missing_video(self):
        cfg = {"scenes": [{"source": "assets/images/x.png", "duration": 4.0}]}
        with self.assertRaisesRegex(ValueError, "`video` 설정이 없습니다"):
            validate_config(cfg)

    def test_validate_config_rejects_non_positive_video_numbers(self):
        cfg = {
            "video": {"width": 0, "height": 1920, "fps": 30},
            "scenes": [{"source": "assets/images/x.png", "duration": 4.0}],
        }
        with self.assertRaisesRegex(ValueError, "영상 크기\\(width/height\\)는 1 이상의 정수여야 합니다"):
            validate_config(cfg)

    def test_validate_config_rejects_empty_scenes(self):
        cfg = {
            "video": {"width": 1080, "height": 1920, "fps": 30},
            "scenes": [],
        }
        with self.assertRaisesRegex(ValueError, "`scenes`가 비어 있습니다"):
            validate_config(cfg)

    def test_validate_config_rejects_invalid_duration(self):
        cfg = {
            "video": {"width": 1080, "height": 1920, "fps": 30},
            "scenes": [{"source": "assets/images/x.png", "duration": 0}],
        }
        with self.assertRaisesRegex(ValueError, "duration은 0보다 커야 합니다"):
            validate_config(cfg)

    def test_validate_config_rejects_non_numeric_video_values(self):
        cfg = {
            "video": {"width": "wide", "height": 1920, "fps": 30},
            "scenes": [{"source": "assets/images/x.png", "duration": 4.0}],
        }
        with self.assertRaisesRegex(ValueError, "video.width, video.height, video.fps는 숫자여야 합니다"):
            validate_config(cfg)

    def test_validate_config_rejects_non_numeric_scene_values(self):
        cfg = {
            "video": {"width": 1080, "height": 1920, "fps": 30},
            "scenes": [{"source": "assets/images/x.png", "duration": "fast", "zoom": 1.0}],
        }
        with self.assertRaisesRegex(ValueError, "duration은 숫자여야 합니다"):
            validate_config(cfg)

    def test_validate_config_rejects_bad_scene_shape_or_missing_source(self):
        cfg_bad_shape = {"video": {"width": 1080, "height": 1920, "fps": 30}, "scenes": ["bad"]}
        with self.assertRaisesRegex(ValueError, "장면 형식이 잘못되었습니다"):
            validate_config(cfg_bad_shape)

        cfg_missing_source = {"video": {"width": 1080, "height": 1920, "fps": 30}, "scenes": [{}]}
        with self.assertRaisesRegex(ValueError, "`source`가 없습니다"):
            validate_config(cfg_missing_source)

    def test_validate_config_rejects_non_positive_zoom(self):
        cfg = {
            "video": {"width": 1080, "height": 1920, "fps": 30},
            "scenes": [{"source": "assets/images/x.png", "duration": 4.0, "zoom": 0}],
        }
        with self.assertRaisesRegex(ValueError, "zoom은 0보다 커야 합니다"):
            validate_config(cfg)

    def test_wrap_text_handles_korean_without_spaces(self):
        image = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        font = load_font(48)
        text = "고양이와아기오리가비오는길을함께달려요"
        lines = wrap_text(draw, text, font=font, max_width=300, stroke_width=2, max_lines=3)
        self.assertGreaterEqual(len(lines), 2)
        self.assertTrue(all(lines))
        for line in lines:
            line_width = draw.textbbox((0, 0), line, font=font, stroke_width=2)[2]
            self.assertLessEqual(line_width, 300)

    def test_wrap_text_truncates_with_ellipsis(self):
        image = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        font = load_font(40)
        max_width = 260
        text = "아기오리와고양이가함께걷고또걷고계속걷다가드디어집을찾았어요"
        lines = wrap_text(draw, text, font=font, max_width=max_width, stroke_width=2, max_lines=2)
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[-1].endswith("…"))
        last_width = draw.textbbox((0, 0), lines[-1], font=font, stroke_width=2)[2]
        self.assertLessEqual(last_width, max_width)


if __name__ == "__main__":
    unittest.main()
