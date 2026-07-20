# PrintLab — Claude contract

Personal "Meshy replacement" desktop app: the user describes a part in plain
English; Claude writes a Python script that builds the geometry and exports a
print-ready STL. No paid APIs — the user explicitly declined Replicate/Meshy
spend; do NOT re-propose them. Organic AI sculpts are out of scope.

## App architecture

- `app.py` — FastAPI server on 127.0.0.1:8123. Serves `static/index.html`
  (the whole UI, one file), lists parts, re-runs scripts with the
  `PRINTLAB_P` env-var override (instant free tweaks), bakes overrides into
  the script's P block, and forges new parts by spawning **Claude Code
  headless**: `claude -p <contract prompt> --output-format stream-json
  --verbose --model fable --effort high --allowedTools
  Read,Glob,Grep,Write,Edit,Bash`.
- The claude binary is resolved from PATH, falling back to the desktop app's
  bundled CLI at `%APPDATA%\Claude\claude-code\<version>\claude.exe`.
  Headless runs need a ONE-TIME interactive `/login` (desktop-app auth is not
  shared); the UI walks the user through it via the Connect card.
- Strip all CLAUDE* env vars before spawning (see `clean_env()`), pass
  `stdin=DEVNULL`, and parse stream-json lines defensively — auth failures
  arrive as plain-text "Not logged in" lines.
- Launch: `PrintLab.bat` (Desktop shortcut "PrintLab") starts the server
  minimized and opens Edge in --app mode. Port already bound = already
  running, app.py exits 0.
- Preview entry for verification: name `printlab` (port 8123) in
  `C:\Claude\.claude\launch.json`. Verify via preview_eval DOM/API checks —
  screenshots time out in this environment. `viewer.html` is a standalone
  drag-drop STL viewer (kept for no-server use).

## Conventions (every part)

- Units: millimeters. Target printer: **Bambu X2D** — main-nozzle volume
  256 × 256 × 260 (`lib3d.PLATE`, per-axis X/Y/Z). Dual-nozzle (two-color)
  prints only get 235.5 in X — cap X at 235 if a part is meant for two colors.
- One script per part in `parts/`, params in `P = lib3d.params({...})` at the
  top — every tunable a plain literal with a short comment. The app renders
  these as editable fields, so name keys clearly.
- **Export name must equal the script filename stem**:
  `lib3d.export(build(), "<stem>")` in `parts/<stem>.py` — the app matches
  STLs to scripts by stem.
- Import path boilerplate (parts/ is not a package):
  `sys.path.insert(0, str(Path(__file__).parents[1]))` then `import lib3d`.
- ALL booleans through `lib3d.union/difference/intersection` (manifold engine,
  watertight by construction). Never `trimesh.boolean` with default engine.
- Run with `venv\Scripts\python.exe parts\<stem>.py`. The run is NOT done
  until the output says `watertight=True` and `plate_fit=OK`.
- STLs go to `output/` (gitignored — regenerate, don't commit).

## lib3d quick reference

- `text_polygons(text, size_mm)` — font outlines as shapely geometry, holes
  handled; rendered cap height ≈ 0.7 × size_mm
- `rounded_rect(w, h, r)` — shapely; `extrude(poly, h)` — shapely → mesh (+Z)
- `box(w,d,h)`, `cylinder(r,h)`, `move(m,x,y,z)`, `rotate(m,deg,axis)`
- Prefer building a 2D profile polygon and extruding over stacking booleans —
  fewer ops, always watertight (see parts/phone_stand.py).

## Dual nozzle (X2D)

Primary uses, in the user's priority order:
1. **Dedicated support filament in nozzle 2** — overhangs cost less than on a
   single-nozzle machine and interfaces come out clean. Still prefer
   self-supporting geometry when it's free, but don't contort a design to
   dodge supports; note "needs supports" in the SUMMARY when relevant.
2. **Rigid + flexible in one print** (e.g. PETG body + TPU hinge/gasket/foot)
   — build SEPARATE non-overlapping bodies in one coordinate frame and export
   with `lib3d.export_multi({"rigid": m1, "flex": m2}, "<stem>")`. Carve the
   flex body's space out of the rigid one with `difference()` using the SAME
   mesh, so they sit flush.
3. Two-color cosmetics (inlaid text etc.) — same export_multi mechanism,
   user rarely wants this.
- Multi-body parts cap X at 235 mm (aux-nozzle reach, `lib3d.DUAL_X`).
- Slicer flow: open all `<stem>.<body>.stl` files together in Bambu Studio →
  "load as a single object with multiple parts" → assign a filament per part.

## Material rules (apply when the user names a material)

- **PLA** (default): rigid, prints anything; min wall 1.2 mm (2 mm better);
  print-in-place clearance 0.35–0.45 mm. Living hinges fatigue and snap —
  use pin or strap hinges instead.
- **PETG**: tough, slightly springy; clearances +0.05 over PLA (0.4–0.5
  print-in-place); add fillets/chamfers at internal corners (notch-sensitive);
  avoid wispy spires (strings).
- **ABS/ASA**: fine on the X2D (heated chamber), but shrinks — prefer ribs
  over bulk, avoid huge flat slabs (warp); ASA for anything outdoor/UV.
- **TPU**: the flex material — living hinges, straps, gaskets, grippy feet;
  flex zones 0.8–1.6 mm thick; tolerances don't matter (it squishes);
  never TPU threads or crisp snap-fits.
- **Material pairing** (one print, two nozzles): PETG+TPU bond strongly —
  the rigid+flex combo of choice. PLA+TPU bonds poorly. PLA vs PETG barely
  adhere to each other (that pairing is a support-interface trick, not a
  bonded joint). Regardless of pairing, ALWAYS add mechanical interlock:
  through-holes the flex fills, T-slots, or pegs — never rely on adhesion
  alone at a working joint.
- **Seam rule (user-mandated): NEVER butt two materials along a straight
  line — a flat seam is a pre-made crack.** Interweave the boundary with
  `lib3d.seam_tabs(span, height, depth)` — dovetail teeth, union into one
  body, difference from the other, zero clearance. For tall seams stack two
  strips at offset phase (move one by half a pitch). Pegs/pockets still
  apply where a strap enters a body (see hinge_demo).

## Design judgment

- **Soft edges (user-mandated): no nasty sharp corners.** Every part gets a
  `"soften"` param (mm radius, 0 = off, default ~2) wired through
  `lib3d.soften()` on its silhouette/profile — for vertical profiles pass
  `keep_flat_y=0` so the bed face stays flat. When the user wants a flat
  bevel instead of a round-over, add `"soften_style": "chamfer"` (soften's
  `style=` arg; default "round"). Use `lib3d.rounded_box()` for slabs/bases
  (rounded verticals + top, flat bottom). Functional surfaces are exempt:
  seam dovetails, threads, snap-fits, and the bed-contact face stay crisp.
  Keep r under half the thinnest feature or details vanish.
- Default wall/floor thickness ≥ 2 mm; raised text ≥ 1.2 mm proud, ≥ 3 mm
  cap height; holes for M3 screws = 3.4 mm dia, countersink 6.5 mm.
- Think about print orientation: flat face down, avoid unsupported overhangs
  > 50°; chamfer rather than fillet on the plate-side edges.
- Sanity-check real-world fit (a phone is ~75 × 150 × 9 mm cased; a credit
  card 86 × 54; AA battery 14.5 dia × 50.5).
