# Blender Workflow Toolkit

## Build and install

Run from the repository root in a terminal using Python 3.11+:

```sh
python3 scripts/build.py
```

In Blender, open **Edit > Preferences > Add-ons**, use the menu's **Install from
Disk** action, and select `dist/blender_workflow_toolkit-0.1.0.zip`. Enable the
extension if needed. In the 3D Viewport, press **N**, open **Workflow**, and click
**Report Selection**. The button reports the selected-object count without
modifying the scene.

Alternatively, use Blender's official extension tooling from the repository root
(the `blender` executable must be on PATH):

```sh
blender --command extension validate blender_workflow_toolkit
blender --command extension build --source-dir blender_workflow_toolkit --output-dir dist
```

See the [Blender extension documentation](https://docs.blender.org/manual/en/4.5/advanced/extensions/getting_started.html).

## Python Scripts

With Blender 4.2+ on PATH, run the script directly inside Blender:

```sh
# Export all objects in example.blend to ./exports as separate GLB files.
blender --background --disable-autoexec --python-exit-code 1 --python tools/batch_export_models.py -- example.blend ./exports

# Export only the selection saved in the file, as self-contained GLB files.
blender --background --disable-autoexec --python-exit-code 1 --python tools/batch_export_models.py -- example.blend ./exports --selected-only --format glb

# Show all options; output defaults to example_exports beside example.blend.
blender --background --python tools/batch_export_models.py -- --help
```


## Shell Wrapper

```sh
./tools/batch_export_models.sh example.blend ./exports
./tools/batch_export_models.sh "my scene.blend" "./my exports" --selected-only 
```

On Linux, keep both scripts in `tools/` and symlink the wrapper into
`~/.local/bin`. Run once from the repository root:

```sh
mkdir -p "$HOME/.local/bin"
chmod +x tools/batch_export_models.sh
ln -s "$PWD/tools/batch_export_models.sh" "$HOME/.local/bin/batch-export-models"
```

With `~/.local/bin` on PATH, run from any directory:

```sh
batch-export-models example.blend ./exports --selected-only
```

The wrapper resolves the symlink to find its companion Python script. Repository
edits take effect immediately; moving the repository requires recreating the link.
Input and output paths are relative to your current directory. Set `BLENDER_BIN`
to override the default Steam Blender executable.

Keep `.venv` in the repository and select it in your editor for `bpy` completion.
The command uses Blender's bundled Python and does not require activating `.venv`.

## Development and validation

With Python 3.12+ and uv installed, run `uv sync` to install development
dependencies and Blender API stubs. Commit `uv.lock`; use `uv sync --locked`
for reproducible installs.

In VS Code, select `.venv/bin/python` (Windows: `.venv/Scripts/python.exe`) via
**Python: Select Interpreter**. Reload the window if import warnings persist.
The stubs provide completion; Blender supplies the runtime `bpy` implementation.
Imports suppress the expected `reportMissingModuleSource` warning.

Add operators in `operators.py`, panels in `panels.py`, and register classes in
`__init__.py` with dependencies first. Use four-space indentation and snake_case
functions.

Run checks from the repository root:

```sh
python3 -m compileall -q blender_workflow_toolkit scripts tools tests
python3 -m unittest discover -s tests -p 'test_*.py'
blender --background --factory-startup --python-exit-code 1 --python tests/blender_smoke.py
```

The smoke test verifies registration, operator execution, and cleanup. Verify UI
changes manually in Blender and report the version and results in pull requests.
Rebuild, reinstall, and restart Blender after add-on changes.

## Release metadata

Before distribution, review the maintainer and version in `blender_manifest.toml`.
The scaffold declares GPL-3.0-or-later in its manifest; include the full license
text and any third-party notices before publishing. No permissions or external
services are required by the starter.
