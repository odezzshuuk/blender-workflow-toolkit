"""Expected user conditions are concise; unexpected code failures remain visible."""

from contextlib import redirect_stderr, redirect_stdout
import io
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from script_loader import load_script

exporter = load_script("headless-scripts", "batch_export_models")
ExportError, export_models, main = exporter.ExportError, exporter.export_models, exporter.main


class ExportMessageTests(unittest.TestCase):
    def test_empty_selection_and_no_visible_meshes_are_normal_outcomes(self):
        class ViewLayer:
            objects = SimpleNamespace(active=None)

        layer = ViewLayer()
        light = SimpleNamespace(type='LIGHT', name='Light', visible_get=lambda: True)
        hidden_mesh = SimpleNamespace(type='MESH', name='Hidden', visible_get=lambda: False)
        for selection, expected in (
            ([], "no saved selection"),
            ([light], "saved selection contains no visible meshes"),
            ([hidden_mesh], "saved selection contains no visible meshes"),
        ):
            with self.subTest(selection=selection):
                bpy = SimpleNamespace(
                    ops=SimpleNamespace(wm=SimpleNamespace(open_mainfile=Mock())),
                    context=SimpleNamespace(mode='OBJECT', view_layer=layer, selected_objects=selection),
                    types=SimpleNamespace(ViewLayer=ViewLayer),
                )
                output = io.StringIO()
                with patch.dict('sys.modules', {'bpy': bpy}), redirect_stdout(output):
                    export_models(SimpleNamespace(blend_file=Path('scene.blend'), selected_only=True))
                self.assertIn(expected, output.getvalue())

        bpy.context.selected_objects = []
        layer.objects = type('Objects', (list,), {'active': None})()
        with patch.dict('sys.modules', {'bpy': bpy}), redirect_stdout(io.StringIO()) as output:
            export_models(SimpleNamespace(blend_file=Path('scene.blend'), selected_only=False))
        self.assertIn('no visible meshes in the active view layer', output.getvalue())

    def test_missing_file_prints_message_and_returns_usage_status(self):
        with tempfile.TemporaryDirectory() as directory:
            with redirect_stderr(io.StringIO()) as output:
                status = main([str(Path(directory) / 'missing.blend')])
        self.assertEqual(status, 2)
        self.assertIn('Expected an existing .blend file', output.getvalue())
        self.assertNotIn('Traceback', output.getvalue())

    def test_expected_failures_have_concise_messages_and_nonzero_status(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'scene.blend'
            source.touch()
            for error in (PermissionError('Permission denied'), ExportError('Cannot export mesh')):
                with self.subTest(error=error):
                    with patch('batch_export_models.export_models', side_effect=error):
                        with redirect_stderr(io.StringIO()) as output:
                            self.assertEqual(main([str(source)]), 1)
                    self.assertIn(str(error), output.getvalue())
                    self.assertNotIn('Traceback', output.getvalue())

    def test_unexpected_programming_errors_are_not_suppressed(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'scene.blend'
            source.touch()
            with patch('batch_export_models.export_models', side_effect=AttributeError('bug')):
                with self.assertRaises(AttributeError):
                    main([str(source)])


if __name__ == '__main__':
    unittest.main()
