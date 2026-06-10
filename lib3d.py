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

def export(mesh, name):
    """Repair, validate, report, and write output/<name>.stl. Returns path."""
    mesh = mesh.copy()
    mesh.merge_vertices()
    mesh.update_faces(mesh.nondegenerate_faces())
    mesh.update_faces(mesh.unique_faces())
    mesh.remove_unreferenced_vertices()
    if not mesh.is_watertight:
        trimesh.repair.fill_holes(mesh)
    trimesh.repair.fix_normals(mesh)

    # rest on the plate: drop so min Z = 0
    mesh.apply_translation([0, 0, -mesh.bounds[0][2]])

    dims = mesh.extents
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
