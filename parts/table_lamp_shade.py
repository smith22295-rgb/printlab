"""Cordless restaurant-table accent lamp — a tulip-shaped glow shade.

There is no wiring: the shade is a hollow shell that simply lifts off and
drops back over a small rechargeable LED puck light sitting on the table.
Print it in TRANSLUCENT filament (white/amber PLA or PETG) with the thin
2 mm wall and it lights up like a candle; the heavy 5 mm skirt at the
bottom keeps the low centre of gravity a tall shade needs on a wobbly
restaurant table.

Construction (TECHNIQUES.md #3): one smooth revolve for the outer body,
a second revolve for the inner cavity, differenced out. The bottom is
open (that's how the light goes in) so the bed-contact face is a wide
flat ring — great adhesion, no supports, prints upright as-is.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

import numpy as np
from shapely.geometry import Polygon

import lib3d

P = lib3d.params({
    "height": 170,        # total height of the shade
    "base_dia": 88,       # widest point, at the table
    "waist_dia": 70,      # pinched waist diameter
    "waist_at": 0.30,     # height of the waist, as a fraction of height
    "belly_dia": 78,      # upper bulge diameter
    "belly_at": 0.62,     # height of the bulge, as a fraction of height
    "neck_dia": 22,       # diameter of the chimney at the very top
    "vent_dia": 10,       # hole through the top (heat vent + lift handle)
    "wall": 2.0,          # shell thickness — thinner glows brighter
    "skirt_wall": 5.0,    # thicker wall low down, for ballast
    "skirt_height": 22,   # how far up the heavy skirt runs
    "puck_dia": 66,       # your LED puck light's diameter (it must fit under)
    "puck_height": 26,    # ...and its height, so the chamber is checked to fit
    "foot_chamfer": 1.2,  # small bevel on the bottom outside edge
    "soften": 2,              # corner rounding radius, 0 = sharp edges
    "soften_style": "round",  # "round" or "chamfer" (flat 45-deg bevel)
})

SAMPLES = 120  # profile resolution up the height


def _outer_radius(zs):
    """Smooth tulip silhouette: base -> waist -> belly -> neck."""
    h = P["height"]
    ctrl_z = [0.0, P["waist_at"] * h, P["belly_at"] * h, h]
    ctrl_r = [P["base_dia"] / 2, P["waist_dia"] / 2,
              P["belly_dia"] / 2, P["neck_dia"] / 2]
    raw = np.interp(zs, ctrl_z, ctrl_r)
    # round off the interpolation kinks so the silhouette reads as one curve
    win = max(3, int(len(zs) * 0.16) | 1)
    pad = np.pad(raw, win // 2, mode="edge")
    return np.convolve(pad, np.ones(win) / win, mode="valid")


def _wall_at(zs):
    """Heavy near the table, thin higher up, blended over 8 mm."""
    t = np.clip((zs - P["skirt_height"]) / 8.0, 0.0, 1.0)
    return P["skirt_wall"] + (P["wall"] - P["skirt_wall"]) * t


def _to_profile(poly):
    """Shapely ring -> [(radius, z), ...] running bottom to top on the axis."""
    ring = list(poly.exterior.coords)[:-1]
    keep = [i for i, p in enumerate(ring) if p[0] > 1e-6]
    # the kept indices are contiguous modulo len(ring) — find where the run starts
    start = 0
    for n, i in enumerate(keep):
        if ring[(i - 1) % len(ring)][0] <= 1e-6:
            start = n
            break
    pts = [ring[i] for i in keep[start:] + keep[:start]]
    if pts[0][1] > pts[-1][1]:
        pts.reverse()
    return [(0.0, pts[0][1])] + [(p[0], p[1]) for p in pts] + [(0.0, pts[-1][1])]


def build():
    h = P["height"]
    ch = P["foot_chamfer"]
    zs = np.linspace(ch, h, SAMPLES)
    r_out = _outer_radius(zs)

    # --- outer body: silhouette polygon, softened, then spun around Z
    sil = Polygon([(0.0, 0.0), (P["base_dia"] / 2 - ch, 0.0)]
                  + [(float(r), float(z)) for r, z in zip(r_out, zs)]
                  + [(0.0, h)])
    sil = lib3d.soften(sil, P["soften"], keep_flat_y=0, style=P["soften_style"])
    body = lib3d.revolve(_to_profile(sil))

    # --- cavity: the same curve pulled in by the wall thickness.
    # Starts below the bed so the bottom stays open for the puck light.
    zc = np.linspace(0.0, h - P["wall"], SAMPLES)
    r_in = np.maximum(_outer_radius(zc) - _wall_at(zc), 0.5)
    cav_pts = ([(0.0, -1.0), (float(r_in[0]), -1.0)]
               + [(float(r), float(z)) for r, z in zip(r_in, zc)]
               + [(0.0, float(zc[-1]))])
    lamp = lib3d.difference(body, lib3d.revolve(cav_pts))

    # --- vent / lift hole straight through the top of the chimney
    vent = lib3d.cylinder(P["vent_dia"] / 2, 40)
    lamp = lib3d.difference(lamp, lib3d.move(vent, z=h - 10))

    # narrowest interior anywhere the puck actually occupies
    clear = 2 * r_in[zc <= P["puck_height"]].min() - P["puck_dia"]
    print(f"  puck clearance in the bottom chamber: {clear:.1f} mm"
          f" ({'OK' if clear > 1 else 'TOO TIGHT — raise base_dia'})")
    return lamp


if __name__ == "__main__":
    lib3d.export(build(), "table_lamp_shade")
