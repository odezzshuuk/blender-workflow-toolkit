"""Find direct data-block references without adding a reference to the target."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from bpy.types import ID


DATA_TYPE_ITEMS = (
    ('images', 'Images', 'Image data'),
    ('materials', 'Materials', 'Material data'),
    ('objects', 'Objects', 'Scene objects'),
    ('meshes', 'Meshes', 'Mesh data'),
    ('node_groups', 'Node Groups', 'Shared node trees'),
    ('textures', 'Textures', 'Texture data'),
    ('collections', 'Collections', 'Object collections'),
    ('worlds', 'Worlds', 'World data'),
    ('scenes', 'Scenes', 'Scene data'),
    ('actions', 'Actions', 'Animation actions'),
    ('armatures', 'Armatures', 'Armature data'),
    ('curves', 'Curves', 'Curve and text data'),
    ('cameras', 'Cameras', 'Camera data'),
    ('lights', 'Lights', 'Light data'),
    ('sounds', 'Sounds', 'Sound data'),
    ('fonts', 'Fonts', 'Vector fonts'),
)


def data_block_label(block: ID) -> str:
    """Include type and library to distinguish similarly named users."""
    library = f' [Library: {block.library.filepath}]' if block.library else ''
    return f'{getattr(block.bl_rna, "name")}: {block.name}{library}'


def find_data_users(collection_name: str, name: str) -> tuple[str, list[str]]:
    """Return the target label and sorted direct users from Blender's user map."""
    import bpy

    if collection_name not in {item[0] for item in DATA_TYPE_ITEMS}:
        raise ValueError('Choose a supported data-block type')
    collection = getattr(bpy.data, collection_name)
    matches = [block for block in collection if block.name == name]
    if not matches:
        raise ValueError('Choose an existing data-block')
    if len(matches) > 1:
        raise ValueError('Multiple libraries contain this name; use a uniquely named data-block')
    target = matches[0]
    # The 4.2 stubs incorrectly require optional filters; empty filters exclude all IDs.
    user_map = cast('Callable[..., dict[ID, set[ID]]]', bpy.data.user_map)
    users = user_map(subset={target}).get(target, set())
    return data_block_label(target), sorted(
        (data_block_label(user) for user in users), key=str.casefold,
    )
