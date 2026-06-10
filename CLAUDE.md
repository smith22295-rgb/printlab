# PrintLab — Claude contract

Personal "Meshy replacement": the user describes a part in plain English;
Claude writes a Python script that builds the geometry and exports a
print-ready STL. No paid APIs — the user explicitly declined Replicate/Meshy
spend; do NOT re-propose them. Organic AI sculpts are out of scope.

## Toolchain

- Python: `venv\Scripts\python.exe` (3.14) — numpy, trimesh, manifold3d,
  shapely, mapbox-earcut, pillow, matplotlib
- Run a part: `venv\Scripts\python.exe parts\<name>.py` (from repo root)
- Preview server: name `printlab` (port 8102) in `C:\Claude\.claude\launch.json`;
  `viewer.html` is a drag-drop STL viewer (three.js CDN). To verify in preview,
  fetch the STL and dispatch a synthetic DragEvent drop — screenshots time out
  in this environment.

## Conventions (every part)

- Units: millimeters. Target printer: Bambu P1S, 256 mm cube (`lib3d.PLATE`).
- One script per part in `parts/`, with a `P = {...}` params dict at the top —
  user iterates by asking for changes; edit P, re-run.
- Import path boilerplate (parts/ is not a package):
  `sys.path.insert(0, str(Path(__file__).parents[1]))` then `import lib3d`.
- ALL booleans through `lib3d.union/difference/intersection` (manifold engine,
  watertight by construction). Never `trimesh.boolean` with default engine.
- Export only via `lib3d.export(mesh, "name")` — it repairs, drops the part
  onto Z=0, checks plate fit, and prints a stats line. The run is NOT done
  until the output says `watertight=True`.
- STLs go to `output/` (gitignored — regenerate, don't commit).

## lib3d quick reference

- `text_polygons(text, size_mm)` — font outlines as shapely geometry, holes
  handled; rendered cap height ≈ 0.7 × size_mm
- `rounded_rect(w, h, r)` — shapely; `extrude(poly, h)` — shapely → mesh (+Z)
- `box(w,d,h)`, `cylinder(r,h)`, `move(m,x,y,z)`, `rotate(m,deg,axis)`
- Prefer building a 2D profile polygon and extruding over stacking booleans —
  fewer ops, always watertight (see parts/phone_stand.py).

## Design judgment

- Default wall/floor thickness ≥ 2 mm; raised text ≥ 1.2 mm proud, ≥ 3 mm
  cap height; holes for M3 screws = 3.4 mm dia, countersink 6.5 mm.
- Think about print orientation: flat face down, avoid unsupported overhangs
  > 50°; chamfer rather than fillet on the plate-side edges.
- Sanity-check real-world fit (a phone is ~75 × 150 × 9 mm cased; a credit
  card 86 × 54; AA battery 14.5 dia × 50.5).
