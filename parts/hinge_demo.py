"""Rigid + flex hinge demo for the X2D dual nozzle.

Two rigid plates (PETG, body "rigid") joined by a flexible strap hinge
(TPU, body "flex"). The strap runs along the bottom so it prints straight
on the bed, and locks into each plate with through-pegs — mechanical
interlock plus the strong PETG/TPU bond. In Bambu Studio: open both body
files as one object, PETG on one nozzle, TPU on the other.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

import lib3d

P = lib3d.params({
    "plate_w": 40,      # each rigid plate, X
    "plate_d": 30,      # depth, Y
    "plate_t": 3,       # plate thickness
    "gap": 8,           # hinge gap between plates (the bend zone)
    "strap_w": 20,      # strap width, Y
    "strap_t": 1.2,     # TPU bend-zone thickness
    "strap_reach": 10,  # how far the strap runs into each plate
    "peg_r": 2.2,       # interlock pegs through the plates
})


def build():
    half = P["gap"] / 2
    plates = lib3d.union(
        lib3d.move(lib3d.box(P["plate_w"], P["plate_d"], P["plate_t"]),
                   x=-(half + P["plate_w"] / 2), z=P["plate_t"] / 2),
        lib3d.move(lib3d.box(P["plate_w"], P["plate_d"], P["plate_t"]),
                   x=half + P["plate_w"] / 2, z=P["plate_t"] / 2),
    )

    strap = lib3d.move(
        lib3d.box(P["gap"] + 2 * P["strap_reach"], P["strap_w"], P["strap_t"]),
        z=P["strap_t"] / 2)
    pegs = [lib3d.move(lib3d.cylinder(P["peg_r"], P["plate_t"]),
                       x=sx * (half + P["strap_reach"] / 2), y=sy * (P["strap_w"] / 4),
                       z=P["plate_t"] / 2)
            for sx in (-1, 1) for sy in (-1, 1)]
    flex = lib3d.union(strap, pegs)

    rigid = lib3d.difference(plates, flex)
    return {"rigid": rigid, "flex": flex}


if __name__ == "__main__":
    lib3d.export_multi(build(), "hinge_demo")
