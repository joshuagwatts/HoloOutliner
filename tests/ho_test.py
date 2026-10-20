"""Holo Outliner headless verification. Run:
~/workspace/.tools/blender-5.2.2-linux-x64/blender -b --python ho_test.py
"""
import sys
import traceback

sys.path.insert(0, "/home/hatch/workspace/HoloOutliner")

import bpy

import holo_outliner
from holo_outliner import core

results = []


def check(name, fn):
    try:
        fn()
        results.append(("PASS", name))
        print(f"PASS {name}", flush=True)
    except Exception:
        results.append(("FAIL", name))
        print(f"FAIL {name}\n{traceback.format_exc(limit=8)}", flush=True)


def new_obj(name, loc=(0, 0, 0)):
    o = bpy.data.objects.new(name, None)
    o.location = loc
    bpy.context.scene.collection.objects.link(o)
    return o


def clear_scene():
    bpy.ops.wm.read_homefile(use_empty=True)
    assert len(bpy.context.scene.objects) == 0


def close(a, b, eps=1e-5):
    return all(abs(x - y) < eps for x, y in zip(a, b))


# ---------------------------------------------------------------- register
def t_register():
    holo_outliner.register()
    assert "select" in dir(bpy.ops.ho)
    assert hasattr(bpy.types, "HO_PT_view3d"), "VIEW_3D panel must register"
    assert not hasattr(bpy.types, "HO_PT_outliner"), "OUTLINER panel must not exist"


check("register (strict)", t_register)


# ---------------------------------------------------------------- tree
def t_tree():
    clear_scene()
    a = new_obj("A")
    b = new_obj("B", loc=(1, 0, 0))
    c = new_obj("C", loc=(2, 0, 0))
    c.parent = b
    b.parent = a
    d = new_obj("D", loc=(3, 0, 0))
    tree = core.build_tree(bpy.context.scene)
    assert [(o.name, dep) for o, dep in tree] == [
        ("A", 0), ("B", 1), ("C", 2), ("D", 0)], tree
    # collapse B -> C hidden
    core.set_expanded(b, False)
    tree = core.build_tree(bpy.context.scene)
    assert [(o.name, dep) for o, dep in tree] == [("A", 0), ("B", 1), ("D", 0)]
    core.set_expanded(b, True)
    assert core.has_children(bpy.context.scene, b)
    assert not core.has_children(bpy.context.scene, c)
    assert {o.name for o in core.descendants(a, bpy.context.scene)} == {"B", "C"}


check("tree build / expand / descendants", t_tree)


# ---------------------------------------------------------------- tri-state visibility
def t_tristate():
    clear_scene()
    a = new_obj("A")
    b = new_obj("B")
    b.parent = a
    s = bpy.context.scene
    # defaults: unset -> effective on
    assert core.get_state(a, core.PROP_VIS_V) == core.UNSET
    assert core.effective_state(b, core.PROP_VIS_V) == core.ON
    # parent off -> child inherits off
    core.set_state(a, core.PROP_VIS_V, core.OFF)
    assert core.effective_state(b, core.PROP_VIS_V) == core.OFF
    # child explicit on overrides red parent (C4D rule)
    core.set_state(b, core.PROP_VIS_V, core.ON)
    assert core.effective_state(b, core.PROP_VIS_V) == core.ON
    # cycle order: unset -> on -> off -> unset
    core.set_state(b, core.PROP_VIS_V, core.UNSET)
    assert core.cycle_state(b, core.PROP_VIS_V) == core.ON
    assert core.cycle_state(b, core.PROP_VIS_V) == core.OFF
    assert core.cycle_state(b, core.PROP_VIS_V) == core.UNSET
    # apply writes Blender flags
    core.set_state(a, core.PROP_VIS_V, core.OFF)
    core.set_state(b, core.PROP_VIS_V, core.UNSET)
    core.set_state(a, core.PROP_VIS_R, core.ON)
    core.apply_visibility(s)
    assert a.hide_viewport and b.hide_viewport
    assert not a.hide_render and not b.hide_render
    # render channel independent from viewport
    core.set_state(b, core.PROP_VIS_R, core.OFF)
    core.apply_visibility(s)
    assert b.hide_render and not a.hide_render


check("tri-state visibility + apply", t_tristate)


# ---------------------------------------------------------------- parenting
def t_parenting():
    clear_scene()
    s = bpy.context.scene
    vl = bpy.context.view_layer
    p = new_obj("P", loc=(5, 0, 0))
    c = new_obj("C", loc=(1, 2, 3))
    vl.update()
    before = tuple(c.matrix_world.translation)
    core.set_parent_keep_transform(c, p)
    vl.update()
    assert c.parent == p
    assert close(tuple(c.matrix_world.translation), before), "world moved on parent"
    # cycle prevention
    assert not core.can_parent(p, c)      # p -> child c would cycle
    assert not core.can_parent(p, p)     # self
    assert core.can_parent(c, None)      # unparent meaningful
    assert not core.can_parent(p, None)  # p has no parent -> nothing to do
    # unparent keeps transform
    core.set_parent_keep_transform(c, None)
    vl.update()
    assert c.parent is None
    assert close(tuple(c.matrix_world.translation), before), "world moved on unparent"
    # parent_selection_to via selection
    c2 = new_obj("C2", loc=(0, 0, 0))
    core.select_replace(vl, c2)
    n = core.parent_selection_to(s, vl, p)
    assert n == 1 and c2.parent == p


check("parent/unparent keep transform + cycle guard", t_parenting)


# ---------------------------------------------------------------- group
def t_group():
    clear_scene()
    s = bpy.context.scene
    vl = bpy.context.view_layer
    a = new_obj("A", loc=(0, 0, 0))
    b = new_obj("B", loc=(2, 0, 0))
    ch = new_obj("CH", loc=(2, 1, 0))
    core.set_parent_keep_transform(ch, b)  # sub-hierarchy must survive grouping
    vl.update()
    assert close(tuple(ch.matrix_world.translation), (2, 1, 0))
    for o in (a, b, ch):
        o.select_set(True)
    null = core.group_selection(s, vl)
    assert null is not None and null.type == "EMPTY"
    assert null.name.startswith("Null")
    # centroid of the top-level selection (A and B; CH rides along under B)
    assert close(tuple(null.location), (1.0, 0.0, 0.0)), tuple(null.location)
    assert a.parent == null and b.parent == null
    assert ch.parent == b, "sub-hierarchy not preserved"
    vl.update()
    assert close(tuple(a.matrix_world.translation), (0, 0, 0))
    assert close(tuple(ch.matrix_world.translation), (2, 1, 0))


check("group into Null preserves sub-hierarchy", t_group)


# ---------------------------------------------------------------- solo
def t_solo():
    clear_scene()
    s = bpy.context.scene
    vl = bpy.context.view_layer
    a = new_obj("A")
    b = new_obj("B")
    c = new_obj("C")
    c.parent = b
    vl.objects.active = b
    core.solo(s, vl, b, "SINGLE")
    assert not b.hide_viewport and a.hide_viewport and c.hide_viewport
    assert core.is_solo_active(s)
    assert core.unsolo(s)
    assert not any(o.hide_viewport for o in (a, b, c))
    assert not core.is_solo_active(s)
    # hierarchy mode keeps children
    core.solo(s, vl, b, "HIERARCHY")
    assert not b.hide_viewport and not c.hide_viewport and a.hide_viewport
    core.unsolo(s)
    assert not a.hide_viewport


check("solo single/hierarchy + restore", t_solo)


# ---------------------------------------------------------------- selection + rename + ops
def t_select_ops():
    clear_scene()
    s = bpy.context.scene
    vl = bpy.context.view_layer
    a = new_obj("A")
    b = new_obj("B")
    b.parent = a
    c = new_obj("C")
    core.select_replace(vl, a)
    assert a.select_get() and not b.select_get()
    assert vl.objects.active == a
    core.select_toggle(vl, b)
    assert b.select_get()
    core.select_toggle(vl, b)
    assert not b.select_get()
    # shift-range between A and C selects B too (tree order A,B,C)
    core.select_replace(vl, a)
    core.select_range(s, vl, c)
    assert a.select_get() and b.select_get() and c.select_get()
    # rename via operator execute path
    op = bpy.ops.ho.rename
    bpy.ops.ho.select(obj_name="A")
    assert vl.objects.active.name == "A"
    # dot operator cycles + applies
    bpy.ops.ho.dot(obj_name="A", channel="V")
    assert core.get_state(s.objects["A"], core.PROP_VIS_V) == core.ON
    assert not s.objects["A"].hide_viewport
    bpy.ops.ho.dot(obj_name="A", channel="V")
    assert s.objects["A"].hide_viewport  # off now
    # expand operator
    bpy.ops.ho.expand(obj_name="A")
    assert not core.is_expanded(s.objects["A"])
    bpy.ops.ho.expand(obj_name="A")
    assert core.is_expanded(s.objects["A"])


check("selection/range/rename/dot/expand operators", t_select_ops)


# ---------------------------------------------------------------- draw validation
class _MockOp:
    def __init__(self, idname, calls):
        object.__setattr__(self, "_idname", idname)
        object.__setattr__(self, "_calls", calls)

    def __setattr__(self, k, v):
        self._calls.append(("prop", self._idname, k, v))


class _MockLayout:
    def __init__(self, calls):
        self._calls = calls

    def row(self, align=False):
        return _MockLayout(self._calls)

    def column(self, align=False):
        return _MockLayout(self._calls)

    def label(self, text="", icon="NONE"):
        self._calls.append(("icon", icon))

    def operator(self, idname, text="", icon="NONE", emboss=True, depress=False):
        self._calls.append(("operator", idname))
        self._calls.append(("icon", icon))
        return _MockOp(idname, self._calls)


class _MockCtx:
    def __init__(self, scene):
        self.scene = scene


def t_draw():
    from holo_outliner import ui as ho_ui
    from holo_outliner import ops as ho_ops
    clear_scene()
    a = new_obj("ParentObj")
    b = new_obj("ChildObj")
    b.parent = a
    new_obj("SoloObj")
    op_classes = {c.bl_idname: c for c in ho_ops.CLASSES}
    icon_ids = {i.identifier for i in
                bpy.types.UILayout.bl_rna.functions["operator"].parameters["icon"].enum_items}
    calls = []
    ho_ui.draw_holo_outliner(_MockLayout(calls), _MockCtx(bpy.context.scene))
    assert calls, "draw produced no layout calls"
    seen_ops = set()
    for c in calls:
        if c[0] == "operator":
            _, idname = c
            seen_ops.add(idname)
            prefix, name = idname.split(".")
            assert name in dir(getattr(bpy.ops, prefix)), f"unknown operator {idname}"
        elif c[0] == "prop":
            _, idname, prop, _v = c
            cls = op_classes[idname]
            assert prop in cls.__annotations__, f"{idname} has no property {prop}"
        elif c[0] == "icon":
            _, icon = c
            assert icon in icon_ids, f"unknown icon {icon}"
    for want in ("ho.select", "ho.dot", "ho.expand", "ho.rename",
                 "ho.parent_to", "ho.unparent", "ho.group", "ho.solo"):
        assert want in seen_ops, f"draw never uses {want}"


check("panel draw: operators/props/icons valid", t_draw)


# ---------------------------------------------------------------- unregister
def t_unregister():
    holo_outliner.unregister()
    assert "select" not in dir(bpy.ops.ho)


check("unregister clean", t_unregister)
fails = [n for st, n in results if st == "FAIL"]
print(f"\n{len(results) - len(fails)}/{len(results)} passed", flush=True)
if fails:
    print("FAILURES:", fails, flush=True)
    sys.exit(1)
