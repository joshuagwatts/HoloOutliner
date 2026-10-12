"""Holo Outliner - C4D-style Object Manager for Blender.

Single-hierarchy tree (real parenting only, collections ignored for display),
C4D tri-state visibility dots (viewport + render), click/shift/ctrl selection
synced with the 3D view, F2 rename, viewport solo, and one-click grouping.
"""

bl_info = {
    "name": "Holo Outliner",
    "author": "Holowatts",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "location": "Outliner > Sidebar (N) > Holo",
    "description": "C4D-style Object Manager: single-hierarchy tree, tri-state "
                   "visibility dots, viewport solo, quick grouping",
    "category": "Interface",
}

import bpy
from bpy.app.handlers import persistent

from . import core
from . import ops
from . import ui


@persistent
def _ho_load_post(_dummy):
    scene = bpy.context.scene
    if scene is not None:
        core.apply_visibility(scene)


_addon_keymaps = []


def _register_keymaps():
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc is None:
        return
    km = kc.keymaps.new(name="Outliner", space_type="OUTLINER")
    kmi = km.keymap_items.new("ho.rename", type="F2", value="PRESS")
    _addon_keymaps.append((km, kmi))


def _unregister_keymaps():
    for km, kmi in _addon_keymaps:
        km.keymap_items.remove(kmi)
    _addon_keymaps.clear()


def register():
    ops.register()
    ui.register()
    if _ho_load_post not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_ho_load_post)
    _register_keymaps()


def unregister():
    _unregister_keymaps()
    if _ho_load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_ho_load_post)
    ui.unregister()
    ops.unregister()


if __name__ == "__main__":
    register()
