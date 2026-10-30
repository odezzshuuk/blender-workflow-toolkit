#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

blender_bin=${BLENDER_BIN:-"$HOME/.local/share/Steam/steamapps/common/Blender/blender"}
archive_path="$PWD/dist/batch_material_baker.zip"

# Build the extension archive and validate it with Blender.
mkdir -p dist
"$blender_bin" --background --factory-startup --command extension build --source-dir src --output-filepath "$archive_path"
"$blender_bin" --background --factory-startup --command extension validate "$archive_path"
