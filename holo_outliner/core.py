"""Holo Outliner core: C4D Object-Manager-style tree logic on top of Blender objects.

All functions here are plain Python operating on bpy objects/scenes so they
can be exercised headless. Operators in ops.py are thin wrappers.
"""

import bpy

# ---------------------------------------------------------------------------
# Custom ID-property keys
# ---------------------------------------------------------------------------
PROP_VIS_V = "ho_vis_v"      # tri-state viewport visibility: -1 unset, 0 off, 1 on
PROP_VIS_R = "ho_vis_r"      # tri-state render visibility:   -1 unset, 0 off, 1 on
PROP_EXPANDED = "ho_expanded"  # branch expanded in the tree (default True)

UNSET, OFF, ON = -1, 0, 1


def _tri(obj, key):
    v = obj.get(key, UNSET)
    return v if v in (UNSET, OFF, ON) else UNSET


def get_state(obj, key):
    """Explicit tri-state for one object (-1 unset, 0 off, 1 on)."""
    return _tri(obj, key)


def set_state(obj, key, value):
    obj[key] = value


def cycle_state(obj, key):
    """C4D dot order: unset -> on -> off -> unset. Returns the new state."""
    cur = get_state(obj, key)
    nxt = {UNSET: ON, ON: OFF, OFF: UNSET}[cur]
    obj[key] = nxt
    return nxt


def effective_state(obj, key):
    """Nearest explicitly-set ancestor wins (self included); default visible."""
    o = obj
    while o is not None:
        s = get_state(o, key)
        if s != UNSET:
            return s
        o = o.parent
    return ON


def apply_visibility(scene):
    """Push effective tri-states into Blender's hide_viewport / hide_render."""
    for o in scene.objects:
        o.hide_viewport = (effective_state(o, PROP_VIS_V) == OFF)
        o.hide_render = (effective_state(o, PROP_VIS_R) == OFF)


def is_expanded(obj):
    return bool(obj.get(PROP_EXPANDED, True))


def set_expanded(obj, value):
    obj[PROP_EXPANDED] = bool(value)


# ---------------------------------------------------------------------------
# Tree
# ---------------------------------------------------------------------------
def build_tree(scene):
    """Flat [(object, depth)] display list honoring expanded state.

    Single-parent hierarchy from real Blender parenting; collections are
    ignored for display. Roots are objects with no parent, in scene order.
    """
    children = {}
    roots = []
    for o in scene.objects:
        p = o.parent
        if p is None:
            roots.append(o)
        else:
            children.setdefault(p, []).append(o)

    out = []
    stack = [(o, 0) for o in reversed(roots)]
    while stack:
        o, depth = stack.pop()
        out.append((o, depth))
        if is_expanded(o):
            for c in reversed(children.get(o, [])):
                stack.append((c, depth + 1))
    return out


def has_children(scene, obj):
    return any(o.parent == obj for o in scene.objects)


def descendants(obj, scene):
    """All objects below obj (any depth)."""
    children = {}
    for o in scene.objects:
        if o.parent is not None:
            children.setdefault(o.parent, []).append(o)
    out = []
    stack = list(children.get(obj, []))
    while stack:
        o = stack.pop()
        out.append(o)
        stack.extend(children.get(o, []))
    return out


def is_descendant_of(obj, ancestor):
    o = obj.parent
    while o is not None:
        if o == ancestor:
            return True
        o = o.parent
    return False


# ---------------------------------------------------------------------------
# Parenting (world transform preserving)
# ---------------------------------------------------------------------------
def set_parent_keep_transform(child, parent):
    """Parent child to parent (or None) without moving it in the world."""
    bpy.context.view_layer.update()  # matrices must be live before reading them
    mw = child.matrix_world.copy()
    child.parent = parent
    if parent is not None:
        child.matrix_parent_inverse = parent.matrix_world.inverted()
    else:
        child.matrix_parent_inverse.identity()
    child.matrix_world = mw


def can_parent(child, parent):
    """False for self-parenting and anything that would create a cycle."""
    if parent is None:
        return child.parent is not None  # unparent only meaningful if parented
    if child == parent:
        return False
    if is_descendant_of(parent, child):
        return False
    return True


def parent_selection_to(scene, view_layer, target):
    """Parent every selected object (except target) to target. Returns count."""
    done = 0
    for o in list(view_layer.objects):
        if not o.select_get():
            continue
        if o == target:
            continue
        if not can_parent(o, target):
            continue
        set_parent_keep_transform(o, target)
        done += 1
    return done


def unparent(obj):
    """Remove obj's parent, keeping its world transform. Returns True."""
    if obj.parent is None:
        return False
    set_parent_keep_transform(obj, None)
    return True


def group_selection(scene, view_layer, name="Null"):
    """C4D 'Group Objects': Empty containing the selection's top-level items.

    Objects whose ancestor is also selected stay put, preserving
    sub-hierarchies. The Null is placed at the selection's centroid.
    Returns the new Empty, or None when nothing was selected.
    """
    sel = [o for o in view_layer.objects if o.select_get()]
    if not sel:
        return None
    view_layer.update()  # matrix_world must be evaluated before reading it
    sel_set = set(sel)
    tops = [o for o in sel
            if not any(is_descendant_of(o, other) for other in sel_set if other != o)]
    cx = sum((o.matrix_world.translation.x for o in tops), 0.0) / len(tops)
    cy = sum((o.matrix_world.translation.y for o in tops), 0.0) / len(tops)
    cz = sum((o.matrix_world.translation.z for o in tops), 0.0) / len(tops)
    null = bpy.data.objects.new(name, None)
    null.location = (cx, cy, cz)
    scene.collection.objects.link(null)
    view_layer.update()  # null.matrix_world must be live before it becomes a parent
    for o in tops:
        set_parent_keep_transform(o, null)
    return null


# ---------------------------------------------------------------------------
# Solo (viewport isolate)
# ---------------------------------------------------------------------------
SOLO_KEY = "ho_solo_backup"


def _backup_key(scene):
    return scene.get(SOLO_KEY, {})


def solo(scene, view_layer, obj, mode="SINGLE"):
    """Hide everything else in the viewport. mode: SINGLE or HIERARCHY."""
    keep = {obj}
    if mode == "HIERARCHY":
        keep.update(descendants(obj, scene))
    backup = {o.name: bool(o.hide_viewport) for o in scene.objects}
    scene[SOLO_KEY] = backup
    for o in scene.objects:
        o.hide_viewport = o not in keep
    return True


def unsolo(scene):
    """Restore viewport visibility from the solo backup."""
    backup = scene.get(SOLO_KEY)
    if not backup:
        return False
    for name, hidden in backup.items():
        o = scene.objects.get(name)
        if o is not None:
            o.hide_viewport = bool(hidden)
    if SOLO_KEY in scene:
        del scene[SOLO_KEY]
    # re-apply tri-state dots so dot logic stays the source of truth
    apply_visibility(scene)
    return True


def is_solo_active(scene):
    return SOLO_KEY in scene


# ---------------------------------------------------------------------------
# Selection (no bpy.ops: works headless and in any context)
# ---------------------------------------------------------------------------
def select_replace(view_layer, obj):
    for o in view_layer.objects:
        o.select_set(False)
    obj.select_set(True)
    view_layer.objects.active = obj


def select_toggle(view_layer, obj):
    obj.select_set(not obj.select_get())
    if obj.select_get():
        view_layer.objects.active = obj


def select_range(scene, view_layer, obj):
    """Shift-click: select everything between active and obj in tree order."""
    active = view_layer.objects.active
    if active is None or active == obj:
        select_replace(view_layer, obj)
        return
    order = [o for o, _ in build_tree(scene)]
    try:
        a, b = order.index(active), order.index(obj)
    except ValueError:
        select_replace(view_layer, obj)
        return
    lo, hi = (a, b) if a < b else (b, a)
    for o in view_layer.objects:
        o.select_set(False)
    for o in order[lo:hi + 1]:
        o.select_set(True)
    view_layer.objects.active = obj