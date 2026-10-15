# Blender Workflow Toolkit

A minimal Blender extension project with a 3D Viewport sidebar and an example
operator. Requires Blender 4.2 or newer; no third-party runtime dependencies.

## Structure

- `blender_workflow_toolkit/`: extension entry point, operators, panels, and manifest.
- `scripts/build.py`: standalone ZIP packager.
- `scripts/export_models.py`: command-line per-object glTF exporter.
- `tests/blender_smoke.py`: registration and operator integration checks.
- `pyproject.toml`: uv project configuration and development dependencies.
- `dist/`: generated installation archives (ignored by Git).

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

## Export models from a .blend file

With Blender 4.2+ on PATH, run using ordinary Python (no `bpy` pip install needed):

```sh
python3 scripts/export_models.py example.blend ./exports
```

This launches Blender in the background and exports each visible mesh in the
file's active view layer separately. It does not process other scenes or excluded
collections. Each mesh gets its own folder containing a `.gltf`, associated
buffers, and textures. Existing folders receive a numbered suffix instead of
being overwritten. The original `.blend` file is not saved or modified.

```sh
# Export only the selection saved in the file, as self-contained GLB files.
python3 scripts/export_models.py example.blend ./exports --selected-only --format glb

# Specify Blender's executable if it is not on PATH (quote paths with spaces).
python3 scripts/export_models.py example.blend ./exports --blender /opt/blender/blender

# Show all options; output defaults to example_exports beside example.blend.
python3 scripts/export_models.py --help
```

This tool exports individual meshes, not complete character rigs or collection
assemblies. It retains object transforms and uses the glTF exporter's defaults
for materials and animation. Automatic execution of scripts embedded in the
source file is disabled, so assets relying on those scripts need separate setup.
An export failure returns a nonzero exit code; earlier exports may remain.

## Development and validation

### Editor setup (`bpy` imports)

Blender supplies `bpy` at runtime. For editor completion and import resolution,
create a separate development environment with Blender 4.2 API stubs. With
`uv` installed, run from the repository root (development Python requires 3.12+):

```sh
uv sync
```

This creates or updates `.venv`, installs the default `dev` dependency group,
and generates `uv.lock`. Commit the generated lockfile for reproducible setups;
subsequent installs can use `uv sync --locked`. Network access is needed for the
initial dependency download.

In VS Code:

1. Run **Python: Select Interpreter** from the Command Palette.
2. Select this repository's `.venv/bin/python` (Windows: `.venv/Scripts/python.exe`).
3. Run **Developer: Reload Window** if the unresolved-import warning remains.

The workspace setting defaults to `.venv`, but an existing interpreter selection
must be changed manually. Confirm the stubs are installed with
`uv pip show --python .venv/bin/python fake-bpy-module-4.2` (adjust the path on Windows).

These [API stubs](https://github.com/nutti/fake-bpy-module) are development-only;
execute the add-on and integration tests inside Blender. They are not included
in the extension ZIP.

If Pylance reports `Import "bpy" could not be resolved from source`
(`reportMissingModuleSource`), it has found the stubs but not Blender's runtime
implementation. The `bpy` imports suppress only that expected diagnostic with
`# pyright: ignore[reportMissingModuleSource]`. Autocomplete and other import
checks remain enabled. A plain `could not be resolved` warning instead means
you should check `uv sync` and the selected interpreter as described above.

### Implementation and checks

Add actions in `operators.py`, UI in `panels.py`, and register new classes in
`__init__.py`, with dependencies first. Unregistration uses reverse order.
Use four-space indentation, snake_case functions, and Blender's `BWT_OT_` and
`BWT_PT_` class naming conventions. No formatter or linter is configured yet.

Run syntax and Blender integration checks from a terminal:

```sh
python3 -m compileall -q blender_workflow_toolkit scripts tests
python3 -m unittest discover -s tests -p 'test_*.py'
blender --background --factory-startup --python-exit-code 1 --python tests/blender_smoke.py
```

The smoke test checks repeated registration, operator execution with empty and
populated selections, and cleanup. It uses Blender's bundled Python. Manually
verify the sidebar and notification in Blender after UI changes; record the
Blender version and results in pull requests. Rebuild and reinstall after edits,
then restart Blender to avoid cached modules.

## Release metadata

Before distribution, review the maintainer and version in `blender_manifest.toml`.
The scaffold declares GPL-3.0-or-later in its manifest; include the full license
text and any third-party notices before publishing. No permissions or external
services are required by the starter.
