"""Holo Outliner panels: C4D Object-Manager-style tree.

Primary home is the Outliner sidebar (N panel, "Holo" tab); a second copy
lives in the 3D View sidebar so the tree is reachable while modeling.
Both panels share draw_holo_outliner().
"""

import bpy

from . import core

_registered = []

TYPE_ICONS = {
    "MESH": "OUTLINER_OB_MESH",
    "CURVE": "OUTLINER_OB_CURVE",
    "SURFACE": "OUTLINER_OB_SURFACE",
    "META": "OUTLINER_OB_META",
    "FONT": "OUTLINER_OB_FONT",
    "CURVES": "OUTLINER_OB_CURVES",
    "POINTCLOUD": "OUTLINER_OB_POINTCLOUD",
    "VOLUME": "OUTLINER_OB_VOLUME",
    "GPENCIL": "OUTLINER_OB_GREASEPENCIL",
    "ARMATURE": "OUTLINER_OB_ARMATURE",
    "LATTICE": "OUTLINER_OB_LATTICE",
    "EMPTY": "OUTLINER_OB_EMPTY",
    "LIGHT": "OUTLINER_OB_LIGHT",
    "LIGHT_PROBE": "OUTLINER_OB_LIGHTPROBE",
    "CAMERA": "OUTLINER_OB_CAMERA",
    "SPEAKER": "OUTLINER_OB_SPEAKER",
}


def _dot_icon(state):
    # unset = hollow (inherits), on = eye open, off = eye closed
    return {core.UNSET: "RADIOBUT_OFF", core.ON: "HIDE_OFF", core.OFF: "HIDE_ON"}[state]


def draw_holo_outliner(layout, context):
    """Shared draw for both panel homes. Kept importable for headless tests."""
    scene = context.scene

    # ---- header: group + solo ----
    hdr = layout.row(align=True)
    hdr.operator("ho.group", text="Group", icon="GROUP")
    hdr.operator("ho.solo", text="Solo", icon="SOLO_ON").mode = "SINGLE"
    solo_h = hdr.operator("ho.solo", text="", icon="OUTLINER_OB_EMPTY")
    solo_h.mode = "HIERARCHY"
    if core.is_solo_active(scene):
        hdr.operator("ho.unsolo", text="", icon="X")

    # ---- tree ----
    col = layout.column(align=True)
    for obj, depth in core.build_tree(scene):
        row = col.row(align=True)

        for _ in range(depth):
            row.label(text="", icon="BLANK1")

        if core.has_children(scene, obj):
            icon = "TRIA_DOWN" if core.is_expanded(obj) else "TRIA_RIGHT"
            op = row.operator("ho.expand", text="", icon=icon, emboss=False)
            op.obj_name = obj.name
        else:
            row.label(text="", icon="BLANK1")

        row.label(text="", icon=TYPE_ICONS.get(obj.type, "OBJECT_DATA"))

        sel = row.operator(
            "ho.select", text=obj.name, emboss=False, depress=obj.select_get()
        )
        sel.obj_name = obj.name

        # viewport dot
        dv = row.operator(
            "ho.dot", text="", icon=_dot_icon(core.get_state(obj, core.PROP_VIS_V)),
            emboss=False,
            depress=core.get_state(obj, core.PROP_VIS_V) == core.OFF,
        )
        dv.obj_name = obj.name
        dv.channel = "V"

        # render dot
        dr = row.operator(
            "ho.dot", text="", icon=_dot_icon(core.get_state(obj, core.PROP_VIS_R)),
            emboss=False,
            depress=core.get_state(obj, core.PROP_VIS_R) == core.OFF,
        )
        dr.obj_name = obj.name
        dr.channel = "R"

        # rename
        rn = row.operator("ho.rename", text="", icon="GREASEPENCIL", emboss=False)
        rn.obj_name = obj.name

        # parent selection to this
        pl = row.operator("ho.parent_to", text="", icon="LINKED", emboss=False)
        pl.obj_name = obj.name

        # unparent (only when parented)
        if obj.parent is not None:
            up = row.operator("ho.unparent", text="", icon="UNLINKED", emboss=False)
            up.obj_name = obj.name


class HO_PT_outliner(bpy.types.Panel):
    bl_label = "Holo Outliner"
    bl_idname = "HO_PT_outliner"
    bl_space_type = "OUTLINER"
    bl_region_type = "UI"
    bl_category = "Holo"

    def draw(self, context):
        draw_holo_outliner(self.layout, context)


class HO_PT_view3d(bpy.types.Panel):
    bl_label = "Holo Outliner"
    bl_idname = "HO_PT_view3d"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Holo"

    def draw(self, context):
        draw_holo_outliner(self.layout, context)


# VIEW_3D first: in background mode the OUTLINER/UI region does not exist,
# so register what we can and tolerate the rest only when headless.
CLASSES = (HO_PT_view3d, HO_PT_outliner)


def register():
    for c in CLASSES:
        try:
            bpy.utils.register_class(c)
        except RuntimeError:
            if not bpy.app.background:
                raise
            # headless: OUTLINER/UI region needs a real window; the rest
            # of the addon (ops, view3d panel) is still fully testable
            continue
        _registered.append(c)


def unregister():
    for c in reversed(_registered):
        bpy.utils.unregister_class(c)
    _registered.clear()
