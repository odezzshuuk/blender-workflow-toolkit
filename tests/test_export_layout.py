"""Check grouped output paths and material-free exports without requiring Blender."""

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from script_loader import load_script

exporter = load_script("headless-scripts", "batch_export_models")
export_models, name_prefix = exporter.export_models, exporter.name_prefix


class ExportLayoutTests(unittest.TestCase):
    def test_prefixes_are_safe_and_have_a_fallback(self):
        for name, expected in (("character_body", "character"), ("Chair", "Chair"),
                               ("../body", "Object"), ("_body", "Object")):
            with self.subTest(name=name):
                self.assertEqual(name_prefix(name), expected)

    def test_export_uses_group_folder_and_collision_policy_for_both_formats(self):
        for file_format in ("gltf", "glb"):
            with self.subTest(file_format=file_format), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                model_dir = root / "models/character"
                model_dir.mkdir(parents=True)
                original = model_dir / f"character_body.{file_format}"
                original.write_text("original")
                obj = SimpleNamespace(type='MESH', name='character_body', visible_get=lambda: True,
                                      material_slots=[SimpleNamespace(material=object())], hide_select=False, select_set=Mock())
                class Objects(list):
                    active = obj
                class ViewLayer:
                    objects = Objects([obj])
                layer = ViewLayer()

                def write_export(**kwargs):
                    path = Path(kwargs['filepath'])
                    if file_format == "gltf":
                        path.write_text(json.dumps({'asset': {'version': '2.0'}}))
                    else:
                        path.write_bytes(b'glb')
                    return {'FINISHED'}

                bpy = SimpleNamespace(
                    types=SimpleNamespace(ViewLayer=ViewLayer),
                    context=SimpleNamespace(mode='OBJECT', view_layer=layer, selected_objects=[obj]),
                    ops=SimpleNamespace(wm=SimpleNamespace(open_mainfile=Mock()),
                                        export_scene=SimpleNamespace(gltf=Mock(side_effect=write_export))))
                args = SimpleNamespace(blend_file=Path('scene.blend'), output_dir=root,
                                       selected_only=False, format=file_format, on_exists='number')
                with patch.dict('sys.modules', {'bpy': bpy}), redirect_stdout(io.StringIO()):
                    export_models(args)
                self.assertTrue((model_dir / f'character_body_1.{file_format}').is_file())
                self.assertEqual(original.read_text(), 'original')
                self.assertFalse((root / 'meshes').exists())
                self.assertFalse((root / 'textures').exists())
                options = bpy.ops.export_scene.gltf.call_args.kwargs
                self.assertEqual(options['export_materials'], 'NONE')
                self.assertNotIn('export_texture_dir', options)
                self.assertIsNotNone(obj.material_slots[0].material)
                self.assertIs(layer.objects.active, obj)
                self.assertFalse(obj.hide_select)


if __name__ == '__main__':
    unittest.main()
