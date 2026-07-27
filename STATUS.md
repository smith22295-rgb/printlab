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

Open improvement this surfaced: PrintLab never shows the model its finished
mesh. Opus builds its own measuring instrument to compensate; making that a
built-in step (render/measure after each build, feed it back) would help any
model and is the highest-value change to the forge loop.

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
