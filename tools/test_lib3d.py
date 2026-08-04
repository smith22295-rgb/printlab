"""Tests for lib3d's measurement and fit helpers.

rebuild_all.py proves the parts still build; this proves the shared helpers
still MEAN the right thing. Both matter — a broken measurement reads as a
passing build.

    venv\\Scripts\\python.exe tools\\test_lib3d.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import lib3d  # noqa: E402

FAILED = []


def check(label, got, want, tol=0.0):
    # must never raise on a mismatch — a crashing assertion hides the result
    try:
        if isinstance(want, (int, float)) and not isinstance(want, bool):
            ok = isinstance(got, (int, float)) and abs(got - want) <= tol
        else:
            ok = got == want
    except TypeError:
        ok = False
    print(f"  {'ok  ' if ok else 'FAIL'} {label}: {got}" + ("" if ok else f" (want {want})"))
    if not ok:
        FAILED.append(label)


def raises(label, fn):
    try:
        fn()
    except KeyError:
        print(f"  ok   {label}")
        return
    except Exception as exc:  # noqa: BLE001
        print(f"  FAIL {label}: raised {type(exc).__name__}, want KeyError")
        FAILED.append(label)
        return
    print(f"  FAIL {label}: did not raise")
    FAILED.append(label)


print("fit table")
check("M3 clearance", lib3d.fit("M3"), 3.4)
check("M5 nut across-flats", lib3d.fit("M5", "nut_af"), 8.0)
check("M4 heat-set boss", lib3d.fit("M4", "heatset"), 5.6)
check("608 bearing OD", lib3d.BEARING["608"][1], 22)
check("AA cell diameter", lib3d.COMMON["AA"][0], 14.5)
# must fail loudly rather than invent a plausible number
raises("unknown fastener raises", lambda: lib3d.fit("M7"))
raises("unknown feature raises", lambda: lib3d.fit("M3", "nonsense"))

print("\nfit helpers")
check("bolt_hole M4 diameter", round(float(lib3d.bolt_hole("M4", 10).extents[0]), 2),
      4.5, 0.05)
hexp = lib3d.hex_pocket(lib3d.fit("M3", "nut_af"), 3)
check("hex_pocket across-flats (Y)", round(float(hexp.extents[1]), 2),
      5.5 + lib3d.CLEAR_SNUG, 0.05)
check("hex_pocket depth", round(float(hexp.extents[2]), 2), 3.0, 0.01)
check("pocket for 608 OD", round(float(lib3d.pocket(22, 7).extents[0]), 2),
      22 + lib3d.CLEAR_PRESS, 0.05)

print("\nrotate accepts named axes")
# CLAUDE.md documents rotate(m, deg, axis); a named axis must work, not just
# a vector, or the engine hits a bare float-conversion error
spun = lib3d.rotate(lib3d.box(10, 20, 30), 90, "x")
check("rotate('x') swaps Y and Z", round(float(spun.extents[1]), 1), 30.0, 0.01)
check("rotate([1,0,0]) matches",
      round(float(lib3d.rotate(lib3d.box(10, 20, 30), 90, [1, 0, 0]).extents[1]), 1),
      30.0, 0.01)
raises_value = []
try:
    lib3d.rotate(lib3d.box(1, 1, 1), 90, "w")
except ValueError:
    print("  ok   bad axis name raises ValueError")
except Exception as exc:  # noqa: BLE001
    print(f"  FAIL bad axis name raised {type(exc).__name__}")
    FAILED.append("bad axis name")
else:
    print("  FAIL bad axis name did not raise")
    FAILED.append("bad axis name")

print("\nprintability")
# a 60 mm disc, 6 mm thick, with three 4 mm through-holes
plate = lib3d.difference(
    lib3d.cylinder(30, 6),
    *[lib3d.move(lib3d.cylinder(2, 20), x, y, 0)
      for x, y in [(10, 0), (-5, 8.7), (-5, -8.7)]])
info = lib3d.printability(plate)
check("single body", info["bodies"], 1)
check("three 4mm holes found along Z", info["holes"].get((4.0, "Z")), 3)
check("bed contact ~ disc area minus holes",
      info["bed_contact_cm2"], (3.1416 * 30 ** 2 - 3 * 3.1416 * 2 ** 2) / 100, 0.5)

# holes do not only run along Z — a bracket's side-entry bolt hole is the
# commonest feature there is, and a Z-only scan reported none
cross = lib3d.difference(lib3d.box(40, 40, 30),
                         lib3d.rotate(lib3d.cylinder(2.25, 80), 90, "y"),
                         lib3d.move(lib3d.cylinder(1.7, 80), 12, 12, 0))
xz = lib3d.printability(cross)["holes"]
check("side hole found along X", xz.get((4.5, "X")), 1)
check("vertical hole still found along Z", xz.get((3.4, "Z")), 1)

# a countersink is two diameters on one axis
csink = lib3d.difference(lib3d.cylinder(20, 10), lib3d.cylinder(1.7, 30),
                         lib3d.move(lib3d.cylinder(3.15, 4), 0, 0, 3.5))
ch = lib3d.printability(csink)["holes"]
check("countersink reports pilot and counterbore",
      sorted(d for d, _ in ch), [3.4, 6.3])

# square slots are real features; they just aren't round
vent = lib3d.printability(lib3d.difference(lib3d.cylinder(30, 6),
                                           lib3d.box(6, 6, 20)))
check("square vent is not called a round hole", vent["holes"], {})
check("square vent counted as a non-round void", vent["other_voids"], 1)

# a hollow vase must NOT report its own cavity as a hole
vase = lib3d.difference(lib3d.cylinder(30, 50), lib3d.move(lib3d.cylinder(27, 48), 0, 0, 3))
check("cavity is not counted as a hole", lib3d.printability(vase)["holes"], {})

# degenerate input must return a result, not blow up the whole build
import trimesh  # noqa: E402
check("empty mesh returns empty report",
      lib3d.printability(trimesh.Trimesh()).get("empty"), True)
ripped = trimesh.creation.box((10, 10, 10))
ripped.update_faces([i > 1 for i in range(len(ripped.faces))])
check("non-watertight mesh still measures",
      lib3d.printability(ripped)["bodies"], 1)

# two separate lumps must be reported as floating geometry
pair = lib3d.union(lib3d.move(lib3d.box(10, 10, 10), -20, 0, 0),
                   lib3d.move(lib3d.box(10, 10, 10), 20, 0, 0))
check("disconnected bodies detected", lib3d.printability(pair, deep=False)["bodies"], 2)

# a flat slab has no overhang; a big flat ceiling does
slab = lib3d.box(20, 20, 5)
check("slab overhang", lib3d.printability(slab, deep=False)["overhang_pct"], 0.0, 0.1)
bridge = lib3d.difference(lib3d.box(30, 30, 20),
                          lib3d.move(lib3d.box(20, 20, 10), 0, 0, -2))
check("enclosed ceiling flags overhang",
      lib3d.printability(bridge, deep=False)["overhang_pct"] > 5, True)

print()
if FAILED:
    print(f"{len(FAILED)} FAILED: {', '.join(FAILED)}")
    sys.exit(1)
print("all lib3d checks passed")
