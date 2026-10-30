"""Check baked-image selection, collision handling, and save failure recovery."""

from contextlib import redirect_stdout
import io
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from script_loader import load_script

exporter = load_script("headless-scripts", "batch_export_images")


class ExportImageTests(unittest.TestCase):
    def test_safe_names_and_case_insensitive_collision_policies(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(exporter.image_path(root, '../Truck/Base Color', 'stop').parent, root)
            self.assertEqual(exporter.image_path(root, '', 'stop').name, 'Image.png')
            existing = root / 'Truck_BaseColor.PNG'
            existing.write_bytes(b'original')
            with self.assertRaises(exporter.ExportError):
                exporter.image_path(root, 'Truck_BaseColor', 'stop')
            self.assertEqual(exporter.image_path(root, 'truck_basecolor', 'overwrite'), existing)
            (root / 'Truck_BaseColor_1.png').mkdir()
            self.assertEqual(exporter.image_path(root, 'Truck_BaseColor', 'number').name,
                             'Truck_BaseColor_2.png')
            self.assertEqual(existing.read_bytes(), b'original')

    def test_save_restores_metadata_on_success_and_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'image.png'
            image = SimpleNamespace(name='Image', filepath_raw='//original.exr', file_format='OPEN_EXR')

            def save():
                self.assertEqual(image.file_format, 'PNG')
                self.assertEqual(image.filepath_raw, str(target))
                target.write_bytes(b'png')

            image.save = save
            exporter.save_image(image, target)
            self.assertEqual(image.filepath_raw, '//original.exr')
            self.assertEqual(image.file_format, 'OPEN_EXR')
            image.save = Mock(side_effect=RuntimeError('cannot save'))
            with self.assertRaisesRegex(exporter.ExportError, 'cannot save'):
                exporter.save_image(image, target)
            self.assertEqual(image.filepath_raw, '//original.exr')
            self.assertEqual(image.file_format, 'OPEN_EXR')

    def test_exports_only_recorded_images_and_deduplicates_shared_maps(self):
        class Image:
            def __init__(self, name):
                self.name = name

            def as_pointer(self):
                return id(self)

        class Object(dict):
            name = 'Object'

        shared = Image('Truck_BaseColor')
        other = Image('Other_Roughness')
        objects = [Object(bwt_bake_images={'BaseColor': shared}),
                   Object(bwt_bake_images={'BaseColor': shared, 'Roughness': other}), Object()]
        bpy = SimpleNamespace(
            ops=SimpleNamespace(wm=SimpleNamespace(open_mainfile=Mock())),
            types=SimpleNamespace(Image=Image), data=SimpleNamespace(objects=objects),
            context=SimpleNamespace(selected_objects=objects[:1]),
        )
        for selected_only, expected in ((False, [other, shared]), (True, [shared])):
            with self.subTest(selected_only=selected_only), tempfile.TemporaryDirectory() as directory:
                args = SimpleNamespace(blend_file=Path('scene.blend'), output_dir=Path(directory),
                                       selected_only=selected_only, on_exists='stop')
                with patch.dict('sys.modules', {'bpy': bpy}), patch.object(exporter, 'save_image') as save:
                    with redirect_stdout(io.StringIO()):
                        exporter.export_images(args)
                self.assertEqual([call.args[0] for call in save.call_args_list], expected)
        objects[0]['bwt_bake_images']['BaseColor'] = None
        with patch.dict('sys.modules', {'bpy': bpy}):
            with self.assertRaisesRegex(exporter.ExportError, 'Missing baked image'):
                exporter.export_images(args)

    def test_defaults_are_non_destructive(self):
        args = exporter.parse_args(['scene.blend'])
        self.assertEqual(args.on_exists, 'stop')
        self.assertIsNone(args.output_dir)
        self.assertFalse(args.selected_only)


if __name__ == '__main__':
    unittest.main()
