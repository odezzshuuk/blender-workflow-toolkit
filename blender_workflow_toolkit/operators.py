"""Workflow actions exposed through Blender operators."""

import bpy  # pyright: ignore[reportMissingModuleSource]


class BWT_OT_report_selection(bpy.types.Operator):
    """Report the number of selected objects without changing the scene."""

    bl_idname = "bwt.report_selection"
    bl_label = "Report Selection"
    bl_description = "Show how many objects are selected"

    def execute(self, context):
        count = len(context.selected_objects)
        self.report({'INFO'}, f"Selected objects: {count}")
        return {'FINISHED'}
