"""PrintLab shared helpers. All units are MILLIMETERS.

Part scripts import this, build a trimesh.Trimesh, and call export(mesh, "name").
Booleans must go through union()/difference()/intersection() so the manifold
engine guarantees watertight output.
"""
import json
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


def text_polygons(text, size_mm, font="DejaVu Sans", weight="bold"):
    """Render text to shapely geometry. size_mm is the font size (cap height
    lands around 0.7 * size_mm). Returns geometry with holes handled (O, A...).
    """
    from matplotlib.font_manager import FontProperties
    from matplotlib.textpath import TextPath

    tp = TextPath((0, 0), text, size=size_mm,
                  prop=FontProperties(family=font, weight=weight))
    rings = [Polygon(p) for p in tp.to_polygons() if len(p) >= 3]
    rings = [r if r.is_valid else r.buffer(0) for r in rings]
    rings = [r for r in rings if r.area > 1e-6]
    rings.sort(key=lambda r: -r.area)

    # even containment depth = letter body, odd = hole in the letter above it
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
