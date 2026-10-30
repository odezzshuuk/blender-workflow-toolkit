#!/usr/bin/env bash
# Stop on failed commands, unset variables, and errors within pipelines.
set -euo pipefail

usage() {
    printf 'Usage: %s [DESTINATION]\nDefault destination: ~/.local/bin/blender-workflow\n' "${0##*/}"
}

# Accept a help flag or one optional destination; reject other options.
if [[ "${1:-}" == --help || "${1:-}" == -h ]]; then
    usage
    exit 0
fi
if (($# > 1)) || [[ "${1:-}" == -* ]]; then
    usage >&2
    exit 2
fi

# Find the repository relative to this script, regardless of the working directory.
project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

# Create the destination and resolve its absolute path for comparisons and messages.
destination=${1:-"$HOME/.local/bin/blender-workflow"}
sources_dir="$project_dir/headless-scripts"
mkdir -p -- "$destination"
destination=$(cd -- "$destination" && pwd)

# Prevent installing files onto themselves.
if [[ "$destination" == "$sources_dir" ]]; then
    printf 'Destination must differ from the source scripts directory.\n' >&2
    exit 2
fi

# Unmatched globs expand to nothing; arrays preserve filenames containing spaces.
shopt -s nullglob
sources=("$sources_dir"/*.sh "$sources_dir"/*.py)

if ((${#sources[@]} == 0)); then
    printf 'No shell or Python scripts found in %s/headless-scripts\n' "$project_dir" >&2
    exit 1
fi

# Copy top-level scripts, replacing matching installed files and setting permissions.
for source in "${sources[@]}"; do
    # Shell wrappers are executable; companion Python files are loaded by Blender.
    mode=644
    [[ "$source" == *.sh ]] && mode=755

    # ${source##*/} removes the directory prefix, keeping the original filename.
    install -m "$mode" -- "$source" "$destination/${source##*/}"
    printf 'Installed %s\n' "$destination/${source##*/}"
done

printf 'Keep %s on PATH. Rerun this installer after editing scripts.\n' "$destination"
