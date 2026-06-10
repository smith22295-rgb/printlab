"""Desk phone stand — chunky wedge, fits a phone with a case, ~62 deg recline."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

import numpy as np
from shapely.geometry import Polygon

import lib3d

P = lib3d.params({
    "width": 70,        # X, side to side
    "slot_width": 16,   # gap the phone sits in (case-friendly)
    "lip_height": 16,   # front lip that stops the phone sliding
    "slot_floor": 7,    # thickness under the phone
    "recline_run": 32,  # how far back the rest leans over its rise
    "rest_top": 75,     # height of the back rest
    "rest_thick": 8,    # thickness of the back rest at the top
    "soften": 2,        # corner rounding radius, 0 = sharp edges
})


def build():
    lip_back = 10
    slot_back = lip_back + P["slot_width"]
    top_front_y = slot_back + P["recline_run"]
    profile = Polygon([
        (0, 0),                                   # front bottom
        (0, P["lip_height"]),                     # front lip
        (lip_back, P["lip_height"]),
        (lip_back, P["slot_floor"]),              # down into the slot
        (slot_back, P["slot_floor"]),             # slot floor
        (top_front_y, P["rest_top"]),             # reclined rest face
        (top_front_y + P["rest_thick"], P["rest_top"]),
        (top_front_y + P["rest_thick"] + 14, 8),  # sloped back
        (top_front_y + P["rest_thick"] + 14, 0),
    ])
    profile = lib3d.soften(profile, P["soften"], keep_flat_y=0)
    wedge = lib3d.extrude(profile, P["width"])
    # extruded in XY+Z; remap so width=X, depth=Y, height=Z
    wedge.apply_transform(np.array([
        [0, 0, 1, 0],
        [1, 0, 0, 0],
        [0, 1, 0, 0],
        [0, 0, 0, 1],
    ], dtype=float))
    return wedge


if __name__ == "__main__":
    lib3d.export(build(), "phone_stand")
