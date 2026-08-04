"""Rebuild every part and report pass/fail.

Parts are code and they all share lib3d, so a change there can silently break
an older part. Run this after touching lib3d.py (and before pushing):

    venv\\Scripts\\python.exe tools\\rebuild_all.py

Exits non-zero if any part fails to build, comes out non-watertight, or no
longer fits the plate.
"""
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARTS = ROOT / "parts"
VENV_PY = ROOT / "venv" / "Scripts" / "python.exe"


def main():
    scripts = sorted(p for p in PARTS.glob("*.py") if not p.name.startswith("_"))
    if not scripts:
        print("no parts found")
        return 0

    width = max(len(p.stem) for p in scripts) + 2
    failures = []
    print(f"rebuilding {len(scripts)} parts\n")
    for script in scripts:
        start = time.time()
        try:
            run = subprocess.run([str(VENV_PY), str(script)], cwd=ROOT,
                                 capture_output=True, text=True, timeout=300)
            out = (run.stdout + run.stderr).strip()
        except subprocess.TimeoutExpired:
            out, run = "TIMEOUT after 300s", None
        secs = time.time() - start

        watertight = "watertight=True" in out
        fits = "plate_fit=OK" in out
        ok = run is not None and run.returncode == 0 and watertight and fits

        why = []
        if run is None:
            why.append("timeout")
        elif run.returncode != 0:
            why.append(f"exit {run.returncode}")
        if not watertight:
            why.append("not watertight")
        if not fits:
            why.append("plate fit")

        # trust lib3d's own "!!" rather than re-judging: multi-body parts
        # legitimately have more shells than named bodies
        extra = ""
        m = re.search(r"bodies=(\d+) !!", out)
        if m:
            extra = f"  [{m.group(1)} separate bodies]"
        m = re.search(r"overhang=([\d.]+)%", out)
        if m and float(m.group(1)) > 20:
            extra += f"  [overhang {m.group(1)}%]"

        print(f"  {'PASS' if ok else 'FAIL'}  {script.stem:<{width}}"
              f"{secs:5.1f}s  {'' if ok else ', '.join(why)}{extra}")
        if not ok:
            failures.append((script.stem, ", ".join(why), out[-500:]))

    print()
    if failures:
        print(f"{len(failures)} FAILED\n")
        for stem, why, tail in failures:
            print(f"--- {stem}: {why}")
            print("\n".join("    " + ln for ln in tail.splitlines()[-8:]))
            print()
        return 1
    print(f"all {len(scripts)} parts OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
