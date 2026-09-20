import unittest
from pathlib import Path

from generate_video_workflow import (
    DEFAULT_SCENE_SPEC,
    build_scene_package,
    build_shot_prompt,
    load_scene_spec,
    validate_scene_spec,
)


class GenerateVideoWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = load_scene_spec(Path(DEFAULT_SCENE_SPEC))

    def test_scene_spec_is_valid(self):
        validate_scene_spec(self.spec)

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


if __name__ == "__main__":
    unittest.main()
