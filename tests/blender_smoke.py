"""Run with Blender in background mode; no third-party test framework needed."""

from pathlib import Path
import sys

import bpy  # pyright: ignore[reportMissingModuleSource]

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import blender_workflow_toolkit as toolkit


def main():
    for _ in range(2):
        toolkit.register()
        try:
            assert hasattr(bpy.types, "BWT_PT_workflow")
            bpy.ops.object.select_all(action='DESELECT')
            assert bpy.ops.bwt.report_selection() == {'FINISHED'}
            bpy.ops.object.select_all(action='SELECT')
            assert bpy.ops.bwt.report_selection() == {'FINISHED'}
        finally:
            toolkit.unregister()
        assert not hasattr(bpy.types, "BWT_PT_workflow")
    print("Workflow Toolkit smoke test passed")


if __name__ == "__main__":
    main()
