"""Export all images in a .blend file as PNGs without exporting models or materials."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
import sys
from typing import TYPE_CHECKING

# Blender's --python execution does not always include the script directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from export_common import (
    ConflictPolicy, ExportArgs as CommonExportArgs, ExportError,
    add_export_arguments, blender_args, numbered_path, overwrite_path, run_export, safe_name,
)

if TYPE_CHECKING:
    from bpy.types import Image



class ExportArgs(CommonExportArgs):
    on_exists: ConflictPolicy


def parse_args(argv: Sequence[str] | None = None) -> ExportArgs:
    parser = argparse.ArgumentParser(
        prog="blender --background --python headless-scripts/batch_export_images.py --",
        description=__doc__,
    )
    add_export_arguments(parser, "_textures", selection_help="Ignored; all images are exported")
    parser.add_argument("--select-only", dest="selected_only", action="store_true",
                        help="Ignored; all images are exported")
    return parser.parse_args(blender_args(argv), namespace=ExportArgs())


def image_path(output_dir: Path, image_name: str, on_exists: ConflictPolicy) -> Path:
    """Choose a safe PNG filename, accounting for case-insensitive collisions."""

    # Match PNG filenames without regard to case.
    name = safe_name(image_name, "Image")
    entries = {path.name.casefold(): path for path in output_dir.iterdir()}
    target = output_dir / f"{name}.png"
    existing = entries.get(target.name.casefold())

    if existing is None:
        return target
    if on_exists == "stop":
        raise ExportError(f"Image already exists: {existing}. Use --on-exists number or overwrite.")
    if on_exists == "overwrite":
        return overwrite_path(existing)

    return numbered_path(output_dir, name, "png",
                         lambda path: path.name.casefold() in entries)


def save_image(image: Image, filepath: Path) -> None:
    """Save pixels directly, without applying a scene render/view transform."""
    previous_path, previous_format = image.filepath_raw, image.file_format
    try:

        # Write the image pixels as PNG using temporary output metadata.
        image.filepath_raw = str(filepath)
        image.file_format = 'PNG'
        image.save()
    except RuntimeError as error:
        raise ExportError(f"Could not export {image.name}: {error}") from error
    finally:

        # Restore the image metadata even when saving fails.
        image.filepath_raw = previous_path
        image.file_format = previous_format

    if not filepath.is_file():
        raise ExportError(f"Image was not written: {filepath}")


def export_images(args: ExportArgs) -> None:
    import bpy  # pyright: ignore[reportMissingModuleSource]

    try:

        # Load the source file before collecting its image datablocks.
        bpy.ops.wm.open_mainfile(filepath=str(args.blend_file))
    except RuntimeError as error:
        raise ExportError(f"Could not open the Blender file: {error}") from error

    # Collect all images independently of object selection or add-on records.
    images = list(bpy.data.images)

    if not images:
        print("Nothing exported: no images in the file.")
        return

    output_dir = args.output_dir

    if output_dir is None:
        raise ExportError("No output directory specified")

    # Create the destination and export each image in name order.
    output_dir.mkdir(parents=True, exist_ok=True)
    for image in sorted(images, key=lambda image: image.name):
        filepath = image_path(output_dir, image.name, args.on_exists)
        save_image(image, filepath)
        print(f"Written: {filepath}", flush=True)
    print(f"Exported {len(images)} image(s) to {output_dir}")


def main(argv: Sequence[str] | None = None) -> int:
    return run_export(parse_args(argv), export_images, "_textures", "Image export")


if __name__ == "__main__":
    raise SystemExit(main())
