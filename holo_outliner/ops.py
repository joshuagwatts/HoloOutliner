"""Holo Outliner operators: thin wrappers around core.py logic."""

import bpy
from bpy.props import StringProperty, EnumProperty

from . import core


def _obj(self, context):
    return context.scene.objects.get(self.obj_name)


class HO_OT_select(bpy.types.Operator):
    """Select object (click / shift-range / ctrl-toggle, C4D style)"""
    bl_idname = "ho.select"
    bl_label = "Holo Select"
    bl_options = {"UNDO"}

    obj_name: StringProperty()

    def invoke(self, context, event):
        obj = _obj(self, context)
        if obj is None:
            return {"CANCELLED"}
        vl = context.view_layer
        if event.shift:
            core.select_range(context.scene, vl, obj)
        elif event.ctrl or event.oskey:
            core.select_toggle(vl, obj)
        else:
            core.select_replace(vl, obj)
        return {"FINISHED"}

    def execute(self, context):
        # headless / repeat path: plain click behavior
        obj = _obj(self, context)
        if obj is None:
            return {"CANCELLED"}
        core.select_replace(context.view_layer, obj)
        return {"FINISHED"}


class HO_OT_dot(bpy.types.Operator):
    """Cycle visibility dot: unset -> on -> off (C4D tri-state)"""
    bl_idname = "ho.dot"
    bl_label = "Holo Visibility Dot"
    bl_options = {"UNDO"}

    obj_name: StringProperty()
    channel: EnumProperty(items=[("V", "Viewport", ""), ("R", "Render", "")])

    def execute(self, context):
        obj = _obj(self, context)
        if obj is None:
            return {"CANCELLED"}
        key = core.PROP_VIS_V if self.channel == "V" else core.PROP_VIS_R
        core.cycle_state(obj, key)
        core.apply_visibility(context.scene)
        return {"FINISHED"}


class HO_OT_expand(bpy.types.Operator):
    """Expand / collapse branch"""
    bl_idname = "ho.expand"
    bl_label = "Holo Expand"
    bl_options = {"UNDO"}

    obj_name: StringProperty()

    def execute(self, context):
        obj = _obj(self, context)
        if obj is None:
            return {"CANCELLED"}
        core.set_expanded(obj, not core.is_expanded(obj))
        return {"FINISHED"}


class HO_OT_parent_to(bpy.types.Operator):
    """Parent the current selection to this object (keeps world transforms)"""
    bl_idname = "ho.parent_to"
    bl_label = "Holo Parent Selection To"
    bl_options = {"UNDO"}

    obj_name: StringProperty()

    def execute(self, context):
        target = _obj(self, context)
        if target is None:
            return {"CANCELLED"}
        n = core.parent_selection_to(context.scene, context.view_layer, target)
        self.report({"INFO"}, f"Parented {n} object(s) to {target.name}")
        return {"FINISHED"}


class HO_OT_unparent(bpy.types.Operator):
    """Unparent this object (keeps world transform)"""
    bl_idname = "ho.unparent"
    bl_label = "Holo Unparent"
    bl_options = {"UNDO"}

    obj_name: StringProperty()

    def execute(self, context):
        obj = _obj(self, context)
        if obj is None:
            return {"CANCELLED"}
        if core.unparent(obj):
            self.report({"INFO"}, f"Unparented {obj.name}")
        return {"FINISHED"}


class HO_OT_group(bpy.types.Operator):
    """Group selection into a Null (C4D Group Objects)"""
    bl_idname = "ho.group"
    bl_label = "Holo Group"
    bl_options = {"UNDO"}

    def execute(self, context):
        null = core.group_selection(context.scene, context.view_layer)
        if null is None:
            self.report({"WARNING"}, "Nothing selected")
            return {"CANCELLED"}
        core.select_replace(context.view_layer, null)
        self.report({"INFO"}, f"Grouped into {null.name}")
        return {"FINISHED"}


class HO_OT_rename(bpy.types.Operator):
    """Rename object (F2, C4D-style)"""
    bl_idname = "ho.rename"
    bl_label = "Holo Rename"
    bl_options = {"UNDO"}

    obj_name: StringProperty()
    new_name: StringProperty(name="Name")

    def invoke(self, context, event):
        obj = _obj(self, context)
        if obj is None:
            # fall back to the active object so F2 works from the panel
            obj = context.view_layer.objects.active
        if obj is None:
            return {"CANCELLED"}
        self.obj_name = obj.name
        self.new_name = obj.name
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        obj = _obj(self, context)
        if obj is None:
            return {"CANCELLED"}
        obj.name = self.new_name or obj.name
        return {"FINISHED"}


class HO_OT_solo(bpy.types.Operator):
    """Isolate object in the viewport (C4D viewport solo)"""
    bl_idname = "ho.solo"
    bl_label = "Holo Solo"
    bl_options = {"UNDO"}

    mode: EnumProperty(
        items=[("SINGLE", "Single", ""), ("HIERARCHY", "Hierarchy", "")],
        default="SINGLE",
    )

    def execute(self, context):
        obj = context.view_layer.objects.active
        if obj is None:
            self.report({"WARNING"}, "Nothing active")
            return {"CANCELLED"}
        core.solo(context.scene, context.view_layer, obj, self.mode)
        return {"FINISHED"}


class HO_OT_unsolo(bpy.types.Operator):
    """Clear viewport solo, restore visibility"""
    bl_idname = "ho.unsolo"
    bl_label = "Holo Unsolo"
    bl_options = {"UNDO"}

    def execute(self, context):
        if not core.unsolo(context.scene):
            self.report({"INFO"}, "Solo was not active")
        return {"FINISHED"}


CLASSES = (
    HO_OT_select,
    HO_OT_dot,
    HO_OT_expand,
    HO_OT_parent_to,
    HO_OT_unparent,
    HO_OT_group,
    HO_OT_rename,
    HO_OT_solo,
    HO_OT_unsolo,
)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
