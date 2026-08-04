"""PrintLab shared helpers. All units are MILLIMETERS.

Part scripts import this, build a trimesh.Trimesh, and call export(mesh, "name").
Booleans must go through union()/difference()/intersection() so the manifold
engine guarantees watertight output.
"""
import json
import math
import os
from pathlib import Path

import numpy as np
import trimesh
from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import unary_union

OUT = Path(__file__).parent / "output"
OUT.mkdir(exist_ok=True)

# Bambu X2D, main-nozzle volume (X, Y, Z mm). Dual/aux-nozzle prints
# only get 235.5 in X — keep X under 235 if a part is meant for two colors.
PLATE = (256.0, 256.0, 260.0)


def params(defaults):
    """Wrap every part's P dict: P = lib3d.params({...}).

    The PrintLab app re-runs parts with tweaked values via the PRINTLAB_P
    env var (JSON) — no Claude call needed for size changes. Unknown keys
    are ignored; types follow the default's type (numbers stay numbers).
    """
    out = dict(defaults)
    raw = os.environ.get("PRINTLAB_P")
    if not raw:
        return out
    try:
        overrides = json.loads(raw)
    except (ValueError, TypeError):
        return out
    for key, val in overrides.items():
        if key not in out:
            continue
        cur = out[key]
        try:
            if isinstance(cur, bool):
                out[key] = bool(val)
            elif isinstance(cur, (int, float)):
                out[key] = float(val) if float(val) != int(float(val)) else int(float(val))
            else:
                out[key] = str(val)
        except (ValueError, TypeError):
            pass
    return out


# ---------------------------------------------------------------- booleans

def union(*meshes):
    flat = _flatten(meshes)
    return trimesh.boolean.union(flat, engine="manifold")


def difference(base, *cutters):
    return trimesh.boolean.difference([base, *_flatten(cutters)], engine="manifold")


def intersection(*meshes):
    return trimesh.boolean.intersection(_flatten(meshes), engine="manifold")


def _flatten(items):
    out = []
    for it in items:
        if isinstance(it, (list, tuple)):
            out.extend(it)
        else:
            out.append(it)
    return out


# ---------------------------------------------------------------- 2D shapes

def rounded_rect(w, h, r):
    """Axis-aligned rounded rectangle centered on origin (shapely polygon)."""
    r = min(r, w / 2, h / 2)
    core = Polygon([(-w / 2 + r, -h / 2 + r), (w / 2 - r, -h / 2 + r),
                    (w / 2 - r, h / 2 - r), (-w / 2 + r, h / 2 - r)])
    return core.buffer(r, quad_segs=24)


def soften(shape, r, keep_flat_y=None, style="round"):
    """Round EVERY corner of a 2D shape (convex and concave) by radius r.

    The standard anti-sharp-edge pass: apply to a silhouette/profile before
    extruding. r=0 returns the shape unchanged (the off switch). Features
    thinner than 2*r will vanish — keep r under half the thinnest feature.

    keep_flat_y: for VERTICAL profiles (side views), pass the bed line's y
    (usually 0) — everything along that line stays flat for bed contact
    while the rest of the profile gets rounded. Not needed for plan-view
    silhouettes, where the bed face is untouched by 2D softening.

    style: "round" (fillet, default) or "chamfer" (flat 45-degree bevel).
    """
    if not r or r <= 0:
        return shape
    q = 24
    js = "round" if style != "chamfer" else "bevel"
    if keep_flat_y is None:
        work = shape
    else:
        from shapely.affinity import translate as _translate
        from shapely.geometry import box as _sbox
        # extend the shape below the bed line so rounding can't curl it up
        work = unary_union([shape, _translate(shape, yoff=-3 * r)])
    out = (work.buffer(r, quad_segs=q, join_style=js)
               .buffer(-2 * r, quad_segs=q, join_style=js)
               .buffer(r, quad_segs=q, join_style=js))
    if keep_flat_y is not None:
        minx, miny, maxx, maxy = shape.bounds
        out = out.intersection(_sbox(minx - 1, keep_flat_y, maxx + 1, maxy + 1))
    return out


def _assemble_rings(rings):
    """Turn a soup of closed rings into polygons with holes (even-odd)."""
    rings = [r if r.is_valid else r.buffer(0) for r in rings]
    rings = [r for r in rings if r.area > 1e-6]
    rings.sort(key=lambda r: -r.area)
    shells, holes = [], []
    for r in rings:
        pt = r.representative_point()
        depth = sum(1 for other in rings if other is not r
                    and other.area > r.area and other.contains(pt))
        (shells if depth % 2 == 0 else holes).append(r)
    bodies = []
    for s in shells:
        mine = [h.exterior.coords for h in holes if s.contains(h.representative_point())]
        bodies.append(Polygon(s.exterior.coords, mine))
    return unary_union(bodies)


def text_polygons(text, size_mm, font="DejaVu Sans", weight="bold"):
    """Render text to shapely geometry. size_mm is the font size (cap height
    lands around 0.7 * size_mm). Returns geometry with holes handled (O, A...).
    """
    from matplotlib.font_manager import FontProperties
    from matplotlib.textpath import TextPath

    tp = TextPath((0, 0), text, size=size_mm,
                  prop=FontProperties(family=font, weight=weight))
    return _assemble_rings([Polygon(p) for p in tp.to_polygons() if len(p) >= 3])


def image_outline(image_path, width_mm, threshold=128, simplify_mm=0.2):
    """Trace the DARK shape in an image into 2D geometry, scaled to width_mm
    and centered on the origin. Light = background, dark = shape — works for
    kid drawings, logos, silhouettes, sketches. Extrude the result for flat
    ornaments; offset with .buffer() for cookie-cutter walls; difference it
    for engravings. Holes inside the shape are preserved.
    """
    import numpy as np
    from PIL import Image as _Image
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as _plt

    arr = np.asarray(_Image.open(image_path).convert("L"), dtype=float)
    arr = arr[::-1]  # image rows run downward; geometry y runs up
    fig = _plt.figure()
    try:
        cs = _plt.contour(arr, levels=[threshold])
        try:
            segs = cs.allsegs[0]
        except AttributeError:
            segs = [p.vertices for p in cs.get_paths()]
    finally:
        _plt.close(fig)
    geom = _assemble_rings([Polygon(s) for s in segs if len(s) >= 3])
    if geom.is_empty:
        raise ValueError("no shape found in the image — adjust threshold")

    from shapely.affinity import scale as _scale, translate as _translate
    minx, miny, maxx, maxy = geom.bounds
    f = width_mm / (maxx - minx)
    geom = _scale(geom, xfact=f, yfact=f, origin=(0, 0))
    if simplify_mm:
        geom = geom.simplify(simplify_mm)
    minx, miny, maxx, maxy = geom.bounds
    return _translate(geom, -(minx + maxx) / 2, -(miny + maxy) / 2)


# ---------------------------------------------------------------- 3D builders

def extrude(polygon, height):
    """Extrude a shapely Polygon/MultiPolygon in +Z. Returns one mesh."""
    if isinstance(polygon, MultiPolygon):
        parts = [trimesh.creation.extrude_polygon(p, height) for p in polygon.geoms]
        return trimesh.util.concatenate(parts)
    return trimesh.creation.extrude_polygon(polygon, height)


def box(w, d, h, center=True):
    m = trimesh.creation.box(extents=[w, d, h])
    if not center:
        m.apply_translation([w / 2, d / 2, h / 2])
    return m


def rounded_box(w, d, h, r=2.0):
    """Brick with rounded vertical edges AND rounded top edges; the bottom
    face stays FLAT (it's the bed-contact face — rounding it kills adhesion
    and creates sub-45-degree overhangs). Sits on z=0, centered in XY.
    """
    r = min(r, w / 2 - 0.1, d / 2 - 0.1, h / 2)
    if r <= 0:
        return move(box(w, d, h), z=h / 2)
    s2d = rounded_rect(w, d, r)
    parts = [
        extrude(s2d, h - r),                  # full footprint, below the roll
        extrude(s2d.buffer(-r), h),           # inset core, full height
    ]
    # roll the top edges: cylinders along the straight runs, spheres at corners
    cx, cy = w / 2 - r, d / 2 - r
    for sy in (-1, 1):
        parts.append(move(rotate(cylinder(r, w - 2 * r), 90, [0, 1, 0]),
                          y=sy * cy, z=h - r))
    for sx in (-1, 1):
        parts.append(move(rotate(cylinder(r, d - 2 * r), 90, [1, 0, 0]),
                          x=sx * cx, z=h - r))
    sphere = trimesh.creation.icosphere(subdivisions=3, radius=r)
    for sx in (-1, 1):
        for sy in (-1, 1):
            parts.append(move(sphere, x=sx * cx, y=sy * cy, z=h - r))
    return union(parts)


def cylinder(radius, height, sections=64):
    return trimesh.creation.cylinder(radius=radius, height=height, sections=sections)


def revolve(profile_points, sections=96):
    """Lathe: spin a 2D profile around the Z axis — bowls, vases, knobs,
    funnels, feet. profile_points = [(radius, z), ...] with radius >= 0;
    for a SOLID part, start and end ON the axis, e.g.
    [(0, 0), (20, 0), (16, 35), (0, 35)] is a tapered cup blank.
    """
    pts = np.asarray(profile_points, dtype=float)
    return trimesh.creation.revolve(pts, sections=sections)


def sweep(polygon, path_points):
    """Sweep a 2D shapely cross-section along a 3D path — hooks, handles,
    tubes, curved brackets. Round section: Point(0, 0).buffer(r, quad_segs=24)
    (from shapely.geometry). Keep the path smooth and non-self-intersecting;
    sample curves with ~20+ points.
    """
    return trimesh.creation.sweep_polygon(
        polygon, np.asarray(path_points, dtype=float), cap=True)


def move(mesh, x=0, y=0, z=0):
    m = mesh.copy()
    m.apply_translation([x, y, z])
    return m


def rotate(mesh, degrees, axis):
    m = mesh.copy()
    m.apply_transform(trimesh.transformations.rotation_matrix(
        np.radians(degrees), axis))
    return m


# ---------------------------------------------------------------- export

def _clean(mesh):
    m = mesh.copy()
    m.merge_vertices()
    m.update_faces(m.nondegenerate_faces())
    m.update_faces(m.unique_faces())
    m.remove_unreferenced_vertices()
    if not m.is_watertight:
        trimesh.repair.fill_holes(m)
    trimesh.repair.fix_normals(m)
    return m


def _clear_bodies(name):
    for old in OUT.glob(f"{name}.*.stl"):
        old.unlink()


# Faces steeper than this from vertical need support on an FDM printer.
OVERHANG_LIMIT_DEG = 50.0


def printability(mesh, deep=True):
    """Measure the finished mesh the way a printer cares about.

    The forge loop used to only prove the mesh was CLOSED, never that it was
    the shape that was asked for — so the engine would write geometry, see
    watertight=True, and stop. These are the spec-independent facts that
    catch the rest: floating shells, surfaces that need support, a part that
    barely touches the bed, and an inventory of the round through-holes so
    hole counts and diameters can be checked without hand-written probes.
    """
    info = {}

    # separate shells: "no floating geometry" was a rule nothing verified
    try:
        info["bodies"] = len(mesh.split(only_watertight=False))
    except Exception:  # noqa: BLE001
        info["bodies"] = None

    nz = mesh.face_normals[:, 2]
    areas = mesh.area_faces
    zmin = mesh.bounds[0][2]

    # bed contact: down-facing faces sitting on the plate
    face_z = mesh.triangles[:, :, 2].max(axis=1)
    on_bed = (nz < -0.99) & (face_z <= zmin + 0.05)
    info["bed_contact_cm2"] = round(float(areas[on_bed].sum()) / 100, 1)

    # overhangs: down-facing and more than OVERHANG_LIMIT_DEG off vertical,
    # not counting the faces already resting on the plate
    steep = (nz < -math.sin(math.radians(OVERHANG_LIMIT_DEG))) & ~on_bed
    total = float(areas.sum())
    info["overhang_pct"] = round(100.0 * float(areas[steep].sum()) / total, 1) if total else 0.0

    if not deep:
        return info

    # Round through-holes, grouped by diameter (what a spec usually pins down).
    # A hollow part's own cavity is also a round interior ring, so holes are
    # judged relative to the part: anything wider than a quarter of the
    # footprint is the cavity, not a drilled hole.
    holes = {}
    try:
        zlo, zhi = float(mesh.bounds[0][2]), float(mesh.bounds[1][2])
        span = zhi - zlo
        max_dia = min(0.25 * float(max(mesh.extents[0], mesh.extents[1])), 25.0)
        for f in np.linspace(0.02, 0.98, 28):
            sec = mesh.section(plane_origin=[0, 0, zlo + span * f],
                               plane_normal=[0, 0, 1])
            if sec is None:
                continue
            planar, _ = sec.to_2D()
            found = {}
            for poly in planar.polygons_full:
                for ring in poly.interiors:
                    ring_poly = Polygon(ring)
                    a = ring_poly.area
                    if a <= 0.75:  # numerical speck
                        continue
                    dia = 2.0 * math.sqrt(a / math.pi)
                    # circular? compare area against its own perimeter's circle
                    circ = 4 * math.pi * a / (ring_poly.length ** 2)
                    if circ > 0.80 and dia <= max_dia:
                        key = round(dia, 1)
                        found[key] = found.get(key, 0) + 1
            for dia, n in found.items():
                holes[dia] = max(holes.get(dia, 0), n)
    except Exception:  # noqa: BLE001
        holes = {}
    info["holes"] = holes
    return info


def format_report(info, expect_bodies=1):
    """expect_bodies=None: report the shell count without judging it.

    A multi-material part can legitimately have more shells than named bodies
    (hinge_demo's rigid half is two leaves held together by the flex strap),
    so only single-body exports get the floating-geometry warning.
    """
    bits = [f"bodies={info.get('bodies')}"]
    if (expect_bodies is not None and info.get("bodies")
            and info["bodies"] != expect_bodies):
        bits[-1] += " !!"
    bits.append(f"bed_contact={info.get('bed_contact_cm2')} cm2")
    bits.append(f"overhang={info.get('overhang_pct')}% >{OVERHANG_LIMIT_DEG:.0f}deg")
    line = "  " + "  ".join(bits)
    holes = info.get("holes") or {}
    if holes:
        inv = ", ".join(f"{n}x {d}mm" for d, n in sorted(holes.items()))
        line += f"\n  round holes: {inv}"
    return line


def export(mesh, name):
    """Repair, validate, report, and write output/<name>.stl. Returns path."""
    mesh = _clean(mesh)
    # rest on the plate: drop so min Z = 0
    mesh.apply_translation([0, 0, -mesh.bounds[0][2]])

    dims = mesh.extents
    _clear_bodies(name)  # part may have been multi-body before
    path = OUT / f"{name}.stl"
    mesh.export(path)

    fit = "OK" if all(d <= p for d, p in zip(dims, PLATE)) else "TOO BIG"
    print(f"[{name}] watertight={mesh.is_watertight}  "
          f"dims={dims[0]:.1f} x {dims[1]:.1f} x {dims[2]:.1f} mm  "
          f"volume={mesh.volume / 1000:.1f} cm3  tris={len(mesh.faces)}  "
          f"plate_fit={fit}")
    # PRINTLAB_FAST=1 during UI rebuilds: skip the slower shape measurements
    # so dimension tweaks stay instant.
    print(format_report(printability(mesh,
                                     deep=os.environ.get("PRINTLAB_FAST") != "1")))
    print(f"  -> {path}")
    if not mesh.is_watertight:
        print("  !! NOT WATERTIGHT — fix the geometry before printing")
    return path


# X2D dual-nozzle: two-color/two-material prints lose width to the aux nozzle
DUAL_X = 235.5


def seam_tabs(span, height, depth=4.0, tooth=None, flare=None):
    """Dovetail interlock teeth for a multi-material seam. NEVER butt two
    materials along a straight line — it's a pre-made crack.

    Builds alternating dovetail teeth on the seam plane X=0, extending into
    +X by `depth`, running along Y (centered on 0), Z from 0 to `height`.
    Teeth are wider at the tip than the root, so the joint locks in both
    pull directions and interweaves along the seam. Zero clearance — the
    bodies print together and fuse.

    Usage for body A (owns x<0) meeting body B (owns x>0), both built
    butting at x=0:
        tabs = seam_tabs(seam_length, part_height)   # orient with move/rotate
        a = lib3d.union(a, tabs)
        b = lib3d.difference(b, tabs)
    """
    if tooth:
        n = max(2, int(round(span / (2 * tooth))))
    else:
        n = max(2, int(round(span / 12.0)))  # ~6 mm teeth by default
    pitch = span / n
    if flare is None:
        flare = pitch * 0.15
    flare = min(flare, pitch * 0.2)
    root, tip = pitch / 2 - flare, pitch / 2 + flare

    clip = Polygon([(-1, -span / 2), (depth + 1, -span / 2),
                    (depth + 1, span / 2), (-1, span / 2)])
    teeth = []
    for k in range(n):
        yc = -span / 2 + (k + 0.5) * pitch
        tooth_poly = Polygon([
            (0, yc - root / 2), (depth, yc - tip / 2),
            (depth, yc + tip / 2), (0, yc + root / 2),
        ]).intersection(clip)
        if tooth_poly.area > 1e-6:
            teeth.append(tooth_poly)
    return extrude(unary_union(teeth), height)


def export_multi(bodies, name):
    """Two-color/two-material export for the X2D's dual nozzles.

    bodies: dict like {"base": mesh, "accent": mesh} — NON-overlapping meshes
    positioned relative to each other in one coordinate frame. Writes
    output/<name>.<body>.stl per body plus a combined output/<name>.stl
    preview. In Bambu Studio: open all body files together, answer "load as
    a single object with multiple parts", assign a filament to each part.
    """
    for key in bodies:
        if not all(c.isalnum() or c == "_" for c in key):
            raise ValueError(f"body name '{key}' must be letters/digits/_")
    cleaned = {k: _clean(m) for k, m in bodies.items()}

    drop = min(m.bounds[0][2] for m in cleaned.values())
    for m in cleaned.values():
        m.apply_translation([0, 0, -drop])

    combined = trimesh.util.concatenate(list(cleaned.values()))
    dims = combined.extents
    fit = "OK" if (dims[0] <= DUAL_X and dims[1] <= PLATE[1]
                   and dims[2] <= PLATE[2]) else "TOO BIG (dual-nozzle X cap is 235.5)"
    print(f"[{name}] {len(cleaned)} bodies  "
          f"dims={dims[0]:.1f} x {dims[1]:.1f} x {dims[2]:.1f} mm  plate_fit={fit}")
    print(format_report(
        printability(combined, deep=os.environ.get("PRINTLAB_FAST") != "1"),
        expect_bodies=None))

    keys = list(cleaned)
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            try:
                import warnings
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")  # empty intersection = good
                    inter = trimesh.boolean.intersection(
                        [cleaned[a], cleaned[b]], engine="manifold")
                    vol = inter.volume if len(inter.faces) else 0.0
                if vol > 10:  # mm3 — flush faces are fine, volume isn't
                    print(f"  !! bodies '{a}' and '{b}' overlap by "
                          f"{vol / 1000:.2f} cm3 — fix before printing")
            except Exception:
                pass

    _clear_bodies(name)
    paths = []
    for key, m in cleaned.items():
        path = OUT / f"{name}.{key}.stl"
        m.export(path)
        paths.append(path)
        print(f"  [{key}] watertight={m.is_watertight}  "
              f"volume={m.volume / 1000:.1f} cm3  tris={len(m.faces)}")
        if not m.is_watertight:
            print(f"  !! body '{key}' NOT WATERTIGHT — fix before printing")
    combined.export(OUT / f"{name}.stl")
    print(f"  -> {OUT / name}.*.stl ({len(paths)} bodies + combined preview)")
    return paths


# --------------------------------------------------------------- real fits
# Measured/standard dimensions for hardware parts actually have to fit.
# The common failure when generating 3D parts is inventing a plausible number
# instead of using the real one, so LOOK IT UP here — never estimate.
#
# Screw values are ISO 273 medium clearance, DIN 912 socket-cap heads,
# DIN 934 hex nuts, DIN 965 countersunk heads. Heat-set inserts are Ruthex /
# CNC Kitchen standard and DO vary by brand — check yours if the fit matters.
#
#   clear     free-running clearance hole (bolt passes through)
#   tap       self-tapping pilot hole into plastic
#   head      socket-cap head diameter (counterbore this + CLEAR_PRESS)
#   csink     countersunk (flat) head diameter at the surface
#   nut_af    hex nut across the flats -> use nut_pocket()
#   nut_thick hex nut thickness
#   heatset   boss hole diameter for a heat-set threaded insert
FIT = {
    "M2":   dict(clear=2.4, tap=1.6, head=3.8, csink=4.4, nut_af=4.0,
                 nut_thick=1.6, heatset=3.2),
    "M2.5": dict(clear=2.9, tap=2.1, head=4.5, csink=5.3, nut_af=5.0,
                 nut_thick=2.0, heatset=3.6),
    "M3":   dict(clear=3.4, tap=2.5, head=5.5, csink=6.3, nut_af=5.5,
                 nut_thick=2.4, heatset=4.0),
    "M4":   dict(clear=4.5, tap=3.3, head=7.0, csink=8.2, nut_af=7.0,
                 nut_thick=3.2, heatset=5.6),
    "M5":   dict(clear=5.5, tap=4.2, head=8.5, csink=9.9, nut_af=8.0,
                 nut_thick=4.0, heatset=6.4),
    "M6":   dict(clear=6.6, tap=5.0, head=10.0, csink=11.7, nut_af=10.0,
                 nut_thick=5.0, heatset=8.0),
    "M8":   dict(clear=9.0, tap=6.8, head=13.0, csink=15.2, nut_af=13.0,
                 nut_thick=6.5, heatset=10.0),
}

# Deep-groove ball bearings: (bore, outer diameter, width) in mm.
BEARING = {
    "623": (3, 10, 4),    "624": (4, 13, 5),   "625": (5, 16, 5),
    "626": (6, 19, 6),    "608": (8, 22, 7),   "688": (8, 16, 5),
    "6800": (10, 19, 5),  "6801": (12, 21, 5), "MR105": (5, 10, 4),
}

# Everyday objects, so a part is sized against reality rather than a guess.
# (diameter, length) for cylinders; (x, y, z) for boxes.
COMMON = {
    "AA": (14.5, 50.5), "AAA": (10.5, 44.5), "C": (26.2, 50.0),
    "18650": (18.6, 65.2), "CR2032": (20.0, 3.2), "CR2016": (20.0, 1.6),
    "9V": (26.5, 17.5, 48.5),
    "credit_card": (85.6, 54.0, 0.76),
    "tea_light_led": (38.0, 19.0),
    "usb_c_port": (9.0, 3.2),
    "2020_extrusion": (20.0, 20.0),   # slot opening 6.0
    "paracord_550": (4.0,),
    "zip_tie_std": (4.8, 1.2), "zip_tie_small": (2.5, 1.0),
}

# Diametral clearance to ADD to a nominal size for the fit you want.
CLEAR_PRESS = 0.05   # magnet/bearing seat that should not move
CLEAR_SNUG = 0.20    # goes in by hand, stays put
CLEAR_SLIP = 0.40    # free to move / print-in-place (PLA; +0.05 for PETG)


def fit(size, feature="clear"):
    """Look up a hardware dimension. Raises on anything unknown.

    Deliberately loud: a wrong-but-plausible number is the failure mode this
    table exists to prevent, so an unknown key must never fall back to a guess.
    """
    try:
        spec = FIT[size]
    except KeyError:
        raise KeyError(f"unknown fastener {size!r}; known: {sorted(FIT)}") from None
    try:
        return spec[feature]
    except KeyError:
        raise KeyError(f"{size} has no {feature!r}; known: "
                       f"{sorted(spec)}") from None


def bolt_hole(size, depth, feature="clear", extra=0.0):
    """Cylinder to difference() out for a fastener. Centred on the origin,
    running +Z from z=0. Give `depth` a mm or two of overshoot so the cut
    breaks cleanly through both faces."""
    return cylinder((fit(size, feature) + extra) / 2.0, depth)


def hex_pocket(across_flats, depth, clearance=CLEAR_SNUG):
    """Hex prism for trapping a nut. across_flats is the nut's AF size —
    use fit(size, 'nut_af'). Extruded +Z from z=0; vertices land on the X
    axis, so the flat-to-flat span runs along Y."""
    r = (across_flats + clearance) / 2.0 / math.cos(math.radians(30))
    pts = [(r * math.cos(math.radians(a)), r * math.sin(math.radians(a)))
           for a in range(0, 360, 60)]
    return extrude(Polygon(pts), depth)


def pocket(nominal_dia, depth, clearance=CLEAR_PRESS):
    """Round seat for a magnet or bearing OD, sized with a real fit
    clearance instead of the nominal diameter."""
    return cylinder((nominal_dia + clearance) / 2.0, depth)
