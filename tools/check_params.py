"""Find dead parameters — knobs that don't actually move anything.

PrintLab's core promise is that every dimension in a part's `P` block can be
retuned for free. That silently breaks if a script declares a param and then
never reads it: you change the number, hit Rebuild, and nothing happens, with
no error to explain why.

This perturbs each param in turn, rebuilds, and compares the STL bytes
(rebuilds are deterministic, so any geometric change shows up as a different
hash). Identical bytes means the knob is dead.

A perturbation that makes the build FAIL counts as live — the value was
clearly read, it just didn't like the number.

    venv\\Scripts\\python.exe tools\\check_params.py [part ...]
"""
import ast
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARTS = ROOT / "parts"
OUT = ROOT / "output"
VENV_PY = ROOT / "venv" / "Scripts" / "python.exe"

# params that are meant to be inert at their default, or that we perturb
# specially because a naive nudge is meaningless
ENUMS = {"soften_style": ["round", "chamfer"]}


def read_params(part):
    src = (PARTS / f"{part}.py").read_text(encoding="utf-8")
    m = re.search(r"P\s*=\s*lib3d\.params\((\{.*?\})\)", src, re.S)
    if not m:
        return {}
    try:
        return ast.literal_eval(m.group(1))
    except (ValueError, SyntaxError):
        return {}


def build(part, overrides=None):
    """Rebuild and return (ok, stl_hash). Hash is None if nothing was written."""
    env = dict(os.environ)
    env["PRINTLAB_FAST"] = "1"          # skip the deep scan; we only need bytes
    env["PRINTLAB_P"] = json.dumps(overrides or {})
    stl = OUT / f"{part}.stl"
    before = stl.stat().st_mtime if stl.exists() else None
    proc = subprocess.run([str(VENV_PY), str(PARTS / f"{part}.py")], cwd=ROOT,
                          env=env, capture_output=True, text=True, timeout=240)
    if proc.returncode != 0 or not stl.exists():
        return False, None
    if before is not None and stl.stat().st_mtime == before:
        return False, None  # script exited 0 but wrote nothing
    return True, hashlib.md5(stl.read_bytes()).hexdigest()


def perturb(value):
    """A nudge big enough to move geometry, small enough to stay buildable."""
    if isinstance(value, bool):
        return not value
    if isinstance(value, int):
        # 0/1 are on/off flags read as `if P["x"]:` — bumping 1 to 3 leaves
        # them just as truthy and falsely reads as dead. Flip instead.
        if value in (0, 1):
            return 1 - value
        return value + 2 if value < 1000 else int(value * 1.2)
    if isinstance(value, float):
        return round(value * 1.3, 3) if value else 2.0
    if isinstance(value, str):
        return None  # handled by the caller via ENUMS
    return None


def check_part(part, advisory):
    body = (PARTS / f"{part}.py").read_text(encoding="utf-8")
    defaults = read_params(part)
    if not defaults:
        print(f"  {part}: no P block")
        return []
    ok, base = build(part)
    if not ok:
        print(f"  {part}: FAILED to build at its own defaults")
        return [(part, "<baseline>", "build failed")]

    dead = []
    for key, val in defaults.items():
        if key in ENUMS:
            options = [o for o in ENUMS[key] if o != val]
            new = options[0] if options else None
        elif isinstance(val, str):
            new = val + "X" if val else "X"
        else:
            new = perturb(val)
        if new is None:
            print(f"    -- {key}: skipped (no sensible nudge)")
            continue

        ok, h = build(part, {key: new})
        if not ok:
            verdict = "live (nudge broke the build)"
        elif h == base:
            # distinguish never-read from read-but-inert: a param used only
            # for a printed fit check is misleading in the UI, but it is a
            # different problem from one the script never looks at
            if re.search(rf'P\[["\']{re.escape(key)}["\']\]', body):
                verdict = "ADVISORY — read, but moves no geometry"
                advisory.append((part, key))
            else:
                verdict = "DEAD — never read at all"
                dead.append((part, key, f"{val!r} -> {new!r}"))
        else:
            verdict = "live"
        print(f"    {'!!' if h == base and ok else '  '} {key}: {val!r} -> {new!r}  {verdict}")

    build(part)  # leave the part's STL exactly as we found it
    return dead


def main():
    wanted = sys.argv[1:]
    parts = [p.stem for p in sorted(PARTS.glob("*.py"))
             if not wanted or p.stem in wanted]
    print(f"checking {len(parts)} parts for dead parameters\n")
    dead, advisory = [], []
    for part in parts:
        print(f"  {part}")
        dead += check_part(part, advisory)
        print()

    if advisory:
        print(f"{len(advisory)} advisory parameter(s) — read, but they move no")
        print("geometry (usually a printed fit check). Editing them in the UI")
        print("looks like it should resize the part, and does not:")
        for part, key in advisory:
            print(f"  {part}.{key}")
        print()

    if dead:
        print(f"{len(dead)} DEAD parameter(s) — never read at all:")
        for part, key, detail in dead:
            print(f"  {part}.{key}   ({detail})")
        print("\nA dead knob is a silent lie in the UI — the field is editable,")
        print("Rebuild succeeds, and the mesh is unchanged. Wire it into the")
        print("geometry or remove it from P.")
        return 1
    print("no dead parameters — every knob moves geometry")
    return 0


if __name__ == "__main__":
    sys.exit(main())
