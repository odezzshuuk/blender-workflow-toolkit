# Repository Guidelines

## Project Structure & Module Organization

- `src/` contains the Blender extension: `texture_baking.py` bakes images, `baked_materials.py` builds shaders, `material_switching.py` restores material assignments, and `ui.py` defines controls. Keep registration in `__init__.py`.
- `headless-scripts/` contains the model exporter and its Bash wrapper. Use this directory for commands; some README examples still reference `scripts/`.
- `tests/` contains Python unit tests and Blender integration checks. `test.blend` is a sample scene.
- `dist/` holds generated extension archives; `output/` holds exports. Both are ignored. `CustomExportMaterials.cs` provides separate C# integration code.

## Build, Test, and Development Commands

Use Python 3.12+ and Blender 4.2+.

- `uv sync` creates the development environment and installs Blender type stubs.
- `BLENDER_BIN=/path/to/blender ./build.sh` builds and validates `dist/batch_material_baker.zip`. Without an override, the script uses the Steam Blender installation.
- `uv run python -m unittest discover -s tests` runs tests without Blender.
- `pyright` runs the configured standard type checks when installed separately; configuration lives in `pyproject.toml`.
- After building, run `blender --background --factory-startup --python-exit-code 1 --python tests/blender_bake_addon_checks.py` to check the packaged extension.
- `./headless-scripts/batch_export_models.sh --on-exists number test.blend ./output` exports the sample scene without overwriting existing output.

## Coding Style & Naming Conventions

Use four-space Python indentation, snake_case functions and modules, and uppercase constants. Preserve Blender class prefixes such as `BWT_OT_`, `BWT_PT_`, and `BWT_PG_`. Add type annotations to public helpers and keep Blender-specific operations separate from pure logic. Follow existing local formatting; no formatter is configured. Bash scripts use `set -euo pipefail` and quote paths.

## Testing Guidelines

Use `unittest`, naming files `test_*.py` and methods `test_*`. Add regression coverage for changed behavior, especially image naming, export collisions, and material restoration. Use disposable Blender processes for integration checks. No numeric coverage threshold is configured. Rebuild the archive before testing extension changes.

## Commit & Pull Request Guidelines

Recent commits use brief subjects such as `update` and `add comments`; no formal convention is established. Prefer descriptive imperative subjects, such as `Fix restoration after failed baking`. PRs should describe the behavior change, relevant issues, and validation commands/results. Include screenshots for UI changes. Keep generated exports, archives, and local configuration out of commits.
