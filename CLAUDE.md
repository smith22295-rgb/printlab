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
  --verbose --model opus --allowedTools Read,Glob,Grep,Write,Edit,Bash`.
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

## Design judgment

- Default wall/floor thickness ≥ 2 mm; raised text ≥ 1.2 mm proud, ≥ 3 mm
  cap height; holes for M3 screws = 3.4 mm dia, countersink 6.5 mm.
- Think about print orientation: flat face down, avoid unsupported overhangs
  > 50°; chamfer rather than fillet on the plate-side edges.
- Sanity-check real-world fit (a phone is ~75 × 150 × 9 mm cased; a credit
  card 86 × 54; AA battery 14.5 dia × 50.5).
