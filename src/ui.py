"""Blender UI for baking materials into images in the current session."""

# Keep annotations evaluated here: Blender reads the property factory results
# from __annotations__ when registering the PropertyGroup.
from typing import TYPE_CHECKING, Literal, Protocol, TypeAlias, cast

import bpy
# bpy is Blender's Python API. Property factories define fields Blender can display and save.
from bpy.props import BoolProperty, EnumProperty, IntProperty, PointerProperty, StringProperty
from bpy.types import Context, Operator, Panel, PropertyGroup, UILayout, Window

# TYPE_CHECKING is true for Pyright but false when Blender runs this module.
# These stub-only types help the editor and are not imported at runtime.
if TYPE_CHECKING:
    from bpy.stub_internal.rna_enums import OperatorTypeFlagItems, RegionTypeItems, SpaceTypeItems

from .texture_baking import BakeError, DEFAULT_MAPS, bake_current_scene


from .material_switching import target_objects, toggle_materials
from .data_users import DATA_TYPE_ITEMS, find_data_users


# Operators return literal status sets. Explicit return annotations prevent Python
# type checkers from widening these values to set[str], which Blender does not accept.
OperatorResult: TypeAlias = set[
    Literal['RUNNING_MODAL', 'CANCELLED', 'FINISHED', 'PASS_THROUGH', 'INTERFACE']
]

# Each enum item contains its internal identifier, visible label, tooltip, and bit value.
# Separate powers of two allow multiple maps to be stored in one enum flag field.
# Keep these bit values stable so saved selections retain their meaning.
MAP_ITEMS: tuple[tuple[str, str, str, int], ...] = (
    ('BaseColor', "Base Color", "Unlit base color, including metallic surfaces", 1),
    ('Normal', "Normal", "Tangent-space normal with +Y (OpenGL/Godot)", 2),
    ('Roughness', "Roughness", "Principled BSDF roughness", 4),
    ('Metallic', "Metallic", "Principled BSDF metallic value", 8),
    ('AO', "Ambient Occlusion", "Occlusion from scene geometry", 16),
    ('Emission', "Emission", "Shader emission, including strength", 32),
    ('Alpha', "Alpha", "Principled BSDF alpha as a grayscale image", 64),
)


# A PropertyGroup bundles Blender-managed settings. Each Scene gets an instance below.
# The PG, OT, and PT class names identify property groups, operators, and panels.
class BWT_PG_bake_settings(PropertyGroup):
    # Blender requires ':' annotations for these definitions, rather than ordinary '=' fields.
    # name/description control the UI; default and min/max control initial and allowed values.
    selected_only: BoolProperty(
        name="Selected Meshes Only",
        description="Bake selected visible meshes; disable to bake all visible meshes in the view layer",
        default=True,
    )
    size: IntProperty(
        name="Resolution", description="Width and height of each image in pixels",
        default=1024, min=16, max=16384, soft_max=4096,
    )
    samples: IntProperty(
        name="Samples", description="Cycles samples per bake",
        default=32, min=1, max=4096, soft_max=256,
    )
    margin: IntProperty(
        name="Margin", description="Padding around UV islands in pixels",
        default=16, min=0, max=1024, soft_max=64,
    )
    # ENUM_FLAG exposes the selection in Python as a set of identifiers, such as {'Normal', 'AO'}.
    maps: EnumProperty(
        name="Texture Maps", description="Create one image per selected map for each mesh",
        items=MAP_ITEMS, options={'ENUM_FLAG'}, default=set(DEFAULT_MAPS),
    )


# This Protocol describes our dynamically added Scene field to the type checker.
# cast(...) below supplies type information; it does not convert or modify the Scene.
class _SceneWithBakeSettings(Protocol):
    """Property attached to Scene when this add-on registers."""

    bwt_bake_settings: BWT_PG_bake_settings


# An Operator is an action Blender can run from a button, search, or bpy.ops.
class BWT_OT_toggle_texture_map(Operator):
    # This identifier also makes the action callable as bpy.ops.bwt.toggle_texture_map(...).
    bl_idname: str = "bwt.toggle_texture_map"
    bl_label: str = "Toggle Texture Map"
    bl_description: str = "Enable or disable this texture map"
    if TYPE_CHECKING:
        bl_options: set[OperatorTypeFlagItems]
        map_id: str
    else:
        # The clicked button supplies this argument; HIDDEN keeps it out of automatic forms.
        map_id: EnumProperty(items=MAP_ITEMS, options={'HIDDEN'})
    # REGISTER records the action; UNDO lets Blender include its changes in undo history.
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context: Context) -> OperatorResult:
        settings = cast(_SceneWithBakeSettings, context.scene).bwt_bake_settings
        # Symmetric difference adds an unselected map or removes a selected one.
        settings.maps = set(settings.maps) ^ {self.map_id}
        return {'FINISHED'}


class BWT_OT_batch_bake_materials(Operator):
    bl_idname: str = "bwt.batch_bake_materials"
    bl_label: str = "Bake Selected Materials"
    bl_description: str = "Bake textures and create corresponding baked materials in this blend"
    if TYPE_CHECKING:
        bl_options: set[OperatorTypeFlagItems]
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context) -> bool:
        # Blender checks poll before running the action and disables its button when false.
        # context describes the current scene, mode, selection, window, and other UI state.
        if context.scene is None or context.mode != 'OBJECT':
            cls.poll_message_set("Switch to Object Mode to bake materials")
            return False
        if not hasattr(context.scene, 'cycles'):
            cls.poll_message_set("Cycles must be available to bake materials")
            return False
        return True

    def execute(self, context: Context) -> OperatorResult:
        # execute runs on button activation. Read the current Scene's settings at that time.
        settings = cast(_SceneWithBakeSettings, context.scene).bwt_bake_settings
        # Use a fixed map order rather than the unordered enum flag set.
        maps: tuple[str, ...] = tuple(item[0] for item in MAP_ITEMS if item[0] in settings.maps)
        if not maps:
            self.report({'ERROR'}, "Select at least one texture map")
            return {'CANCELLED'}

        # Snapshot image identities so a failed batch can report any completed output it kept.
        before = {image.name: image.as_pointer() for image in bpy.data.images}
        window = cast(Window | None, context.window)
        if window:
            window.cursor_set('WAIT')
        try:
            # The baking engine handles the scene work; this operator handles UI feedback.
            baked = bake_current_scene(
                size=settings.size, samples=settings.samples, margin=settings.margin,
                selected_only=settings.selected_only, maps=maps,
            )
        except (BakeError, ValueError, RuntimeError) as error:
            completed = sum(before.get(image.name) != image.as_pointer() for image in bpy.data.images)
            if completed:
                # FINISHED creates an undo step for images kept from earlier bakes.
                self.report({'WARNING'}, f"Bake stopped: {error}. Kept {completed} completed image(s); baked materials may need updating")
                return {'FINISHED'}
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        finally:
            # Reset the busy cursor even if baking raises an error.
            if window:
                window.cursor_set('DEFAULT')

        count = sum(len(images) for images in baked.values())
        if not count:
            self.report({'WARNING'}, "No visible meshes to bake; select a mesh or disable Selected Meshes Only")
            return {'CANCELLED'}
        self.report({'INFO'}, f"Baked {count} image(s) from {len(baked)} mesh(es). Corresponding baked materials created")
        return {'FINISHED'}


class BWT_OT_toggle_baked_materials(Operator):
    """Restore saved source slots or assign each object's corresponding bake."""
    bl_idname = "bwt.toggle_baked_materials"
    bl_label = "Original/Baked materials"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context) -> bool:
        return context.mode == 'OBJECT'

    def execute(self, context: Context) -> OperatorResult:
        try:
            state = toggle_materials(target_objects(context))
        except (ValueError, RuntimeError) as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        self.report({'INFO'}, f"{state} materials active")
        return {'FINISHED'}


# A Panel describes a section of Blender's interface; its draw method builds the controls.
class BWT_PT_batch_bake_materials(Panel):
    bl_label: str = "Batch Material Bake"
    bl_idname: str = "BWT_PT_batch_bake_materials"
    if TYPE_CHECKING:
        bl_space_type: SpaceTypeItems
        bl_region_type: RegionTypeItems
    # Show in the 3D Viewport's sidebar (N key), under the Workflow tab.
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category: str = "Workflow"

    def draw(self, context: Context) -> None:
        # Blender calls draw repeatedly to refresh the UI; baking happens only in execute.
        layout: UILayout | None = self.layout
        if layout is None:
            return
        settings = cast(_SceneWithBakeSettings, context.scene).bwt_bake_settings
        # prop creates an editable control bound directly to a Blender property.
        layout.prop(settings, "selected_only")
        # A column stacks controls vertically; align=True joins adjacent control edges.
        column = layout.column(align=True)
        column.prop(settings, "size")
        column.prop(settings, "samples")
        column.prop(settings, "margin")
        layout.label(text="Texture Maps")
        maps_column = layout.column(align=True)
        # Separate operator buttons toggle each flag without the expanded enum's Shift behavior.
        for map_id, label, _, _bit in MAP_ITEMS:
            toggle = maps_column.operator(
                BWT_OT_toggle_texture_map.bl_idname,
                text=label, depress=map_id in settings.maps,
            )
            # operator() returns the future action's arguments, not an executed action.
            # depress above displays whether this map is currently selected.
            toggle.map_id = map_id
        layout.separator()
        layout.operator(BWT_OT_batch_bake_materials.bl_idname)
        layout.operator(BWT_OT_toggle_baked_materials.bl_idname)
        layout.label(text="Active UV map required", icon='INFO')
        layout.label(text="Save .blend to keep baked images")


def _clear_user_results(self, context) -> None:
    self.results = ''
    self.result_target = ''


def _change_user_type(self, context) -> None:
    self.target_name = ''
    _clear_user_results(self, context)


class BWT_PG_data_user_settings(PropertyGroup):
    data_type: EnumProperty(
        name="Type", items=DATA_TYPE_ITEMS, default='images', update=_change_user_type,
    )
    # A string avoids making this tool itself a user of the selected data-block.
    target_name: StringProperty(name="Data-block", update=_clear_user_results)
    results: StringProperty(options={'SKIP_SAVE'})
    result_target: StringProperty(options={'SKIP_SAVE'})


class _SceneWithDataUserSettings(Protocol):
    bwt_data_user_settings: BWT_PG_data_user_settings


class BWT_OT_find_data_users(Operator):
    bl_idname = "bwt.find_data_users"
    bl_label = "Find Users"
    bl_description = "List direct data-block users in this panel and Blender's Info editor"

    def execute(self, context: Context) -> OperatorResult:
        settings = cast(_SceneWithDataUserSettings, context.scene).bwt_data_user_settings
        _clear_user_results(settings, context)
        try:
            target, users = find_data_users(settings.data_type, settings.target_name)
        except ValueError as error:
            self.report({'WARNING'}, str(error))
            return {'CANCELLED'}
        settings.result_target = target
        settings.results = '\n'.join(users) if users else 'No direct data-block users found.'
        self.report({'INFO'}, f'Direct users of {target} ({len(users)}):')
        for user in users:
            self.report({'INFO'}, user)
        if not users:
            self.report({'INFO'}, settings.results)
        return {'FINISHED'}


class BWT_PT_data_users(Panel):
    bl_label = "Data-block Users"
    bl_idname = "BWT_PT_data_users"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Workflow"

    def draw(self, context: Context) -> None:
        layout = self.layout
        if layout is None:
            return
        settings = cast(_SceneWithDataUserSettings, context.scene).bwt_data_user_settings
        layout.prop(settings, "data_type")
        layout.prop_search(settings, "target_name", bpy.data, settings.data_type)
        row = layout.row()
        row.enabled = bool(settings.target_name)
        row.operator(BWT_OT_find_data_users.bl_idname, icon='VIEWZOOM')
        layout.label(text="Direct references only", icon='INFO')
        if settings.result_target:
            box = layout.box()
            box.label(text=settings.result_target)
            for line in settings.results.splitlines():
                box.label(text=line)
            layout.label(text="Run Find Users again to refresh")


# Define dependencies first so the settings and actions exist before the panel uses them.
CLASSES: tuple[type[PropertyGroup] | type[Operator] | type[Panel], ...] = (
    BWT_PG_bake_settings, BWT_OT_toggle_texture_map,
    BWT_OT_batch_bake_materials,
    BWT_OT_toggle_baked_materials, BWT_PT_batch_bake_materials,
    BWT_PG_data_user_settings, BWT_OT_find_data_users, BWT_PT_data_users,
)

