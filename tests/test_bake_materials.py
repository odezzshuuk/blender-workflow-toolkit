"""Session baking validation and image naming without requiring Blender."""

import unittest
from script_loader import load_script

baker = load_script("src", "texture_baking")
BakeError, bake_current_scene, image_names = baker.BakeError, baker.bake_current_scene, baker.image_names


class BakeMaterialTests(unittest.TestCase):
    def test_stable_target_names(self):
        maps = ('BaseColor', 'Normal')
        names = image_names('character_body', maps)
        self.assertEqual(names['BaseColor'], 'character_body_BaseColor')
        self.assertEqual(names['Normal'], 'character_body_Normal')
        self.assertEqual(image_names('character_body', maps), names)

    def test_sanitized_object_names_keep_map_suffix(self):
        self.assertEqual(image_names('body.001', ('Normal',)), {'Normal': 'body_001_Normal'})
        self.assertEqual(image_names('', ('Normal',)), {'Normal': 'Object_Normal'})

    def test_invalid_settings_fail_before_accessing_blender(self):
        for settings in ({'size': 0}, {'samples': -1}, {'margin': -1}, {'size': 1.5},
                         {'maps': []}, {'maps': ['Unknown']}, {'maps': 'Normal'}):
            with self.subTest(settings=settings), self.assertRaises(BakeError):
                bake_current_scene(**settings)


if __name__ == '__main__':
    unittest.main()
