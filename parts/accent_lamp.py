"""Wireless table accent lamp — a vase-shaped lantern shade for restaurants.

Drop it over any standard battery LED tea light (38 mm dia) and it glows
through tall vertical slots; the open top throws a soft pool of light upward.
No wiring, no electronics — swap the tea light to "recharge". Built as one
revolved shell (smooth vase profile, ~3 mm wall), printed open-side-down so
the bed face is the table rim. Wall never exceeds ~35 deg from vertical, so
it prints with no supports.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

import numpy as np
from shapely.geometry import Polygon

import lib3d

P = lib3d.params({
    "height": 90,      # overall lamp height
    "base_dia": 64,    # diameter of the rim that sits on the table
    "bulge_dia": 72,   # widest belly diameter of the vase
    "bulge_z": 32,     # height of the widest point
    "top_dia": 28,     # outer diameter of the open top
    "wall": 2.8,       # shell wall thickness
    "slot_count": 10,  # vertical glow slots around the belly
    "slot_w": 5,       # slot width
    "slot_h": 38,      # slot height
    "slot_z": 34,      # center height of the slots
    "soften": 1.2,     # edge round-over radius (keep under half the wall)
})


def vase_r(z, base_r, bulge_r, top_r, bulge_z, height):
    """Smooth vase radius at height z: cosine-eased belly then neck."""
    if z <= bulge_z:
        t = z / bulge_z
        return base_r + (bulge_r - base_r) * (1 - np.cos(np.pi * t)) / 2
    t = (z - bulge_z) / (height - bulge_z)
    return top_r + (bulge_r - top_r) * (1 + np.cos(np.pi * t)) / 2


def build():
    h = P["height"]
    base_r = P["base_dia"] / 2
    bulge_r = P["bulge_dia"] / 2
    top_r = P["top_dia"] / 2
    wall = P["wall"]

    # wall cross-section in the (radius, z) plane: outer curve up, across the
    # top rim, inner curve back down, across the bottom rim
    zs = np.linspace(0, h, 80)
    outer = [(vase_r(z, base_r, bulge_r, top_r, P["bulge_z"], h), z) for z in zs]
    inner = [(r - wall, z) for r, z in reversed(outer)]
    prof = Polygon(outer + inner)
    prof = lib3d.soften(prof, P["soften"], keep_flat_y=0)
    shell = lib3d.revolve(list(prof.exterior.coords))
    if shell.volume < 0:  # winding depends on shapely's ring orientation
        shell.invert()

    # vertical glow slots, rounded ends, cut radially through the belly
    cutters = []
    reach = bulge_r + 5
    slot2d = lib3d.rounded_rect(P["slot_w"], P["slot_h"], P["slot_w"] / 2 - 0.01)
    blade = lib3d.rotate(lib3d.extrude(slot2d, reach), -90, [1, 0, 0])
    blade = lib3d.move(blade, z=P["slot_z"])
    for i in range(int(P["slot_count"])):
        cutters.append(lib3d.rotate(blade, i * 360 / P["slot_count"], [0, 0, 1]))
    return lib3d.difference(shell, cutters)


if __name__ == "__main__":
    lib3d.export(build(), "accent_lamp")
