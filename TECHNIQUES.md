# PrintLab modeling cookbook

Proven construction recipes. Pick the right one BEFORE writing geometry —
and skim 1–2 similar scripts in `parts/` as worked examples. Prefer building
in 2D (shapely) and extruding/revolving/sweeping ONCE over stacking many 3D
booleans.

## 1. Plan-silhouette extrude (flat parts, trays, plates, brackets)
Draw the outline in XY, soften it, extrude up. Bed face is automatically flat.
```python
sil = lib3d.soften(outline_polygon, P["soften"], style=P.get("soften_style", "round"))
part = lib3d.extrude(sil, P["thick"])
```

## 2. Side-profile extrude (stands, wedges, L/U shapes)
Draw the SIDE VIEW as a polygon (y = depth, z = height), soften with the bed
line kept flat, extrude to width, then remap axes. See `parts/phone_stand.py`.
```python
profile = lib3d.soften(profile, P["soften"], keep_flat_y=0)
wedge = lib3d.extrude(profile, P["width"])
wedge.apply_transform(np.array([[0,0,1,0],[1,0,0,0],[0,1,0,0],[0,0,0,1]], dtype=float))
```

## 3. Revolve / lathe (anything round: bowls, vases, knobs, funnels, feet)
Profile = [(radius, z), ...]. Solid parts start and end on the axis.
```python
bowl = lib3d.revolve([(0,0), (40,0), (45,8), (42,38), (38,38), (40,8), (8,5), (0,5)])
```

## 4. Sweep (hooks, handles, tubes, curved brackets)
Round/oval cross-section along a smooth 3D path (20+ samples on curves).
```python
from shapely.geometry import Point
import numpy as np
t = np.linspace(0, np.pi, 24)
path = np.c_[np.zeros_like(t), 20*np.cos(t), 20*np.sin(t) + 5]  # half-circle hook
hook = lib3d.sweep(Point(0,0).buffer(5, quad_segs=24), path)
```

## 5. Text (signs, keychains, labels)
`lib3d.text_polygons(text, size)` → extrude. Raised: union on top (>=1.2 mm
proud, >=3 mm cap height). Engraved: difference 0.6–1.0 mm deep.
See `parts/keychain_smith.py`.

## 6. Image trace (drawings, logos, silhouettes → real shapes)
`lib3d.image_outline(path, width_mm)` traces the dark shape, holes included.
- Flat ornament: `lib3d.extrude(shape, 4)`
- Cookie cutter: `lib3d.extrude(shape.buffer(0.8).difference(shape.buffer(-0.4)), 18)`
  plus a wider 1.2 mm-tall flange at the top for pressing
- Emboss/engrave: union/difference a thin extrude onto a rounded_box
If the user wants the OBJECT in a photo (not its outline), view the image and
model the 3D object's proportions and features yourself.

## 7. Multi-material / multi-body (X2D dual nozzle)
Separate non-overlapping bodies, one coordinate frame, `lib3d.export_multi`.
Flex zones 0.8–1.6 mm TPU. NEVER a straight seam — `lib3d.seam_tabs()`
dovetails; pegs/pockets where a strap enters a body. See `parts/hinge_demo.py`.

## 8. Bases and softening
Slab base → `lib3d.rounded_box(w, d, h, r)` (flat bottom for the bed).
Everything visible gets `soften` (param, default 2); `style="chamfer"` for
flat bevels. Functional faces (seams, snaps, threads) stay crisp.

## 9. Fits and mechanisms
Print-in-place clearance 0.35–0.45 mm (PLA) / 0.4–0.5 (PETG). Snap cantilever:
1.2 mm thick, 7–9 mm long, 1.0 mm undercut, chamfered tip. M3: hole 3.4 mm,
countersink 6.5 × 2 mm. Pin hinge: pin 4 mm, bore 4.4 mm, add end caps.

## 10. Sanity dimensions
Cased phone ~75×150×9 · credit card 86×54 · AA 14.5⌀×50.5 · 1:64 diecast car
~62×25×20 · US quarter 24.3⌀×1.75 · pencil 7.5⌀ · broom handle 22–25⌀.
