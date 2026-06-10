"""XYZ calibration cube — a true 20 mm cube with X/Y/Z engraved into the
three outward faces. Letters are recessed (not proud) so the outer faces stay
dead flat at the nominal size for caliper measurement."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

import numpy as np
from shapely.affinity import translate as shp_translate

import lib3d

P = lib3d.params({
    "size": 20,          # cube edge length, mm (the dimension you measure)
    "letter_size": 12,   # font size; cap height ~= 0.7 x this
    "letter_depth": 0.8, # how deep X/Y/Z are engraved into the faces, mm
})


def _letter_slab(ch, thick):
    """Letter centered on origin in XY, extruded 0..thick in +Z."""
    poly = lib3d.text_polygons(ch, P["letter_size"])
    minx, miny, maxx, maxy = poly.bounds
    poly = shp_translate(poly, -(minx + maxx) / 2, -(miny + maxy) / 2)
    return lib3d.extrude(poly, thick)


# axis permutations (new = M * old) to lay a flat letter onto a vertical face
_TO_X = np.array([[0, 0, 1, 0],   # old Z(thick)->X, old X(width)->Y, old Y->Z
                  [1, 0, 0, 0],
                  [0, 1, 0, 0],
                  [0, 0, 0, 1]], dtype=float)
_TO_Y = np.array([[1, 0, 0, 0],   # old X(width)->X, old Z(thick)->Y, old Y->Z
                  [0, 0, 1, 0],
                  [0, 1, 0, 0],
                  [0, 0, 0, 1]], dtype=float)


def build():
    half = P["size"] / 2
    t = P["letter_depth"]
    cube = lib3d.box(P["size"], P["size"], P["size"])

    # Z on the top face: slab sits just under z = half, cutting down into it
    z_cut = lib3d.move(_letter_slab("Z", t), z=half - t)

    # X on the +X face
    x_cut = _letter_slab("X", t)
    x_cut.apply_transform(_TO_X)
    x_cut = lib3d.move(x_cut, x=half - t)

    # Y on the +Y face
    y_cut = _letter_slab("Y", t)
    y_cut.apply_transform(_TO_Y)
    y_cut = lib3d.move(y_cut, y=half - t)

    return lib3d.difference(cube, x_cut, y_cut, z_cut)


if __name__ == "__main__":
    lib3d.export(build(), "calibration_cube")
