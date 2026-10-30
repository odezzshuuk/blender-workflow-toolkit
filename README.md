# Blender Workflow Toolkit

## Introduction

- Blender scripts development environment

## Initial Setup

```sh
uv sync
```

## Build

```sh
mkdir -p dist
blender --background --factory-startup --command extension build --source-dir src --output-filepath "$PWD/dist/batch_material_baker.zip"
blender --background --factory-startup --command extension validate dist/batch_material_baker.zip
```

## Shell Wrapper

- `--selected-only` 
- `--on-exists overwrite|number|stop`.
- Choose one of `--model` (GLB meshes) or `--image` (baked PNG images).
  - for `--model`, files export to directory `<output_dir>/models/<model_name_prefix>/`
  - for `--image`, files export to directory `<output_dir>/textures/<model_name_prefix>/`.

```sh
./headless-scripts/batch_export_tools.sh --model example.blend ./output
./headless-scripts/batch_export_tools.sh --image "example.blend" "./output" --selected-only
```


```sh
./headless-scripts/batch_export_tools.sh --image example.blend ./textures --on-exists number
```

## Headless Scripts

- `headless-scripts/batch_export_models.py` exports meshes
- `headless-scripts/batch_export_images.py` exports baked images

With Blender 4.2+ on PATH, run the script directly inside Blender:

```sh
# Export grouped models without materials or textures to ./exports.
blender --background --disable-autoexec --python-exit-code 1 --python headless-scripts/batch_export_models.py -- example.blend ./exports --format gltf

# Export only the selection saved in the file, as self-contained GLB files.
blender --background --disable-autoexec --python-exit-code 1 --python headless-scripts/batch_export_models.py -- example.blend ./exports --selected-only --format glb

# Show all options; output defaults to example_exports beside example.blend.
blender --background --python headless-scripts/batch_export_models.py -- --help

# Export baked images only
blender --background --factory-startup --disable-autoexec --python-exit-code 1 --python headless-scripts/batch_export_images.py -- example.blend ./textures --on-exists number
```

### Baked material workflow

1. `Bake Selected Materials` create materials named `<object_name>_baked`
2. `Original/Baked Materials` switching between baked materials and original materials

- Avoid changing topology while baked materials are active; 
- restoration requires the original face order. 

### Find data-block users


Supported types include 

- images
- materials
- objects
- meshes
- node groups
- textures,
- collections
- worlds
- scenes
- actions
- armatures
- curves
- cameras
- lights
- sounds
- fonts. 
