"""Blender Workflow Toolkit extension entry point."""

import bpy  # pyright: ignore[reportMissingModuleSource]

from .operators import BWT_OT_report_selection
from .panels import BWT_PT_workflow

CLASSES = (BWT_OT_report_selection, BWT_PT_workflow)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
