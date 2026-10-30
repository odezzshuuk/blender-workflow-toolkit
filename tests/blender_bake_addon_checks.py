"""Run in a disposable Blender process; test the packaged add-on, not the live scene.

blender --background --factory-startup --python-exit-code 1 \
    --python tests/blender_bake_addon_checks.py
"""

import importlib.util
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import Mock, patch
import zipfile

import bpy


def check_rejected(message):
    before = set(bpy.data.images.keys())
    try:
        result = bpy.ops.bwt.batch_bake_materials()
    except RuntimeError as error:
        assert message in str(error), error
    else:
        assert result == {'CANCELLED'}, result
    assert set(bpy.data.images.keys()) == before


def check_data_users(addon):
    assert bpy.types.BWT_PT_data_users.is_registered
    settings = bpy.context.scene.bwt_data_user_settings
    image = bpy.data.images.new('users_probe_image', width=1, height=1)
    material = bpy.data.materials.new('users_probe_material')
    material.use_nodes = True
    material.node_tree.nodes.new('ShaderNodeTexImage').image = image
    group = bpy.data.node_groups.new('users_probe_group', 'ShaderNodeTree')
    group.nodes.new('ShaderNodeTexImage').image = image
    material.node_tree.nodes.new('ShaderNodeGroup').node_tree = group
    mesh = bpy.data.meshes.new('users_probe_mesh')
    mesh.materials.append(material)
    obj = bpy.data.objects.new('users_probe_object', mesh)
    bpy.context.collection.objects.link(obj)

    before = image.users
    settings.target_name = image.name
    with patch('builtins.print') as terminal_print:
        assert bpy.ops.bwt.find_data_users() == {'FINISHED'}
        terminal_print.assert_not_called()
    # Exercise execute with a report sink to verify the names reach Blender's Info reports.
    reporter = SimpleNamespace(report=Mock())
    assert addon.ui.BWT_OT_find_data_users.execute(reporter, bpy.context) == {'FINISHED'}
    reports = [call.args[1] for call in reporter.report.call_args_list]
    assert all(call.args[0] == {'INFO'} for call in reporter.report.call_args_list)
    assert reports == [
        f'Direct users of {settings.result_target} (2):',
        *settings.results.splitlines(),
    ]
    assert any(material.name in report for report in reports)
    assert any(group.name in report for report in reports)
    assert obj.name not in settings.results, 'Only direct references should appear'
    assert image.users == before, 'Selecting a target must not add a user'
    for kind, target, expected in (
        ('materials', material, mesh), ('meshes', mesh, obj),
        ('node_groups', group, material),
    ):
        settings.data_type = kind
        assert not settings.target_name and not settings.results
        settings.target_name = target.name
        assert bpy.ops.bwt.find_data_users() == {'FINISHED'}
        assert expected.name in settings.results
    settings.data_type = 'images'
    unused = bpy.data.images.new('users_probe_unused', width=1, height=1)
    unused.use_fake_user = True
    settings.target_name = unused.name
    assert bpy.ops.bwt.find_data_users() == {'FINISHED'}
    assert settings.results == 'No direct data-block users found.'
    reporter.report.reset_mock()
    assert addon.ui.BWT_OT_find_data_users.execute(reporter, bpy.context) == {'FINISHED'}
    reporter.report.assert_any_call({'INFO'}, 'No direct data-block users found.')
    bpy.data.images.remove(unused)
    assert bpy.ops.bwt.find_data_users() == {'CANCELLED'}
    assert not settings.results and not settings.result_target
    settings.target_name = ''
    assert bpy.ops.bwt.find_data_users() == {'CANCELLED'}
    bpy.data.objects.remove(obj, do_unlink=True)
    bpy.data.meshes.remove(mesh)
    bpy.data.materials.remove(material)
    bpy.data.node_groups.remove(group)
    bpy.data.images.remove(image)
    print('PASS: data users, image nodes, node groups, other types, unused and deleted targets')


def run_checks(addon, directory):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    initial_images = set(bpy.data.images.keys())
    addon.register()
    assert set(bpy.data.images.keys()) == initial_images, "Enabling must not bake"
    assert bpy.types.BWT_PT_batch_bake_materials.is_registered
    assert set(bpy.context.scene.bwt_bake_settings.maps) == set(addon.ui.DEFAULT_MAPS)
    check_data_users(addon)

    settings = bpy.context.scene.bwt_bake_settings
    settings.maps = set()
    selected_maps = set()
    for map_id, *_ in addon.ui.MAP_ITEMS:
        assert bpy.ops.bwt.toggle_texture_map(map_id=map_id) == {'FINISHED'}
        selected_maps.add(map_id)
        assert set(settings.maps) == selected_maps
    for map_id, *_ in addon.ui.MAP_ITEMS:
        assert bpy.ops.bwt.toggle_texture_map(map_id=map_id) == {'FINISHED'}
        selected_maps.remove(map_id)
        assert set(settings.maps) == selected_maps
    settings.maps = set(addon.ui.DEFAULT_MAPS)

    bpy.ops.mesh.primitive_cube_add()
    obj = bpy.context.object
    obj.name = 'character_body'
    material = bpy.data.materials.new('character_skin')
    material.use_nodes = True
    shader = material.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (0.8, 0.1, 0.05, 1)
    shader.inputs['Metallic'].default_value = 1
    shader.inputs['Roughness'].default_value = 0.35
    obj.data.materials.append(material)
    # An unselected mesh without materials/UVs must be ignored by selected-only baking.
    ignored = bpy.data.objects.new('unselected', bpy.data.meshes.new('unselected'))
    bpy.context.collection.objects.link(ignored)
    scene = bpy.context.scene
    original_settings = (scene.render.engine, scene.cycles.samples, scene.cycles.device)
    settings = scene.bwt_bake_settings
    settings.size, settings.samples, settings.margin = 32, 1, 1
    settings.maps = {item[0] for item in addon.ui.MAP_ITEMS}
    assert bpy.ops.bwt.batch_bake_materials() == {'FINISHED'}
    assert bpy.data.filepath == '', "Baking must not open or save a project"
    for kind in settings.maps:
        image = bpy.data.images.get(f'character_body_{kind}')
        assert image is not None, kind
        assert image.packed_file and image.use_fake_user, kind
        assert tuple(image.size) == (32, 32)
        red = max(list(image.pixels)[::4])
        if kind == 'BaseColor':
            assert red > 0.7, red
        elif kind == 'Metallic':
            assert red > 0.95, red
        elif kind == 'Roughness':
            assert abs(red - 0.35) < 0.03, red
    assert obj.material_slots[0].material == material
    assert obj.material_slots[0].link == 'DATA'
    assert len(material.node_tree.nodes) == 2
    assert bpy.context.view_layer.objects.active == obj and obj.select_get()
    assert (scene.render.engine, scene.cycles.samples, scene.cycles.device) == original_settings

    # The combined bake action creates a local material; switching preserves source slots.
    assert not bpy.data.libraries
    baked_material = obj["bwt_baked_material"]
    assert baked_material.name == obj.name + "_baked"
    assert obj.material_slots[0].material == material
    assert bpy.ops.bwt.toggle_baked_materials() == {'FINISHED'}
    assert obj.material_slots[0].material == baked_material
    assert bpy.ops.bwt.toggle_baked_materials() == {'FINISHED'}
    assert obj.material_slots[0].material == material
    assert obj.material_slots[0].link == 'DATA'
    assert obj["bwt_baked_material"] == baked_material

    # Matching final image nodes survive rebaking; source copies are cleaned up.
    base_node = next(node for node in baked_material.node_tree.nodes
                     if node.type == 'TEX_IMAGE' and node.label == 'BaseColor')
    base_pointer = base_node.as_pointer()
    material_count = len(bpy.data.materials)
    old_image = bpy.data.images['character_body_BaseColor']
    old_pointer = old_image.as_pointer()
    old_pixels = list(old_image.pixels)
    names_before = set(bpy.data.images.keys())
    external_group = bpy.data.node_groups.new('external_image_user', 'ShaderNodeTree')
    external_node = external_group.nodes.new('ShaderNodeTexImage')
    external_node.image = old_image
    obj['extra_image_reference'] = old_image
    settings.maps = {'BaseColor'}
    with patch.object(addon.texture_baking, 'bake_materials',
                      side_effect=addon.ui.BakeError('Simulated image bake failure')):
        check_rejected('Simulated image bake failure')
    assert bpy.data.images['character_body_BaseColor'].as_pointer() == old_pointer
    assert list(old_image.pixels) == old_pixels
    assert external_node.image == old_image
    assert obj['extra_image_reference'] == old_image
    shader.inputs['Base Color'].default_value = (0.1, 0.8, 0.05, 1)
    assert bpy.ops.bwt.batch_bake_materials() == {'FINISHED'}
    # Rebaking updates the same material and connects the latest per-object image.
    assert obj["bwt_baked_material"] == baked_material
    image_nodes = [node for node in baked_material.node_tree.nodes if node.type == 'TEX_IMAGE']
    assert len(image_nodes) == 1
    assert image_nodes[0].as_pointer() == base_pointer
    assert len(bpy.data.materials) == material_count
    replacement = bpy.data.images['character_body_BaseColor']
    assert image_nodes[0].image == replacement
    assert replacement.as_pointer() != old_pointer
    assert set(bpy.data.images.keys()) == names_before
    assert list(replacement.pixels) != old_pixels
    assert external_node.image == replacement
    assert obj['extra_image_reference'] == replacement
    assert obj['bwt_bake_images']['BaseColor'] == replacement
    assert replacement.packed_file and replacement.use_fake_user

    # A later failed map preserves its old image while earlier maps stay replaced.
    normal_pointer = bpy.data.images['character_body_Normal'].as_pointer()
    replacement_pointer = replacement.as_pointer()
    real_bake_materials = addon.texture_baking.bake_materials

    def fail_normal(bpy_module, target, image, kind):
        if kind == 'Normal':
            raise addon.ui.BakeError('Simulated second map failure')
        return real_bake_materials(bpy_module, target, image, kind)

    settings.maps = {'BaseColor', 'Normal'}
    with patch.object(addon.texture_baking, 'bake_materials', side_effect=fail_normal):
        assert bpy.ops.bwt.batch_bake_materials() == {'FINISHED'}
    assert bpy.data.images['character_body_Normal'].as_pointer() == normal_pointer
    assert bpy.data.images['character_body_BaseColor'].as_pointer() != replacement_pointer
    assert external_node.image == bpy.data.images['character_body_BaseColor']
    assert set(bpy.data.images.keys()) == names_before

    # Sanitizing two distinct object names must not overwrite one object's bake.
    collision = obj.copy()
    collision.name = 'character.body'
    bpy.context.collection.objects.link(collision)
    collision.select_set(True)
    check_rejected('share image target')
    bpy.data.objects.remove(collision, do_unlink=True)

    settings.maps = set()
    check_rejected('Select at least one')
    settings.maps = {'Normal'}
    settings.selected_only = False
    check_rejected('requires mesh faces')
    settings.selected_only = True
    bpy.ops.object.mode_set(mode='EDIT')
    assert not bpy.ops.bwt.batch_bake_materials.poll()
    bpy.ops.object.mode_set(mode='OBJECT')

    real_bake = addon.ui.bake_current_scene

    def partial_failure(**kwargs):
        real_bake(**kwargs)
        raise addon.ui.BakeError('Simulated failure after a completed image')

    with patch.object(addon.ui, 'bake_current_scene', side_effect=partial_failure):
        # FINISHED ensures the kept image participates in Blender undo.
        assert bpy.ops.bwt.batch_bake_materials() == {'FINISHED'}
    assert 'character_body_Normal' in bpy.data.images
    assert set(bpy.data.images.keys()) == names_before

    # Use the background process context; a fake VIEW_3D override crashes Blender redo UI.
    bpy.ops.ed.undo_push(message='Before material bake')
    print('Undo check: initial state saved', flush=True)
    images_before = set(bpy.data.images.keys())
    settings.size = 16
    assert bpy.ops.bwt.batch_bake_materials('EXEC_DEFAULT', True) == {'FINISHED'}
    print('Undo check: bake finished', flush=True)
    assert set(bpy.data.images.keys()) == images_before
    assert tuple(bpy.data.images['character_body_Normal'].size) == (16, 16)
    assert bpy.ops.ed.undo() == {'FINISHED'}
    print('Undo check: undo finished', flush=True)
    assert set(bpy.data.images.keys()) == images_before
    assert tuple(bpy.data.images['character_body_Normal'].size) == (32, 32)

    image_names = set(bpy.data.images.keys())
    filepath = str(directory / 'packed_bakes.blend')
    bpy.ops.wm.save_as_mainfile(filepath=filepath)
    bpy.ops.wm.open_mainfile(filepath=filepath)
    assert set(bpy.data.images.keys()) == image_names
    assert bpy.data.images['character_body_BaseColor'].packed_file
    assert bpy.context.scene.bwt_bake_settings.size == 32

    addon.unregister()
    assert not hasattr(bpy.types.Scene, 'bwt_bake_settings')
    assert not hasattr(bpy.types.Scene, 'bwt_data_user_settings')
    assert set(bpy.data.images.keys()) == image_names, "Disabling must keep baked images"
    addon.register()
    assert hasattr(bpy.types.Scene, 'bwt_bake_settings')
    addon.unregister()
    print('PASS: packaged add-on registration, seven maps, replacement references, failure recovery, name collisions, undo, persistence, and cleanup')


def check_single_slot_toggle(addon, directory):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_cube_add()
    obj = bpy.context.object
    obj.name = 'multi_material'
    source = bpy.data.materials.new('source')
    override = bpy.data.materials.new('override')
    baked = bpy.data.materials.new('baked')
    obj.data.materials.append(source)
    obj.data.materials.append(source)
    obj.data.materials.append(None)
    obj.material_slots[1].link = 'OBJECT'
    obj.material_slots[1].material = override
    original_indices = [i % 3 for i in range(len(obj.data.polygons))]
    for face, index in zip(obj.data.polygons, original_indices):
        face.material_index = index
    obj.active_material_index = 1
    shared = bpy.data.objects.new('shared_mesh', obj.data)
    bpy.context.collection.objects.link(shared)
    obj['bwt_baked_material'] = baked
    toggle = addon.ui.toggle_materials
    assert toggle([obj]) == 'Baked'
    assert len(obj.material_slots) == 1
    assert obj.material_slots[0].material == baked
    assert all(face.material_index == 0 for face in obj.data.polygons)
    assert obj.data != shared.data
    assert len(shared.material_slots) == 3
    assert [face.material_index for face in shared.data.polygons] == original_indices

    # Restoration metadata must survive saving while the single baked slot is active.
    filepath = str(directory / 'single_slot.blend')
    bpy.ops.wm.save_as_mainfile(filepath=filepath)
    bpy.ops.wm.open_mainfile(filepath=filepath)
    obj = bpy.data.objects['multi_material']
    assert toggle([obj]) == 'Source'
    assert len(obj.material_slots) == 3
    assert obj.material_slots[0].material == bpy.data.materials['source']
    assert obj.material_slots[1].link == 'OBJECT'
    assert obj.material_slots[1].material == bpy.data.materials['override']
    assert obj.data.materials[1] == bpy.data.materials['source']
    assert obj.material_slots[2].material is None
    assert obj.active_material_index == 1
    assert [face.material_index for face in obj.data.polygons] == original_indices
    assert obj.get('bwt_original_slots') is None
    assert toggle([obj]) == 'Baked'
    assert toggle([obj]) == 'Source'
    assert [face.material_index for face in obj.data.polygons] == original_indices
    print('PASS: single baked slot, shared meshes, empty slots, object overrides, and saved restoration')


package = Path(__file__).resolve().parents[1] / 'dist/batch_material_baker.zip'
with tempfile.TemporaryDirectory(prefix='bake-addon-check-') as temp:
    directory = Path(temp)
    source = directory / 'batch_material_baker'
    with zipfile.ZipFile(package) as archive:
        archive.extractall(source)
    spec = importlib.util.spec_from_file_location(
        'batch_material_baker', source / '__init__.py', submodule_search_locations=[str(source)],
    )
    addon = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = addon
    spec.loader.exec_module(addon)
    run_checks(addon, directory)
    check_single_slot_toggle(addon, directory)
