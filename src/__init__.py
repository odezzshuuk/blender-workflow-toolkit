"""Register the modular baking workflow extension."""
import bpy
from bpy.props import PointerProperty
from .ui import CLASSES, BWT_PG_bake_settings, BWT_PG_data_user_settings

def register() -> None:
    # Blender calls register when enabling the add-on. Class definitions alone are not enough.
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    # Attach settings to every Scene, accessible as context.scene.bwt_bake_settings.
    # Blender stores these property values with the scene when the .blend is saved.
    setattr(bpy.types.Scene, "bwt_bake_settings", PointerProperty(type=BWT_PG_bake_settings))
    setattr(bpy.types.Scene, "bwt_data_user_settings", PointerProperty(type=BWT_PG_data_user_settings))


def unregister() -> None:
    # Blender calls unregister when disabling the add-on. Remove the Scene field before
    # unregistering its PropertyGroup, then remove classes in reverse dependency order.
    delattr(bpy.types.Scene, "bwt_bake_settings")
    delattr(bpy.types.Scene, "bwt_data_user_settings")
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
