"""Exercise shell exporter dispatch with a disposable Blender stand-in."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


WRAPPER = Path(__file__).resolve().parents[1] / 'headless-scripts/batch_export_tools.sh'


class ExportToolsTests(unittest.TestCase):
    def test_modes_forward_paths_and_common_options(self):
        with tempfile.TemporaryDirectory(prefix='export tools ') as directory:
            root = Path(directory)
            source = root / 'test scene.blend'
            source.touch()
            blender = root / 'fake blender'
            blender.write_text('#!/usr/bin/env python3\nimport json, sys\nprint(json.dumps(sys.argv[1:]))\n')
            blender.chmod(0o755)
            env = dict(os.environ, BLENDER_BIN=str(blender))
            for mode, script in (('--model', 'batch_export_models.py'),
                                 ('--image', 'batch_export_images.py')):
                with self.subTest(mode=mode):
                    result = subprocess.run(
                        [str(WRAPPER), mode, str(source), str(root / 'output dir'),
                         '--selected-only', '--on-exists=number'],
                        env=env, capture_output=True, text=True,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(json.loads(result.stdout), [
                        '--background', '--disable-autoexec', '--python-exit-code', '1',
                        '--python', str(WRAPPER.parent / script), '--',
                        str(source), str(root / 'output dir'), '--selected-only',
                        '--on-exists', 'number',
                    ])

    def test_quoted_home_paths_are_expanded(self):
        with tempfile.TemporaryDirectory(prefix='export tools ') as directory:
            root = Path(directory)
            source = root / 'My Assets' / 'Truck.blend'
            source.parent.mkdir()
            source.touch()
            blender = root / 'fake blender'
            blender.write_text('#!/usr/bin/env python3\nimport json, sys\nprint(json.dumps(sys.argv[1:]))\n')
            blender.chmod(0o755)
            env = dict(os.environ, HOME=str(root), BLENDER_BIN=str(blender))
            for mode in ('--model', '--image'):
                with self.subTest(mode=mode):
                    result = subprocess.run(
                        [str(WRAPPER), mode, '--selected-only', '--on-exists', 'overwrite',
                         '~/My Assets/Truck.blend', '~/export assets/'],
                        env=env, capture_output=True, text=True,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    args = json.loads(result.stdout)
                    self.assertEqual(args[args.index('--') + 1:], [
                        str(source), str(root / 'export assets') + '/',
                        '--selected-only', '--on-exists', 'overwrite',
                    ])

    def test_missing_or_conflicting_modes_are_rejected_before_blender_runs(self):
        for args in ([], ['--model', '--image'], ['--image', '--model']):
            with self.subTest(args=args):
                result = subprocess.run([str(WRAPPER), *args], capture_output=True, text=True)
                self.assertEqual(result.returncode, 2)
                self.assertIn('Choose exactly one of --model or --image', result.stderr)

    def test_help_documents_both_modes(self):
        result = subprocess.run([str(WRAPPER), '--help'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn('--model', result.stdout)
        self.assertIn('--image', result.stdout)


if __name__ == '__main__':
    unittest.main()
