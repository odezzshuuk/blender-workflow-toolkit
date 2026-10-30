#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'HELP'
Usage: batch_export_tools.sh (--model | --image) [--selected-only] [--on-exists POLICY] INPUT.blend OUTPUT_DIR

Export models or all images to OUTPUT_DIR. Choose exactly one mode.
  --model         Export visible meshes as GLB files without materials or textures.
  --image         Export all images as PNG files.
  --selected-only  Models only: use the saved selection; ignored for images.
  --on-exists POLICY  overwrite, number, or stop.
                      Default: prompt for models; stop for images.
  -h, --help       Show this help.

Quote paths containing spaces. Relative paths are resolved from your current directory.
Quoted paths beginning with ~/ are resolved from your home directory.
Set BLENDER_BIN to override the default Steam Blender executable.
HELP
}

export_script=""
positional=()
selection_args=()
exists_args=()

# Collect the export mode and options to forward to the Python exporter.
while (($#)); do
    case "$1" in
        --model|--image)
            if [[ -n "$export_script" ]]; then
                printf 'Choose exactly one of --model or --image.\n' >&2
                exit 2
            fi
            case "$1" in
                --model) export_script="batch_export_models.py" ;;
                --image) export_script="batch_export_images.py" ;;
            esac
            shift ;;
        --selected-only|--select-only) selection_args=(--selected-only); shift ;;
        --on-exists)
            if (($# < 2)); then
                printf 'Expected overwrite, number, or stop after --on-exists.\n' >&2
                exit 2
            fi
            exists_args=(--on-exists "$2"); shift 2 ;;
        --on-exists=*) exists_args=(--on-exists "${1#*=}"); shift ;;
        -h|--help) usage; exit 0 ;;
        --) shift; positional+=("$@"); break ;;
        -*) printf 'Unknown option: %s\n' "$1" >&2; usage >&2; exit 2 ;;
        *) positional+=("$1"); shift ;;
    esac
done

if ((${#exists_args[@]})); then
    case "${exists_args[1]}" in
        overwrite|number|stop) ;;
        *) printf 'Invalid --on-exists policy: %s\n' "${exists_args[1]}" >&2; exit 2 ;;
    esac
fi

if [[ -z "$export_script" ]]; then
    printf 'Choose exactly one of --model or --image.\n' >&2
    usage >&2
    exit 2
fi

if ((${#positional[@]} != 2)); then
    usage >&2
    exit 2
fi

blend_file=${positional[0]}
output_dir=${positional[1]}
# Quoting paths with spaces prevents the shell from expanding a leading ~/.
if [[ "$blend_file" == '~/'* ]]; then
    blend_file="$HOME/${blend_file:2}"
fi
if [[ "$output_dir" == '~/'* ]]; then
    output_dir="$HOME/${output_dir:2}"
fi

if [[ ! -f "$blend_file" || "${blend_file,,}" != *.blend ]]; then
    printf 'Expected an existing .blend file: %s\n' "$blend_file" >&2
    exit 2
fi
if [[ -z "$output_dir" || ( -e "$output_dir" && ! -d "$output_dir" ) ]]; then
    printf 'Expected an output directory: %s\n' "$output_dir" >&2
    exit 2
fi

# Resolve links installed in ~/.local/bin back to the repository (Linux).
script_path=$(readlink -f -- "${BASH_SOURCE[0]}")
script_dir=$(dirname -- "$script_path")
blender_bin=${BLENDER_BIN:-"$HOME/.local/share/Steam/steamapps/common/Blender/blender"}

if ! command -v "$blender_bin" >/dev/null 2>&1; then
    printf 'Blender not found: %s\nSet BLENDER_BIN to its executable path.\n' "$blender_bin" >&2
    exit 127
fi

# Run the selected exporter in a disposable background Blender process.
exec "$blender_bin" --background --disable-autoexec --python-exit-code 1 \
    --python "$script_dir/$export_script" -- \
    "$blend_file" "$output_dir" "${selection_args[@]}" "${exists_args[@]}"
