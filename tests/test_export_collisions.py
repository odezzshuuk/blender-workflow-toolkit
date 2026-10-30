"""Collision prompts can be tested without running Blender."""

from contextlib import redirect_stdout
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from script_loader import load_script

exporter = load_script("headless-scripts", "batch_export_models")
export_path, parse_args = exporter.export_path, exporter.parse_args


class ExportCollisionTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.output = Path(directory.name)
        self.original = self.output / "Cube.glb"
        self.original.write_bytes(b"original")
        output = redirect_stdout(io.StringIO())
        output.__enter__()
        self.addCleanup(output.__exit__, None, None, None)

    def test_new_name_does_not_prompt(self):
        with patch("builtins.input") as prompt:
            self.assertEqual(export_path(self.output, "Sphere", "glb"), self.output / "Sphere.glb")
        prompt.assert_not_called()

    def test_overwrite_reuses_original_path_without_modifying_it_yet(self):
        with patch("builtins.input", return_value="1"):
            self.assertEqual(export_path(self.output, "Cube", "glb"), self.original)
        self.assertEqual(self.original.read_bytes(), b"original")

    def test_numbered_copy_skips_existing_names_and_buffers(self):
        (self.output / "Cube_1.bin").touch()
        with patch("builtins.input", return_value="2"):
            path = export_path(self.output, "Cube", "glb")
        self.assertEqual(path, self.output / "Cube_2.glb")
        self.assertEqual(self.original.read_bytes(), b"original")

    def test_stop_returns_no_destination(self):
        with patch("builtins.input", return_value="3"):
            self.assertIsNone(export_path(self.output, "Cube", "glb"))

    def test_invalid_choice_reprompts(self):
        with patch("builtins.input", side_effect=["invalid", "", "1"]) as prompt:
            self.assertEqual(export_path(self.output, "Cube", "glb"), self.original)
        self.assertEqual(prompt.call_count, 3)

    def test_no_input_stops_without_overwriting(self):
        for error in (EOFError, KeyboardInterrupt):
            with self.subTest(error=error):
                with patch("builtins.input", side_effect=error):
                    self.assertIsNone(export_path(self.output, "Cube", "glb"))
        self.assertEqual(self.original.read_bytes(), b"original")

    def test_case_insensitive_conflict_reuses_existing_filename(self):
        with patch("builtins.input", return_value="1"):
            self.assertEqual(export_path(self.output, "cube", "glb"), self.original)

    def test_explicit_policies_never_prompt(self):
        for policy, expected in (
            ("overwrite", self.original),
            ("number", self.output / "Cube_1.glb"),
            ("stop", None),
        ):
            with self.subTest(policy=policy):
                with patch("builtins.input") as prompt:
                    self.assertEqual(export_path(self.output, "Cube", "glb", policy), expected)
                prompt.assert_not_called()
        self.assertEqual(self.original.read_bytes(), b"original")

    def test_cli_defaults_to_prompt_and_accepts_policies(self):
        self.assertIsNone(parse_args(["scene.blend"]).on_exists)
        for policy in ("overwrite", "number", "stop"):
            self.assertEqual(parse_args(["scene.blend", "--on-exists", policy]).on_exists, policy)

    def test_cli_rejects_invalid_policy(self):
        with patch("sys.stderr", new=io.StringIO()):
            with self.assertRaises(SystemExit) as error:
                parse_args(["scene.blend", "--on-exists", "invalid"])
        self.assertEqual(error.exception.code, 2)


class ShellPolicyTests(unittest.TestCase):
    def test_wrapper_forwards_policies_and_selection_without_changing_paths(self):
        wrapper = Path(__file__).resolve().parents[1] / "headless-scripts/batch_export_tools.sh"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "scene with spaces.blend"
            source.touch()
            fake_blender = root / "fake blender"
            fake_blender.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$@"\n')
            fake_blender.chmod(0o755)
            env = dict(os.environ, BLENDER_BIN=str(fake_blender))
            for policy in (None, "overwrite", "number", "stop"):
                with self.subTest(policy=policy):
                    options = ["--on-exists", policy] if policy else []
                    result = subprocess.run(
                        ["bash", str(wrapper), "--model", str(source), "output folder", "--selected-only", *options],
                        cwd=root, env=env, text=True, capture_output=True, check=True,
                    )
                    forwarded = result.stdout.splitlines()
                    self.assertEqual(
                        forwarded[forwarded.index("--") + 1:],
                        [str(source), "output folder", "--selected-only", *options],
                    )
            for options in (["--on-exists"], ["--on-exists", "invalid"], ["--on-exists="]):
                with self.subTest(options=options):
                    result = subprocess.run(
                        ["bash", str(wrapper), "--model", *options], env=env, capture_output=True,
                    )
                    self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
