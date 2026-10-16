"""CLI checks that do not require Blender."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import batch_export_models as export_models


class ExportCliTests(unittest.TestCase):
    def test_missing_input_does_not_export(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(export_models, "export_models") as export:
                with self.assertRaisesRegex(ValueError, "existing .blend file"):
                    export_models.main([str(Path(directory) / "missing.blend")])
        export.assert_not_called()

    def test_blender_arguments_are_separated_from_script_arguments(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "my scene.blend"
            source.touch()
            output = Path(directory) / "my exports"
            argv = [
                "blender", "--background", "--python-exit-code", "1",
                "--python", "tools/batch_export_models.py", "--",
                str(source), str(output), "--format", "glb", "--selected-only",
            ]
            with patch.object(export_models.sys, "argv", argv):
                with patch.object(export_models, "export_models") as export:
                    export_models.main()
            args = export.call_args.args[0]
            self.assertEqual(args.blend_file, source.resolve())
            self.assertEqual(args.output_dir, output.resolve())
            self.assertEqual(args.format, "glb")
            self.assertTrue(args.selected_only)

    def test_default_destination_and_export_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "scene.blend"
            source.touch()
            with patch.object(export_models, "export_models") as export:
                export.side_effect = RuntimeError("Export failed")
                with self.assertRaisesRegex(RuntimeError, "Export failed"):
                    export_models.main([str(source)])
            args = export.call_args.args[0]
            self.assertEqual(args.output_dir, source.resolve().with_name("scene_exports"))
            self.assertEqual(args.format, "glb")
            self.assertFalse(args.selected_only)

    def test_export_path_is_flat_and_avoids_existing_buffers(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / "mesh_Cube.bin").touch()
            (output / "mesh_Cube_1.glb").touch()
            path = export_models.export_path(output, "Cube", "gltf")
            self.assertEqual(path, output / "mesh_Cube_2.gltf")
            self.assertFalse(any(child.is_dir() for child in output.iterdir()))

    def test_export_path_handles_sanitized_name_collisions(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            first = export_models.export_path(output, "Cube/A", "glb")
            first.touch()
            second = export_models.export_path(output, "cube:a", "glb")
            self.assertNotEqual(first.name.casefold(), second.name.casefold())
            self.assertEqual(second.parent, output)


if __name__ == "__main__":
    unittest.main()
