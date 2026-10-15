"""Export individual meshes from a .blend file using a background Blender process."""

import argparse
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import cast


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("blend_file", type=Path, help="Source .blend file")
    parser.add_argument("output_dir", type=Path, nargs="?", help="Default: <blend stem>_exports")
    parser.add_argument("--blender", default="blender", help="Blender executable name or path")
    parser.add_argument("--format", choices=("gltf", "glb"), default="gltf")
    parser.add_argument("--selected-only", action="store_true", help="Use the selection saved in the file")
    return parser.parse_args(argv)


def export_models(args):
    import bpy  # pyright: ignore[reportMissingModuleSource]

    # Loading here makes load failures Python errors handled by --python-exit-code.
    bpy.ops.wm.open_mainfile(filepath=str(args.blend_file))
    if bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    # Some generated bpy stubs misidentify this property as a method.
    view_layer = cast("bpy.types.ViewLayer | None", bpy.context.view_layer)
    if view_layer is None:
        raise RuntimeError("The loaded file has no active view layer")
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
            # Prefixing also avoids reserved device names on Windows.
            name = "mesh_" + (re.sub(r"[^A-Za-z0-9_-]", "_", obj.name) or "Object")
            folder = args.output_dir / name
            suffix = 1
            while True:
                try:
                    folder.mkdir()
                    break
                except FileExistsError:
                    folder = args.output_dir / f"{name}_{suffix}"
                    suffix += 1

            filepath = folder / f"{folder.name}.{args.format}"
            locked = obj.hide_select
            try:
                obj.hide_select = False
                obj.select_set(True)
                view_layer.objects.active = obj
                result = bpy.ops.export_scene.gltf(
                    filepath=str(filepath),
                    export_format='GLTF_SEPARATE' if args.format == "gltf" else 'GLB',
                    use_selection=True,
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
        print(f"Error: expected an existing .blend file: {args.blend_file}", file=sys.stderr)
        return 2
    args.output_dir = (
        args.output_dir or args.blend_file.with_name(args.blend_file.stem + "_exports")
    ).expanduser().resolve()
    blender = shutil.which(args.blender)
    if blender is None:
        print("Error: Blender not found. Set --blender /path/to/blender", file=sys.stderr)
        return 2
    command = [
        blender, "--background", "--factory-startup", "--disable-autoexec",
        "--python-exit-code", "1", "--python", str(Path(__file__).resolve()),
        "--", "--bwt-worker", str(args.blend_file), str(args.output_dir),
        "--format", args.format,
    ]
    if args.selected_only:
        command.append("--selected-only")
    return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    if "--" in sys.argv and sys.argv[sys.argv.index("--") + 1:][:1] == ["--bwt-worker"]:
        export_models(parse_args(sys.argv[sys.argv.index("--") + 2:]))
    else:
        raise SystemExit(main())
