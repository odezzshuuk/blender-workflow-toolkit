"""Build one reusable export material from each object's completed bake set."""

from typing import cast

import bpy
from bpy.types import (ShaderNodeTree, ShaderNodeUVMap, ShaderNodeTexImage,
                       ShaderNodeNormalMap, ShaderNodeGroup, NodeSocketFloat)

INPUTS = {"BaseColor": "Base Color", "Roughness": "Roughness",
          "Metallic": "Metallic", "Alpha": "Alpha", "Emission": "Emission Color"}


def create_materials(objects):
    """Connect baked maps using their recorded UV map, preserving source materials.

    Only completed bake sets are accepted. Existing generated materials are rebuilt
    in place, reusing image nodes so object and texture-node references stay stable. AO is exposed through glTF's
    recognized occlusion group rather than multiplied into the base color.
    """
    if not objects:
        raise ValueError("No visible meshes in the requested scope")
    for obj in objects:
        images = obj.get("bwt_bake_images")
        if not images or any(image is None for image in images.values()):
            raise ValueError(f"{obj.name}: bake textures first")
        if obj.data.uv_layers.get(obj.get("bwt_bake_uv", "")) is None:
            raise ValueError(f"{obj.name}: baked UV map is missing")
    for obj in objects:
        material = obj.get("bwt_baked_material")
        if material is None:
            material = bpy.data.materials.new(f"{obj.name}_baked")
            obj["bwt_baked_material"] = material
        material.use_nodes = True
        # Enabling nodes creates a shader tree; narrow the generic RNA types for tooling.
        tree = cast(ShaderNodeTree, material.node_tree)
        # Keep matching image nodes so rebakes update their image references in place.
        # Rebuild only the small shader wiring; discard maps absent from the new set.
        image_nodes = {node.label: node for node in tree.nodes
                       if node.type == 'TEX_IMAGE' and node.label in obj["bwt_bake_images"]}
        for existing in list(tree.nodes):
            if existing not in image_nodes.values():
                tree.nodes.remove(existing)
        output = tree.nodes.new("ShaderNodeOutputMaterial")
        shader = tree.nodes.new("ShaderNodeBsdfPrincipled")
        tree.links.new(shader.outputs["BSDF"], output.inputs["Surface"])
        uv = cast(ShaderNodeUVMap, tree.nodes.new("ShaderNodeUVMap"))
        assert uv.outputs is not None
        uv.uv_map = obj["bwt_bake_uv"]
        for index, (kind, image) in enumerate(obj["bwt_bake_images"].items()):
            texture = cast(ShaderNodeTexImage, image_nodes.get(kind))
            if texture is None:
                texture = cast(ShaderNodeTexImage, tree.nodes.new("ShaderNodeTexImage"))
            assert texture.inputs is not None and texture.outputs is not None
            texture.image = image
            texture.label = kind
            texture.location = (-600, -index * 260)
            tree.links.new(uv.outputs["UV"], texture.inputs["Vector"])
            if kind == "Normal":
                normal = cast(ShaderNodeNormalMap, tree.nodes.new("ShaderNodeNormalMap"))
                assert normal.inputs is not None and normal.outputs is not None
                normal.uv_map = uv.uv_map
                tree.links.new(texture.outputs["Color"], normal.inputs["Color"])
                tree.links.new(normal.outputs["Normal"], shader.inputs["Normal"])
            elif kind == "AO":
                group = cast(ShaderNodeTree | None, bpy.data.node_groups.get("glTF Material Output"))
                if group is None:
                    # Blender registers shader-tree enum values dynamically; stubs list only DUMMY.
                    group = cast(ShaderNodeTree, bpy.data.node_groups.new("glTF Material Output", "ShaderNodeTree"))  # pyright: ignore[reportArgumentType]
                    assert group.interface is not None
                    group.interface.new_socket(name="Occlusion", in_out='INPUT', socket_type='NodeSocketFloat')
                node = cast(ShaderNodeGroup, tree.nodes.new("ShaderNodeGroup"))
                node.node_tree = group
                if node.inputs.get("Occlusion") is not None:
                    tree.links.new(texture.outputs["Color"], node.inputs["Occlusion"])
            elif kind in INPUTS:
                tree.links.new(texture.outputs["Color"], shader.inputs[INPUTS[kind]])
                if kind == "Emission":
                    cast(NodeSocketFloat, shader.inputs["Emission Strength"]).default_value = 1.0
        shader.location = (0, 0)
        output.location = (300, 0)
    return len(objects)
