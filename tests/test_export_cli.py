"""CLI checks that do not require Blender."""

import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import export_models


class ExportCliTests(unittest.TestCase):
    def test_missing_input_does_not_launch_blender(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(export_models.subprocess, "run") as run:
                with contextlib.redirect_stderr(io.StringIO()):
                    result = export_models.main([str(Path(directory) / "missing.blend")])
        self.assertEqual(result, 2)
        run.assert_not_called()

    def test_paths_options_and_failure_exit_code_are_forwarded(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "my scene.blend"
            source.touch()
            output = Path(directory) / "my exports"
            with patch.object(export_models.shutil, "which", return_value="/opt/Blender App/blender"):
                with patch.object(export_models.subprocess, "run") as run:
                    run.return_value.returncode = 7
                    result = export_models.main([
                        str(source), str(output), "--format", "glb", "--selected-only",
                    ])
            command = run.call_args.args[0]
            self.assertEqual(command[0], "/opt/Blender App/blender")
            self.assertEqual(command[command.index("--") + 1:], [
                "--bwt-worker", str(source.resolve()), str(output.resolve()),
                "--format", "glb", "--selected-only",
            ])
            self.assertEqual(result, 7)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
