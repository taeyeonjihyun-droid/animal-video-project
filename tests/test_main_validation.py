import unittest
from PIL import Image, ImageDraw

from main import validate_config, wrap_text, load_font


class MainValidationTests(unittest.TestCase):
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

    def test_wrap_text_handles_korean_without_spaces(self):
        image = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        font = load_font(48)
        text = "고양이와아기오리가비오는길을함께달려요"
        lines = wrap_text(draw, text, font=font, max_width=300, stroke_width=2, max_lines=3)
        self.assertGreaterEqual(len(lines), 2)
        self.assertTrue(all(lines))


if __name__ == "__main__":
    unittest.main()
