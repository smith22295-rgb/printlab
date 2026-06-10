"""Sitting dog wearing a top hat — a cute desk figurine.

Built from overlapping ellipsoids + cylinders, all fused with the manifold
union so the result is one watertight solid. The whole figure is sliced flat
at the bottom so it stands stably and prints with its base on the plate.
Dog faces +Y; Z is up.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

import trimesh

import lib3d

P = lib3d.params({
    "head_r": 22,        # radius of the head ball
    "body_r": 26,        # girth of the seated rear/haunches
    "snout_len": 14,     # how far the snout pokes forward
    "ear_drop": 16,      # length of the floppy ears
    "leg_r": 9,          # radius of the front legs
    "tail_len": 18,      # length of the tail
    "hat_brim_r": 24,    # radius of the top-hat brim
    "hat_crown_r": 16,   # radius of the top-hat crown
    "hat_height": 28,    # height of the top-hat crown
    "base_cut": 5,       # everything below this Z is sliced off flat
})


def ellipsoid(rx, ry, rz, x=0, y=0, z=0):
    """A smooth ellipsoid centered at (x,y,z)."""
    s = trimesh.creation.icosphere(subdivisions=3, radius=1.0)
    s.apply_scale([rx, ry, rz])
    return lib3d.move(s, x, y, z)


def build():
    br = P["body_r"]
    hr = P["head_r"]
    parts = []

    # --- seated body: heavy rounded rear + an upright chest leaning forward
    parts.append(ellipsoid(br, br + 4, br + 2, x=0, y=-10, z=26))      # haunches
    parts.append(ellipsoid(br - 2, br - 2, 30, x=0, y=16, z=36))       # chest

    # --- front legs: two columns down to the base, with little paws
    for sx in (-1, 1):
        leg = lib3d.cylinder(P["leg_r"], 46)
        parts.append(lib3d.move(leg, 13 * sx, 30, 20))
        parts.append(ellipsoid(11, 14, 7, x=13 * sx, y=37, z=3))      # paw

    # --- head + face
    head_z = 62
    parts.append(ellipsoid(hr, hr, hr, x=0, y=26, z=head_z))
    parts.append(ellipsoid(10, P["snout_len"], 10, x=0, y=44, z=56))  # snout
    parts.append(ellipsoid(4, 4, 4, x=0, y=44 + P["snout_len"], z=58))  # nose
    for sx in (-1, 1):                                                 # floppy ears
        ear = ellipsoid(5, 11, P["ear_drop"])
        ear = lib3d.rotate(ear, 12 * sx, [0, 1, 0])                    # splay outward
        parts.append(lib3d.move(ear, 20 * sx, 22, head_z - 2))

    # --- tail: thick, leaning slightly back so it never floats
    tail = ellipsoid(7, 10, P["tail_len"], z=0)
    tail = lib3d.rotate(tail, 18, [1, 0, 0])
    parts.append(lib3d.move(tail, 0, -28, 46))

    # --- top hat: flat brim sitting on the head + tall crown
    head_top = head_z + hr
    brim_z = head_top - 3
    parts.append(lib3d.move(lib3d.cylinder(P["hat_brim_r"], 5), 0, 26, brim_z))
    crown_z = brim_z + 2 + P["hat_height"] / 2
    parts.append(lib3d.move(lib3d.cylinder(P["hat_crown_r"], P["hat_height"]),
                            0, 26, crown_z))

    dog = lib3d.union(parts)

    # slice the bottom flat so it stands and prints on a flat face
    slab = lib3d.box(400, 400, 400)
    slab = lib3d.move(slab, 0, 0, 200 + P["base_cut"])
    return lib3d.intersection(dog, slab)


if __name__ == "__main__":
    lib3d.export(build(), "dog_top_hat")
