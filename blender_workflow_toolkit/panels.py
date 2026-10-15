"""Panels displayed in the 3D Viewport sidebar."""

import bpy  # pyright: ignore[reportMissingModuleSource]


class BWT_PT_workflow(bpy.types.Panel):
    bl_label = "Workflow Toolkit"
    bl_idname = "BWT_PT_workflow"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Workflow"

    def draw(self, context):
        layout = self.layout
        layout.label(text=f"Selected: {len(context.selected_objects)}")
        layout.operator("bwt.report_selection", icon='INFO')
