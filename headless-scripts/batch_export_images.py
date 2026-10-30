"""Export recorded baked images as PNGs without exporting models or materials."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from pathlib import Path
import re
import sys
from typing import TYPE_CHECKING, Literal, TypeAlias, cast

if TYPE_CHECKING:
    from bpy.types import Image

ConflictPolicy: TypeAlias = Literal["overwrite", "number", "stop"]


class ExportArgs(argparse.Namespace):
    blend_file: Path
    output_dir: Path | None
    selected_only: bool
    on_exists: ConflictPolicy


class ExportError(Exception):
    """An expected image or Blender operation failure."""


def parse_args(argv: Sequence[str] | None = None) -> ExportArgs:
    if argv is None:
        argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(
        prog="blender --background --python headless-scripts/batch_export_images.py --",
        description=__doc__,
    )
    parser.add_argument("blend_file", type=Path, help="Source .blend file with saved bakes")
    parser.add_argument("output_dir", type=Path, nargs="?", help="Default: <blend stem>_textures")
    parser.add_argument("--selected-only", action="store_true", help="Use the selection saved in the file")
    parser.add_argument(
        "--on-exists", choices=("overwrite", "number", "stop"), default="stop",
        help="Handle filename conflicts (default: stop without overwriting)",
    )
    return parser.parse_args(argv, namespace=ExportArgs())


def image_path(output_dir: Path, image_name: str, on_exists: ConflictPolicy) -> Path:
    """Choose a safe PNG filename, accounting for case-insensitive collisions."""
    name = re.sub(r"[^A-Za-z0-9_-]", "_", image_name) or "Image"
    entries = {path.name.casefold(): path for path in output_dir.iterdir()}
    target = output_dir / f"{name}.png"
    existing = entries.get(target.name.casefold())
    if existing is None:
        return target
    if on_exists == "stop":
        raise ExportError(f"Image already exists: {existing}. Use --on-exists number or overwrite.")
    if on_exists == "overwrite":
        if existing.is_dir():
            raise IsADirectoryError(existing)
        return existing
    suffix = 1
    while f"{name}_{suffix}.png".casefold() in entries:
        suffix += 1
    return output_dir / f"{name}_{suffix}.png"


def save_image(image: Image, filepath: Path) -> None:
    """Save pixels directly, without applying a scene render/view transform."""
    previous_path, previous_format = image.filepath_raw, image.file_format
    try:
        image.filepath_raw = str(filepath)
        image.file_format = 'PNG'
        image.save()
    except RuntimeError as error:
        raise ExportError(f"Could not export {image.name}: {error}") from error
    finally:
        image.filepath_raw = previous_path
        image.file_format = previous_format
    if not filepath.is_file():
        raise ExportError(f"Image was not written: {filepath}")


def export_images(args: ExportArgs) -> None:
    import bpy  # pyright: ignore[reportMissingModuleSource]

    try:
        bpy.ops.wm.open_mainfile(filepath=str(args.blend_file))
    except RuntimeError as error:
        raise ExportError(f"Could not open the Blender file: {error}") from error
    objects = bpy.context.selected_objects if args.selected_only else bpy.data.objects
    images: dict[int, Image] = {}
    for obj in sorted(objects, key=lambda obj: obj.name):
        recorded = cast("Mapping[str, Image | None] | None", obj.get("bwt_bake_images"))
        if not recorded:
            continue
        for kind, image in recorded.items():
            if not isinstance(image, bpy.types.Image):
                raise ExportError(f"Missing baked image: {obj.name} / {kind}. Rebake and save the blend.")
            images[image.as_pointer()] = image
    if not images:
        scope = "the saved selection" if args.selected_only else "the file"
        print(f"Nothing exported: no recorded baked images in {scope}.")
        return
    output_dir = args.output_dir
    if output_dir is None:
        raise ExportError("No output directory specified")
    output_dir.mkdir(parents=True, exist_ok=True)
    for image in sorted(images.values(), key=lambda image: image.name):
        filepath = image_path(output_dir, image.name, args.on_exists)
        save_image(image, filepath)
        print(f"Written: {filepath}", flush=True)
    print(f"Exported {len(images)} baked image(s) to {output_dir}")


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        args.blend_file = args.blend_file.expanduser().resolve()
        if not args.blend_file.is_file() or args.blend_file.suffix.lower() != ".blend":
            print(f"Expected an existing .blend file: {args.blend_file}", file=sys.stderr)
            return 2
        args.output_dir = (
            args.output_dir or args.blend_file.with_name(args.blend_file.stem + "_textures")
        ).expanduser().resolve()
        export_images(args)
    except (OSError, ExportError) as error:
        print(f"Image export stopped: {' '.join(str(error).split())}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nImage export interrupted; completed files kept.")
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
