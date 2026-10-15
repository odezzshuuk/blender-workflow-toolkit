"""Export individual meshes from a .blend file using a background Blender process."""

import argparse
from pathlib import Path
import re
import sys


def parse_args(argv=None):
    if argv is None:
        argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(
        prog="blender --background --python scripts/export_models.py --",
        description=__doc__,
    )
    parser.add_argument("blend_file", type=Path, help="Source .blend file")
    parser.add_argument("output_dir", type=Path, nargs="?", help="Default: <blend stem>_exports")
    parser.add_argument("--format", choices=("gltf", "glb"), default="glb")
    parser.add_argument("--selected-only", action="store_true", help="Use the selection saved in the file")
    return parser.parse_args(argv)


def export_path(output_dir, object_name, file_format):
    """Choose a flat destination without replacing an existing model or buffer."""
    name = "mesh_" + (re.sub(r"[^A-Za-z0-9_-]", "_", object_name) or "Object")
    existing = {path.stem.casefold() for path in output_dir.iterdir()}
    stem = name
    suffix = 1
    while stem.casefold() in existing:
        stem = f"{name}_{suffix}"
        suffix += 1
    return output_dir / f"{stem}.{file_format}"


def export_models(args):
    import bpy  # pyright: ignore[reportMissingModuleSource]

    # Loading here makes load failures Python errors handled by --python-exit-code.
    bpy.ops.wm.open_mainfile(filepath=str(args.blend_file))
    if bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    view_layer = bpy.context.view_layer
    if not isinstance(view_layer, bpy.types.ViewLayer):
        raise RuntimeError("The loaded file has no valid active view layer")
    selected = list(bpy.context.selected_objects)
    active = view_layer.objects.active
    candidates = selected if args.selected_only else list(view_layer.objects)
    objects = sorted(
        (obj for obj in candidates if obj.type == 'MESH' and obj.visible_get()),
        key=lambda obj: obj.name,
    )
    if not objects:
        raise RuntimeError("No visible mesh objects to export in the active view layer")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    try:
        for obj in selected:
            obj.select_set(False)
        for obj in objects:
            filepath = export_path(args.output_dir, obj.name, args.format)
            if not any(slot.material for slot in obj.material_slots):
                print(f"Note: {obj.name} has no material assigned in its source material slots")
            locked = obj.hide_select
            try:
                obj.hide_select = False
                obj.select_set(True)
                view_layer.objects.active = obj
                result = bpy.ops.export_scene.gltf(
                    filepath=str(filepath),
                    export_format='GLTF_SEPARATE' if args.format == "gltf" else 'GLB',
                    use_selection=True,
                    export_materials='EXPORT',
                    export_image_format='AUTO',
                    export_texture_dir="",
                )
                if result != {'FINISHED'} or not filepath.is_file():
                    raise RuntimeError(f"Export failed: {obj.name}")
                print(f"Written: {filepath}", flush=True)
            finally:
                obj.select_set(False)
                obj.hide_select = locked
    finally:
        for obj in selected:
            obj.select_set(True)
        view_layer.objects.active = active
    print(f"Exported {len(objects)} mesh object(s) to {args.output_dir}")


def main(argv=None):
    args = parse_args(argv)
    args.blend_file = args.blend_file.expanduser().resolve()
    if not args.blend_file.is_file() or args.blend_file.suffix.lower() != ".blend":
        raise ValueError(f"Expected an existing .blend file: {args.blend_file}")
    args.output_dir = (
        args.output_dir or args.blend_file.with_name(args.blend_file.stem + "_exports")
    ).expanduser().resolve()
    export_models(args)


if __name__ == "__main__":
    main()
