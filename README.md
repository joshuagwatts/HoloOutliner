# Holo Outliner

C4D-style Object Manager for Blender. A single-hierarchy tree — one parent per
object, no "same object in multiple collections doing different things."

## Install

**From the zip (easiest):** Blender → Edit → Preferences → Add-ons → Install from
Disk → pick `HoloOutliner.zip` → enable "Interface: Holo Outliner".

**From source:** copy the `holo_outliner/` folder into Blender's addons directory,
then enable it in Preferences.

## Where it lives

- 3D Viewport → Sidebar (N) → **Holo** tab

(Blender's Outliner editor has no sidebar region, so the panel can't dock inside
the Outliner window itself — v1.0.0 tried and failed to install. The 3D View
sidebar is its home.)

## Interactions (C4D Object Manager parity)

| C4D | Holo Outliner v1 |
|---|---|
| Single-parent tree | Tree follows real Blender parenting only; collections are ignored for display |
| Drop onto row = parent | Select objects, then click the 🔗 link button on the target row |
| Drop between rows = unparent to root | ⛓‍💥 unlink button on any parented row |
| Editor / Renderer visibility dots (gray/green/red) | Two dots per row: hollow = inherits parent, eye-open = on, eye-closed = off. A red parent hides children unless a child is explicitly green |
| Click / shift-click / ctrl-click selection, synced with viewport | Same, both directions |
| Double-click / Return rename | F2 (also the ✏️ button per row) |
| Viewport solo (single / hierarchy) | Solo / Solo-hierarchy buttons in the header, X to clear |
| Group Objects into a Null | Group button: selection's top-level items go into a Null at the selection centroid, sub-hierarchies preserved |
| Triangle expand/collapse | Same per row |

All parenting operations preserve world transforms. Visibility dots are the source
of truth on file load.

## v1 limits (honest)

- **No true drag-and-drop.** Blender's Python UI does not expose drag events for
  custom panels, so parenting is select-then-click-link instead of drag-onto-row.
  Same result, one extra click.
- Rename is F2, not double-click (no double-click events in Blender's UI API).
- No arrow-key hopping between rows while renaming.
- Solo restores by object name; renaming mid-solo confuses the restore.
- Toggling visibility in Blender's native outliner bypasses the tri-state dots.
  Use the Holo dots as the control.

## Dev

Headless tests (need Blender, run from this folder):

```
~/workspace/.tools/blender-5.2.2-linux-x64/blender -b --python tests/ho_test.py
```

9 checks: register, tree build, tri-state visibility, parenting, grouping, solo,
selection, panel draw validation, unregister.
