# PrintLab — status / handoff

Source of truth for cross-PC handoff. Update this when state changes.

## Current state (2026-07-26)

- **Engine: Opus 5 at high effort** — `--model opus --effort high`.
  Settled by a bake-off, not a guess; see "Model bake-off" below.
- Set up and verified on BOTH PCs. This entry added from the RTX5080 laptop:
  cloned to `C:\ClaudeCode\printlab`, Python 3.12 via winget, venv built,
  Desktop shortcut created, headless engine already authenticated (test forge
  responded without the Connect card).
- Fresh-clone fix landed: app.py creates `output/` on startup (it's
  gitignored, so new clones used to crash at mount time).
- Repo cleaned: `refs/_scratch_star.png` removed (byte-identical duplicate of
  `ref_45f048467c.png`, which stays — `parts/star_ornament.py` traces it on
  every rebuild).

## Model bake-off (2026-07-26)

Same hard prompt forged under six model/effort configs: a pour-over dripper
with a 60° cone, mug-rim shoulder, 3× 4 mm drain holes, 6 internal ribs, and
a 25 mm viewing window. Meshes scored geometrically (ray-cast wall profile
for cone angle and ribs, section interiors for holes).

| config | score | cone | ribs | holes | cm³ | min | own build runs |
|---|---|---|---|---|---|---|---|
| sonnet high  | 7/7 | 30.0° | 6 | 3 | 174.6 | 7.9 | 4 |
| fable high   | 7/7 | 30.0° | 6 | 3 | 178.1 | 12.4 | 0 |
| fable xhigh  | 7/7 | 30.0° | 6 | 3 | 100.6 | 13.4 | 0 |
| fable max    | 7/7 | 30.0° | 6 | 3 | 127.8 | 18.1 | 0 |
| fable medium | 6/7 | 30.0° | 6 | 3 | 84.0 | 8.7 | 0 |
| opus high    | 6/7 | 30.0° | 6 | 3 | 76.4 | 14.4 | 4 |

**The task is saturated** — every config, down to Sonnet and Fable at medium
effort, nailed the cone angle to 30.0°, produced exactly 6 ribs and exactly
3 holes of 4.0 mm, watertight and plate-fitting. Quality did not separate the
models, so the choice came down to behaviour and cost:

1. **Opus verifies its own geometry; Fable does not.** Raw streams show Opus
   spontaneously writing trimesh code to section its own STL, count interior
   rings, and measure hole diameters and window width — nothing in the forge
   prompt asks for that. Every Fable config wrote the script and stopped
   without ever executing it. Fable's blind output happened to be correct
   here, but this harness's only safety net is the model iterating on
   `watertight=True` / `plate_fit=OK`, and Fable doesn't use it.
2. **Opus 5 is half the token price** ($5/$25 vs $10/$50 per Mtok), so it
   burns roughly half the plan allowance per forge.
3. **`high`, not `xhigh`** — Opus already self-verifies at `high`, and
   Anthropic's guidance is to start there for Opus 5 and reserve `xhigh` for
   long-running (30 min+) agentic work. A forge is ~10-15 min.

Caveat: n=1 per config on one part. The round-2 replicates (opus xhigh ×2)
were cancelled part-way to stop burning plan usage, so `xhigh` on Opus is
untested here.

## Printability report (2026-07-26, done)

Acting on the bake-off's main finding. `lib3d.printability()` now measures
every build and `export()` prints it, so the engine gets shape feedback for
free instead of reinventing probes each forge:

- `bodies` — separate shells. Catches floating/disconnected geometry, which
  the prompt forbade but nothing ever checked.
- `bed_contact` cm² and `overhang%` (faces >50° off vertical, bed excluded).
- round through-holes inventoried by diameter — the thing a spec usually
  pins down ("three 4 mm drain holes").

The forge prompt now treats these as an acceptance gate, not just
`watertight=True`. `tools/rebuild_all.py` rebuilds all parts and fails on
regressions — run it after touching lib3d.py. UI rebuilds set
`PRINTLAB_FAST=1` to skip the slower scan and stay instant.

Two traps found while building it, both worth remembering:
- A hollow part's cavity is also a round interior ring, so the vase read as
  "8 holes, 22–38 mm". Holes are now judged relative to part size (under a
  quarter of the footprint). Verified both directions: a synthetic 3×4 mm
  plate reports `3x 4.0mm`, accent_lamp reports none.
- A sampled wall-thickness metric was tried and **removed** — it reported
  0.35 mm on a solid 20 mm cube, measuring corner artifacts rather than
  walls. A misleading number is worse than no number.
- Multi-body parts legitimately have more shells than named bodies
  (hinge_demo: 2 bodies, 3 shells — the rigid half is two leaves joined by
  the flex strap), so only single-body exports get the warning.

Still open: nothing shows the model a *picture*. Headless rendering needs
pyglet plus a GL context, which is unreliable on Windows; the numeric report
covers most of the value without that dependency.

## Real-hardware fits (2026-07-26, done)

The documented failure mode for LLM-generated 3D parts is inventing a
plausible-but-wrong dimension — geometry that is sound and numbers that are
made up. `M3 = 3.4 mm` used to live as prose in two files and nothing else
was covered, so every M4/M5/bearing/magnet part was a guess.

`lib3d` now carries the real numbers: `FIT` (M2–M8: clearance, tap, head,
countersink, nut across-flats, nut thickness, heat-set boss), `BEARING`
(bore/OD/width for 623–6801, 608, MR105), `COMMON` (batteries, credit card,
USB-C, 2020 extrusion, zip ties), and diametral clearances `CLEAR_PRESS`
0.05 / `CLEAR_SNUG` 0.20 / `CLEAR_SLIP` 0.40. Helpers: `fit()`,
`bolt_hole()`, `hex_pocket()`, `pocket()`.

`fit()` **raises on an unknown key rather than falling back to a guess** —
that is the whole point, so don't add a default. CLAUDE.md, TECHNIQUES.md
recipe 9, and the forge prompt all now say look it up, never estimate.

`tools/test_lib3d.py` covers the fits, the helper geometry, and the
printability measurements (including the two traps above: cavity-is-not-a-
hole, and disconnected-body detection). Run it plus `rebuild_all.py` after
touching lib3d.py.

Not done: no printer calibration. `parts/calibration_cube.py` exists purely
to be measured with calipers, but nothing consumes the measurement — a
stored per-printer offset applied to holes and clearances is the obvious
next step for parts that must physically fit.

## Working parts (parts/)

calibration_cube · car_lift_164 · dog_top_hat · hinge_demo · keychain_smith ·
phone_stand · star_ornament · table_lamp_shade (first Fable-forged part,
2026-07-19)

## Handoff rules

- Push main after every change; pull before working on the other PC.
- STLs (`output/`) are never committed — regenerate with Rebuild.
- Reference images a part traces live in `refs/` and MUST be committed
  (the part script needs them at rebuild time).
- Headless login is per-PC: first forge on a fresh PC may show the Connect
  card → `/login` once in the terminal it opens.
