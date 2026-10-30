"""Bake per-object texture maps for the Batch Material Baker add-on.

Also usable directly in Blender's Text Editor or from Python via bake_current_scene.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from contextlib import contextmanager
import re
from types import ModuleType
from typing import TYPE_CHECKING, Literal, Protocol, TypeAlias, TypedDict, cast

if TYPE_CHECKING:
    from bpy.types import (
        Image, Material, Mesh, NodeSocketColor, NodeSocketFloat, Object, Scene,
        ShaderNodeBsdfPrincipled, ShaderNodeEmission, ShaderNodeOutputMaterial,
        ShaderNodeTexImage, ShaderNodeTree, ViewLayer,
    )

BakeResult: TypeAlias = dict[str, dict[str, "Image"]]


class BakeSettings(TypedDict):
    size: int
    samples: int
    margin: int
    selected_only: bool
    maps: tuple[str, ...]


class _CyclesSettings(Protocol):
    """Cycles properties registered dynamically by Blender's Cycles add-on."""

    samples: int
    device: Literal['CPU', 'GPU']


class _RenderSettings(Protocol):
    """Available engines include those registered by render-engine add-ons."""

    engine: str


class _ColorSpaceSettings(Protocol):
    """Color-space names come from the active OCIO configuration at runtime."""

    name: str


MAP_INPUTS: dict[str, str] = {
    "BaseColor": "Base Color", "Roughness": "Roughness",
    "Metallic": "Metallic", "Alpha": "Alpha",
}
MAP_TYPES: tuple[str, ...] = (*MAP_INPUTS, "Normal", "AO", "Emission")
DEFAULT_MAPS: tuple[str, ...] = ("BaseColor", "Normal", "Roughness", "Metallic")


class BakeError(Exception):
    """An expected input or baking failure."""


# Edit these settings before using Text Editor > Run Script (Alt-P).
SETTINGS: BakeSettings = {
    "size": 1024, "samples": 32, "margin": 16, "selected_only": True, "maps": DEFAULT_MAPS,
}


def image_names(
    object_name: str, maps: Iterable[str],
) -> dict[str, str]:
    """Use stable target names so repeated bakes replace the same images."""
    name = re.sub(r"[^A-Za-z0-9_-]", "_", object_name) or "Object"
    return {kind: f"{name}_{kind}" for kind in maps}


def material_tree(material: Material) -> ShaderNodeTree:
    tree = material.node_tree
    if not material.use_nodes or tree is None:
        raise BakeError(f"Material '{material.name}' must use nodes")
    return tree


def material_output(material: Material) -> ShaderNodeOutputMaterial:
    output = cast("ShaderNodeOutputMaterial | None", material_tree(material).get_output_node('CYCLES'))
    if output is None or output.inputs is None or not output.inputs['Surface'].is_linked:
        raise BakeError(f"Material '{material.name}' has no connected Cycles surface output")
    return cast("ShaderNodeOutputMaterial", output)


def principled_input(material: Material, kind: str) -> NodeSocketColor | NodeSocketFloat:
    output = material_output(material)
    inputs = output.inputs
    if inputs is None:
        raise BakeError(f"Material '{material.name}' has no surface inputs")
    shader = inputs['Surface'].links[0].from_node
    if shader.type != 'BSDF_PRINCIPLED':
        raise BakeError(
            f"{material.name}: {kind} requires a Principled BSDF connected directly to Material Output; "
            "mixed shaders and shader groups are not supported for these maps"
        )
    shader = cast("ShaderNodeBsdfPrincipled", shader)
    shader_inputs = shader.inputs
    socket = shader_inputs.get(MAP_INPUTS[kind]) if shader_inputs is not None else None
    if socket is None:
        raise BakeError(f"Material '{material.name}' has no {MAP_INPUTS[kind]} input")
    return cast("NodeSocketColor | NodeSocketFloat", socket)


@contextmanager
def bake_sources(bpy: ModuleType, obj: Object) -> Iterator[None]:
    """Copy each distinct source once per object and reuse it across all maps.

    Object-local overrides protect other meshes using the same materials. Every
    source needs an active bake target because Blender evaluates its own graph.
    """
    originals: list[tuple[Literal["OBJECT", "DATA"], Material | None]] = [
        (slot.link, slot.material) for slot in obj.material_slots
    ]
    copies = {}
    try:
        for slot, (_, original) in zip(obj.material_slots, originals):
            original = cast("Material", original)
            key = original.as_pointer()
            if key not in copies:
                material = original.copy()
                copies[key] = material
                tree = material_tree(material)
                target = tree.nodes.new('ShaderNodeTexImage')
                target["bwt_bake_target"] = True
                tree.nodes.active = target
            slot.link = 'OBJECT'
            slot.material = copies[key]
        yield
    finally:
        for slot, (link, material) in zip(obj.material_slots, originals):
            slot.link = link
            slot.material = material
        for material in copies.values():
            bpy.data.materials.remove(material)


@contextmanager
def bake_materials(
    bpy: ModuleType, obj: Object, image: Image, kind: str,
) -> Iterator[None]:
    """Retarget prepared copies for one pass and restore their source outputs.

    Reuse the same Image Texture node for every map. Only scalar/color passes
    need an emission adapter to bake values without scene lighting.
    """
    restored = []
    seen = set()
    try:
        for slot in obj.material_slots:
            material = cast("Material", slot.material)
            if material.as_pointer() in seen:
                continue
            seen.add(material.as_pointer())
            tree = material_tree(material)
            output = material_output(material)
            assert output.inputs is not None
            surface = output.inputs['Surface']
            source_output = surface.links[0].from_socket
            emission = None
            if kind in MAP_INPUTS:
                source = principled_input(material, kind)
                emission = cast("ShaderNodeEmission", tree.nodes.new('ShaderNodeEmission'))
                restored.append((tree, surface, source_output, emission))
                assert emission.inputs is not None and emission.outputs is not None
                if source.is_linked:
                    tree.links.new(source.links[0].from_socket, emission.inputs['Color'])
                else:
                    value = source.default_value
                    color = (tuple(cast(Iterable[float], value)) if kind == 'BaseColor'
                             else (cast(float, value),) * 3 + (1.0,))
                    emission.inputs['Color'].default_value[:] = color
                tree.links.new(emission.outputs[0], surface)
            target = cast("ShaderNodeTexImage", next(
                node for node in tree.nodes if node.get("bwt_bake_target")
            ))
            target.image = image
            tree.nodes.active = target
        yield
    finally:
        for tree, surface, source_output, emission in restored:
            tree.links.new(source_output, surface)
            tree.nodes.remove(emission)


def bake_current_scene(
    *, size: int = 1024, samples: int = 32, margin: int = 16,
    selected_only: bool = True, maps: Iterable[str] = DEFAULT_MAPS,
) -> BakeResult:
    """Return {object_name: {map_type: Image}}; do not load or save any files."""
    for name, value, minimum in (("size", size, 1), ("samples", samples, 1), ("margin", margin, 0)):
        if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
            raise BakeError(f"{name} must be an integer >= {minimum}")
    if isinstance(maps, str):
        raise BakeError("maps must be a sequence of map names, not a string")
    maps = tuple(dict.fromkeys(maps))
    if not maps or any(kind not in MAP_TYPES for kind in maps):
        raise BakeError(f"Choose at least one map from {MAP_TYPES}")
    import bpy  # pyright: ignore[reportMissingModuleSource]

    if bpy.context.mode != 'OBJECT':
        raise BakeError("Switch to Object Mode before baking")
    scene = cast("Scene | None", bpy.context.scene)
    layer = cast("ViewLayer | None", bpy.context.view_layer)
    if scene is None or layer is None:
        raise BakeError("Baking requires an active scene and view layer")
    selected: list[Object] = list(bpy.context.selected_objects)
    active: Object | None = layer.objects.active
    candidates = selected if selected_only else list(layer.objects)
    objects: list[Object] = sorted(
        (obj for obj in candidates if obj.type == 'MESH' and obj.visible_get()),
        key=lambda obj: obj.name,
    )
    if not objects:
        print("Nothing baked: no visible meshes in the requested selection.")
        return {}
    # Validate the whole batch before spending time baking it.
    uv_names: dict[str, str] = {}
    target_owners: dict[str, str] = {}
    for obj in objects:
        for name in image_names(obj.name, maps).values():
            if name in target_owners:
                raise BakeError(f"{obj.name} and {target_owners[name]} share image target '{name}'; rename an object")
            target_owners[name] = obj.name
            existing = bpy.data.images.get(name)
            if existing is not None and existing.library is not None:
                raise BakeError(f"Image '{name}' is linked from a library; make it local before replacing it")
        if obj.get("bwt_original_slots") is not None:
            raise BakeError(f"{obj.name}: toggle back to source materials before rebaking")
        mesh = cast("Mesh", obj.data)  # Objects were filtered to type MESH above.
        uv_layer = mesh.uv_layers.active
        if not mesh.polygons or uv_layer is None:
            raise BakeError(f"{obj.name}: requires mesh faces and an active UV map; unwrap it before baking")
        uv_names[obj.name] = uv_layer.name
        if not obj.material_slots or any(slot.material is None for slot in obj.material_slots):
            raise BakeError(f"{obj.name}: every material slot must have a material")
        for slot in obj.material_slots:
            material = cast("Material", slot.material)  # All slots were validated above.
            material_output(material)
            for kind in maps:
                if kind in MAP_INPUTS:
                    principled_input(material, kind)

    cycles = cast(_CyclesSettings, getattr(scene, "cycles"))
    render = cast(_RenderSettings, scene.render)
    engine, original_samples, device = render.engine, cycles.samples, cycles.device
    baked: BakeResult = {}
    try:
        # Temporarily use Cycles and make each mesh the sole selected bake target in turn.
        render.engine = 'CYCLES'
        cycles.samples = samples
        cycles.device = 'CPU'
        for obj in selected:
            obj.select_set(False)
        for obj in objects:
            names = image_names(obj.name, maps)
            baked[obj.name] = {}
            locked, hidden = obj.hide_select, obj.hide_render
            try:
                obj.hide_select = False
                obj.hide_render = False
                obj.select_set(True)
                layer.objects.active = obj
                with bake_sources(bpy, obj):
                    for kind, name in names.items():
                        # Bake into a temporary image so failure leaves the old pixels intact.
                        previous = bpy.data.images.get(name)
                        image = bpy.data.images.new(name, width=size, height=size,
                                                    alpha=False, float_buffer=False)
                        try:
                            colorspace = image.colorspace_settings
                            if colorspace is None:
                                raise BakeError(f"Could not access color-space settings for '{image.name}'")
                            # Color maps use sRGB; numeric data maps must avoid color conversion.
                            cast(_ColorSpaceSettings, colorspace).name = (
                                'sRGB' if kind in ('BaseColor', 'Emission') else 'Non-Color'
                            )
                            # Normal and AO use dedicated passes; other maps use emission.
                            bake_type: Literal['NORMAL', 'AO', 'EMIT'] = (
                                'NORMAL' if kind == 'Normal' else 'AO' if kind == 'AO' else 'EMIT'
                            )
                            with bake_materials(bpy, obj, image, kind):
                                result = bpy.ops.object.bake(
                                    type=bake_type,
                                    target='IMAGE_TEXTURES', use_selected_to_active=False,
                                    use_clear=True, use_cage=False, margin=margin,
                                    normal_space='TANGENT', normal_r='POS_X', normal_g='POS_Y', normal_b='POS_Z',
                                    uv_layer=uv_names[obj.name],
                                )
                                if result != {'FINISHED'}:
                                    raise BakeError(f"Bake failed: {obj.name} / {kind}")
                            # Keep pixels in the .blend when saved, and retain the image even though
                            # the reusable source copies are removed after all maps complete.
                            image.pack()
                            image.use_fake_user = True
                        except BaseException:
                            # Discard only the failed image; completed maps remain available.
                            bpy.data.images.remove(image)
                            raise
                        # Commit only after baking and packing succeed. Remap material nodes,
                        # object custom properties, and other users before removing the old ID.
                        if previous is not None:
                            previous.user_remap(image)
                            bpy.data.images.remove(previous)
                        image.name = name
                        baked[obj.name][kind] = image
                        print(f"Baked image: {image.name}", flush=True)
                # Publish a complete map set. If a later map fails, earlier replacements
                # remain committed while the failed map retains its previous image.
                obj["bwt_bake_images"] = dict(baked[obj.name])
                obj["bwt_bake_uv"] = uv_names[obj.name]
                # Commit the shader immediately for each completed object, including
                # earlier objects when a later object fails in the same batch.
                from .baked_materials import create_materials
                create_materials([obj])
            finally:
                obj.select_set(False)
                obj.hide_select, obj.hide_render = locked, hidden
    finally:
        # Return the user's render settings, selection, and active object after success or failure.
        render.engine, cycles.samples, cycles.device = engine, original_samples, device
        for obj in selected:
            obj.select_set(True)
        layer.objects.active = active
    print(f"Baked {sum(len(images) for images in baked.values())} image(s) in the current session")
    return baked


if __name__ == '__main__':
    baked_images = bake_current_scene(**SETTINGS)
