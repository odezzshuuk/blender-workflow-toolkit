"""Switch between a single baked slot and the saved source assignments."""

import bpy


def target_objects(context):
    """Use the same visible-mesh scope as the baking controls."""
    candidates = (context.selected_objects if context.scene.bwt_bake_settings.selected_only
                  else context.view_layer.objects)
    return [obj for obj in candidates if obj.type == 'MESH' and obj.visible_get()]


def toggle_materials(objects):
    """Switch a batch to baked materials, or restore it when every object is baked.

    Save slot linkage, mesh materials, and polygon indices before collapsing slots.
    Shared meshes become independent so other objects retain their assignments.
    Original material ID references survive renaming and saving the blend file.
    """
    if not objects:
        raise ValueError("No visible meshes in the requested scope")
    restore = all(obj.get("bwt_original_slots") is not None for obj in objects)
    # Validate the whole batch before changing any assignments.
    for obj in objects:
        saved = obj.get("bwt_original_slots")
        indices = obj.get("bwt_original_material_indices")
        if saved is not None:
            if indices is None and len(saved) != len(obj.material_slots):
                raise ValueError(f"{obj.name}: material slot count changed; restore slots first")
            if indices is not None and len(indices) != len(obj.data.polygons):
                raise ValueError(f"{obj.name}: face count changed; cannot restore original face assignments")
        if not restore and obj.get("bwt_baked_material") is None:
            raise ValueError(f"{obj.name}: create its baked material first")
        if not obj.material_slots:
            raise ValueError(f"{obj.name}: no material slots")

    for obj in objects:
        saved = obj.get("bwt_original_slots")
        if restore:
            indices = obj.get("bwt_original_material_indices")
            if indices is not None:
                if obj.data.users > 1:
                    obj.data = obj.data.copy()
                obj.data.materials.clear()
                for i in range(len(saved)):
                    obj.data.materials.append(saved[str(i)].get("data_material"))
                for polygon, index in zip(obj.data.polygons, indices):
                    polygon.material_index = index
            # Older saved blends used object overrides without collapsing slots.
            for i, slot in enumerate(obj.material_slots):
                entry = saved[str(i)]
                slot.link = entry["link"]
                slot.material = entry.get("material")
            if indices is not None:
                obj.active_material_index = obj["bwt_original_active_slot"]
                del obj["bwt_original_material_indices"]
                del obj["bwt_original_active_slot"]
            del obj["bwt_original_slots"]
        elif saved is None:
            obj["bwt_original_slots"] = {
                str(i): {"link": slot.link,
                         **({"material": slot.material} if slot.material else {}),
                         **({"data_material": obj.data.materials[i]} if obj.data.materials[i] else {})}
                for i, slot in enumerate(obj.material_slots)
            }
            obj["bwt_original_material_indices"] = [p.material_index for p in obj.data.polygons]
            obj["bwt_original_active_slot"] = obj.active_material_index
            if obj.data.users > 1:
                obj.data = obj.data.copy()
            obj.data.materials.clear()
            obj.data.materials.append(obj["bwt_baked_material"])
            obj.material_slots[0].link = 'DATA'
            for polygon in obj.data.polygons:
                polygon.material_index = 0
            obj.active_material_index = 0
    return "Source" if restore else "Baked"
