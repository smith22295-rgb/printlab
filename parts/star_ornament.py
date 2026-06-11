"""Flat star tree ornament — traced from the reference image, with a top
hanging hole. Plan-silhouette extrude (TECHNIQUES recipe #6 image trace)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

import lib3d

REF = str(Path(__file__).parents[1] / "refs" / "ref_45f048467c.png")

P = lib3d.params({
    "width": 70,        # overall star width, mm
    "thick": 5,         # ornament thickness, mm
    "hole_dia": 4,      # hanging hole diameter, mm
    "hole_drop": 7,     # hole center distance below the top point, mm
    "soften": 2,        # corner round-over radius, mm (0 = off)
    "soften_style": "round",  # "round" or "chamfer"
})


def build():
    # Trace the dark star in the image, scaled and centered on origin.
    star = lib3d.image_outline(REF, P["width"])
    star = lib3d.soften(star, P["soften"], style=P["soften_style"])
    # Softening rounds the sharp points inward; rescale so the final width
    # matches the requested size.
    from shapely.affinity import scale as _scale
    minx, _, maxx, _ = star.bounds
    star = _scale(star, xfact=P["width"] / (maxx - minx),
                  yfact=P["width"] / (maxx - minx), origin="center")

    body = lib3d.extrude(star, P["thick"])

    # Hanging hole: centered on the top point (max-y, x~0), dropped down a bit
    # so there's solid material all around it.
    minx, miny, maxx, maxy = star.bounds
    cx = (minx + maxx) / 2
    cy = maxy - P["hole_drop"]
    hole = lib3d.cylinder(P["hole_dia"] / 2, P["thick"] * 3)
    hole.apply_translation([cx, cy, 0])

    return lib3d.difference(body, hole)


if __name__ == "__main__":
    lib3d.export(build(), "star_ornament")
