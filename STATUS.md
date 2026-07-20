# PrintLab — status / handoff

Source of truth for cross-PC handoff. Update this when state changes.

## Current state (2026-07-19)

- **Engine: Fable at high effort** (was Opus) — `--model fable --effort high`
  in app.py's forge command.
- Set up and verified on BOTH PCs. This entry added from the RTX5080 laptop:
  cloned to `C:\ClaudeCode\printlab`, Python 3.12 via winget, venv built,
  Desktop shortcut created, headless engine already authenticated (test forge
  responded without the Connect card).
- Fresh-clone fix landed: app.py creates `output/` on startup (it's
  gitignored, so new clones used to crash at mount time).
- Repo cleaned: `refs/_scratch_star.png` removed (byte-identical duplicate of
  `ref_45f048467c.png`, which stays — `parts/star_ornament.py` traces it on
  every rebuild).

## Working parts (parts/)

calibration_cube · car_lift_164 · dog_top_hat · hinge_demo · keychain_smith ·
phone_stand · star_ornament

## Handoff rules

- Push main after every change; pull before working on the other PC.
- STLs (`output/`) are never committed — regenerate with Rebuild.
- Reference images a part traces live in `refs/` and MUST be committed
  (the part script needs them at rebuild time).
- Headless login is per-PC: first forge on a fresh PC may show the Connect
  card → `/login` once in the terminal it opens.
