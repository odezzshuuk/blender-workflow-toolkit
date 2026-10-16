# Blender Workflow Toolkit

## Introduction

- Blender scripts development environment

## Initial Setup

```sh
uv sync
```

## Shell Wrapper

```sh
./tools/batch_export_models.sh example.blend ./exports
./tools/batch_export_models.sh "my scene.blend" "./my exports" --selected-only 
```

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

