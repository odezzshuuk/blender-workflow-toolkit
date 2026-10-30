"""Export individual meshes without materials from a .blend file in background Blender."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
import sys
from typing import TYPE_CHECKING, Literal, TypeAlias, cast

# Blender's --python execution does not always include the script directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from export_common import (
    ConflictPolicy, ExportArgs as CommonExportArgs, ExportError,
    add_export_arguments, blender_args, numbered_path, overwrite_path, run_export, safe_name,
)

if TYPE_CHECKING:
    from bpy.types import ViewLayer

ExportFormat: TypeAlias = Literal["gltf", "glb"]


class ExportArgs(CommonExportArgs):
    format: ExportFormat
    on_exists: ConflictPolicy | None


def parse_args(argv: Sequence[str] | None = None) -> ExportArgs:
    parser = argparse.ArgumentParser(
        prog="blender --background --python headless-scripts/batch_export_models.py --",
        description=__doc__,
    )
    add_export_arguments(parser, "_exports", prompt=True)
    parser.add_argument("--format", choices=("gltf", "glb"), default="glb")
    return parser.parse_args(blender_args(argv), namespace=ExportArgs())


def export_path(
    output_dir: Path, object_name: str, file_format: ExportFormat,
    on_exists: ConflictPolicy | None = None,
) -> Path | None:
    """Apply a collision policy or ask; return None to stop the batch."""

    if on_exists not in (None, "overwrite", "number", "stop"):
        raise ValueError(f"Unknown conflict policy: {on_exists}")

    # Reserve matching stems across model files and their sidecar buffers.
    name = safe_name(object_name, "Object")
    entries: list[Path] = list(output_dir.iterdir())
    existing: set[str] = {path.stem.casefold() for path in entries}
    filepath = output_dir / f"{name}.{file_format}"

    if name.casefold() not in existing:
        return filepath

    # Ask how to resolve the collision when no automatic policy was supplied.
    if on_exists is None:
        print(f"An export with the name '{name}' already exists in {output_dir}.")
        print("1. Overwrite existing export")
        print("2. Keep existing export and add a numbered suffix to the new export")
        print("3. Stop exporting")
        choices: dict[str, ConflictPolicy] = {"1": "overwrite", "2": "number", "3": "stop"}
        while on_exists is None:
            try:
                choice = input("Choose [1/2/3]: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nNo choice received; stopping export.")
                return None
            on_exists = choices.get(choice)
            if on_exists is None:
                print("Enter 1, 2, or 3.")

    if on_exists == "stop":
        return None
    if on_exists == "overwrite":
        # Reuse the actual spelling when the existing filename differs in case.
        filepath = next(
            (path for path in entries if path.name.casefold() == filepath.name.casefold()),
            filepath,
        )
        return overwrite_path(filepath)

    return numbered_path(output_dir, name, file_format,
                         lambda path: path.stem.casefold() in existing)


def export_models(args: ExportArgs) -> None:
    import bpy  # pyright: ignore[reportMissingModuleSource]

    try:

        # Load the source scene and prepare mesh selection for export.
        bpy.ops.wm.open_mainfile(filepath=str(args.blend_file))
        if bpy.context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
    except RuntimeError as error:
        raise ExportError(f"Could not prepare the Blender file: {error}") from error

    view_layer = cast("ViewLayer | None", bpy.context.view_layer)

    if view_layer is None:
        print("Nothing exported: the file has no active view layer.")
        return

    selected: list[bpy.types.Object] = list(bpy.context.selected_objects)

    if args.selected_only and not selected:
        print("Nothing exported: no saved selection. Save a selection or omit --selected-only.")
        return

    # Collect visible meshes in a stable export order.
    active: bpy.types.Object | None = view_layer.objects.active
    candidates = selected if args.selected_only else list(view_layer.objects)
    objects: list[bpy.types.Object] = sorted(
        (obj for obj in candidates if obj.type == 'MESH' and obj.visible_get()),
        key=lambda obj: obj.name,
    )

    if not objects:
        if args.selected_only:
            print("Nothing exported: the saved selection contains no visible meshes.")
        else:
            print("Nothing exported: no visible meshes in the active view layer.")
        return

    # main() resolves the optional CLI output directory before exporting.
    # output_dir = cast(Path, args.output_dir)
    output_dir = args.output_dir

    if output_dir is None:
        return

    # Create the destination used directly by every mesh export.
    output_dir.mkdir(parents=True, exist_ok=True)
    exported = 0
    try:
        for obj in selected:
            obj.select_set(False)
        for obj in objects:
            filepath = export_path(output_dir, obj.name, args.format, args.on_exists)

            if filepath is None:
                print("Export stopped; completed files kept.")
                break

            locked = obj.hide_select
            try:

                # Make this mesh the sole selected export target.
                obj.hide_select = False
                obj.select_set(True)
                view_layer.objects.active = obj
                try:

                    # Write the selected mesh without embedding materials.
                    result = bpy.ops.export_scene.gltf(
                        filepath=str(filepath),
                        check_existing=False,
                        export_format='GLTF_SEPARATE' if args.format == "gltf" else 'GLB',
                        use_selection=True,
                        export_materials='NONE',
                    )
                except RuntimeError as error:
                    raise ExportError(f"Could not export {obj.name}: {error}") from error

                if result != {'FINISHED'} or not filepath.is_file():
                    raise ExportError(f"Export failed: {obj.name}")

                print(f"Written: {filepath}", flush=True)
                exported += 1
            finally:
                obj.select_set(False)
                obj.hide_select = locked
    finally:

        # Restore the saved selection and active object after the batch.
        for obj in selected:
            obj.select_set(True)
        view_layer.objects.active = active
    print(f"Exported {exported} mesh object(s) to {args.output_dir}")


def main(argv: Sequence[str] | None = None) -> int:
    return run_export(parse_args(argv), export_models, "_exports", "Export")


if __name__ == "__main__":
    raise SystemExit(main())
