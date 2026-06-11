"""1:64 diecast service lift — drive-on 4-post hydraulic lift, detailed.

Two runways the car's wheels sit on, raised on four posts over an open bay so
you can see underneath (the whole point of a lift). Each runway is one solid
side-profile (ramp wedge -> flat deck -> back wheel stop) so it's watertight by
construction. Realistic garage details: traction-tread grooves milled across
the deck, a ladder frame of side rails + diagonal X-braces tying the posts,
a cross safety bar between the runways, a hydraulic power cabinet with a motor
drum at one corner, and anchor-bolt holes through the base so it can be lagged
to a shop floor.

Reference car: Hot Wheels / Matchbox 1:64 ~ 78 x 32 x 25 mm, wheel track ~26 mm.
Print flat on the bed (base down). The deck underside is a horizontal overhang —
light supports under the two runways come out clean (use the X2D's nozzle-2
support filament).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

import numpy as np
from shapely.geometry import Polygon

import lib3d

P = lib3d.params({
    "car_length": 78,       # reference 1:64 car length (sizes the deck)
    "deck_length": 95,      # flat drive deck, car length + room + stop
    "lift_height": 50,      # height of the drive surface above the bed
    "ramp_length": 55,      # run of the drive-up ramp (shallower = easier)
    "runway_width": 14,     # width of each wheel runway
    "track_gap": 12,        # open gap between the two runways
    "deck_thickness": 5,    # thickness of the raised deck slab
    "post_size": 9,         # square corner post (X = Y)
    "wheel_stop": 5,        # height of the lip at the back so the car stops
    "base_thickness": 5,    # base frame plate under the posts
    "tread": 1.2,           # traction groove depth milled across the deck, 0 = smooth
    "tread_pitch": 6,       # spacing between tread grooves
    "control_box": 1,       # 1 = hydraulic power cabinet + motor at one corner
    "bolt_holes": 1,        # 1 = anchor-bolt holes through the base, 0 = off
    "braces": 1,            # 1 = diagonal X-braces + side rails between posts
    "soften": 2,            # corner rounding radius, 0 = sharp edges
})


def runway():
    """One wheel runway as a single extruded side profile (X across, Z up):
    solid ramp wedge -> thin raised deck -> back wheel stop. Extruded by
    runway_width, then stood up so its width runs along Y."""
    ramp = P["ramp_length"]
    deck_top = P["lift_height"]
    deck_bot = deck_top - P["deck_thickness"]
    deck_end = ramp + P["deck_length"]
    stop_h = P["wheel_stop"]
    stop_w = 4.0

    profile = Polygon([
        (0, 0),                                   # ramp toe on the bed
        (ramp, deck_top),                         # up the ramp to deck level
        (deck_end, deck_top),                     # flat drive deck
        (deck_end, deck_top + stop_h),            # wheel stop, inner face
        (deck_end + stop_w, deck_top + stop_h),   # stop top
        (deck_end + stop_w, deck_bot),            # stop / deck back face
        (ramp, deck_bot),                         # deck underside (open bay)
        (ramp, 0),                                # back face of the ramp wedge
    ])
    profile = lib3d.soften(profile, P["soften"], keep_flat_y=0)

    m = lib3d.extrude(profile, P["runway_width"])      # width along +Z for now
    m = lib3d.move(m, z=-P["runway_width"] / 2)        # center the width on 0
    m = lib3d.rotate(m, 90, [1, 0, 0])                 # stand up: width -> Y
    return m


def diag_brace(x0, x1, z0, z1, y, thick_y, thick_z):
    """A flat strut spanning from (x0,z0) to (x1,z1) in the X-Z plane at a
    given Y. Built as a box on +X, rotated about Y to lie along the diagonal."""
    dx, dz = x1 - x0, z1 - z0
    length = float(np.hypot(dx, dz))
    angle = float(np.degrees(np.arctan2(dz, dx)))
    bar = lib3d.box(length, thick_y, thick_z)          # centered on origin
    bar = lib3d.rotate(bar, angle, [0, 1, 0])
    return lib3d.move(bar, x=(x0 + x1) / 2, y=y, z=(z0 + z1) / 2)


def build():
    ramp = P["ramp_length"]
    deck_top = P["lift_height"]
    deck_bot = deck_top - P["deck_thickness"]
    deck_end = ramp + P["deck_length"]
    center = P["track_gap"] / 2 + P["runway_width"] / 2   # runway Y center

    parts = []

    # two runways, mirrored across the centerline
    parts.append(lib3d.move(runway(), y=center))
    parts.append(lib3d.move(runway(), y=-center))

    # base frame plate under the deck footprint, overlapping the ramp feet
    base_len = P["deck_length"] + 12
    base_wid = 2 * center + P["runway_width"] + 8
    base_x = ramp + P["deck_length"] / 2 - 6
    base = lib3d.rounded_box(base_len, base_wid, P["base_thickness"], r=P["soften"])
    parts.append(lib3d.move(base, x=base_x))

    # four corner posts, directly under the runways
    post_h = deck_bot + 2          # overlap up into the deck slab
    post_x = [ramp + 12, deck_end - 12]
    for px in post_x:
        for py in (center, -center):
            post = lib3d.rounded_box(P["post_size"], P["post_size"], post_h,
                                     r=P["soften"])
            parts.append(lib3d.move(post, x=px, y=py))

    # cross beams tying each post pair into a frame, tucked under the deck
    beam_h = 10
    beam_span = 2 * center + P["post_size"]
    for px in post_x:
        beam = lib3d.rounded_box(P["post_size"], beam_span, beam_h, r=P["soften"])
        parts.append(lib3d.move(beam, x=px, z=deck_bot - beam_h + 2))

    # ---- garage frame detail: side rails + diagonal X-braces per side ----
    if P["braces"]:
        z_lo, z_hi = P["base_thickness"] + 3, deck_bot - 3
        rail_len = (post_x[1] - post_x[0]) + P["post_size"]
        rail_x = (post_x[0] + post_x[1]) / 2
        rail_z = (z_lo + z_hi) / 2
        for py in (center, -center):
            # horizontal mid-rail along the side
            rail = lib3d.rounded_box(rail_len, 5, 6, r=min(P["soften"], 2))
            parts.append(lib3d.move(rail, x=rail_x, y=py, z=rail_z - 3))
            # crossing diagonals (the classic 4-post X-brace)
            parts.append(diag_brace(post_x[0], post_x[1], z_lo, z_hi, py, 5, 4))
            parts.append(diag_brace(post_x[0], post_x[1], z_hi, z_lo, py, 5, 4))

    # cross safety bar spanning the gap between the runways at deck level
    bar_span = P["track_gap"] + 6
    bar = lib3d.rounded_box(8, bar_span, P["deck_thickness"], r=min(P["soften"], 2))
    parts.append(lib3d.move(bar, x=deck_end - 4, z=deck_bot))

    # ---- hydraulic power cabinet + motor drum at the front corner ----
    if P["control_box"]:
        cab_w, cab_d, cab_h = 20, 18, 32
        cab_y = base_wid / 2 + cab_d / 2 - 3      # outboard, overlapping base edge
        cab_x = ramp + 15
        cab = lib3d.rounded_box(cab_w, cab_d, cab_h, r=P["soften"])
        parts.append(lib3d.move(cab, x=cab_x, y=cab_y))
        # horizontal motor drum lying on top of the cabinet
        drum = lib3d.rotate(lib3d.cylinder(6, 16), 90, [0, 1, 0])
        parts.append(lib3d.move(drum, x=cab_x, y=cab_y, z=cab_h + 5))
        # hydraulic line running up the nearest front post
        line = lib3d.cylinder(2.2, deck_bot - P["base_thickness"])
        parts.append(lib3d.move(line, x=post_x[0],
                                y=center + P["post_size"] / 2,
                                z=(P["base_thickness"] + deck_bot) / 2))

    solid = lib3d.union(parts)

    # ---- subtractive detail: traction tread + anchor-bolt holes ----
    cutters = []
    if P["tread"] > 0:
        depth, pitch = P["tread"], P["tread_pitch"]
        gx = ramp + 5
        while gx <= deck_end - 6:
            for py in (center, -center):
                groove = lib3d.box(2.0, P["runway_width"] + 3, depth + 1)
                cutters.append(lib3d.move(groove, x=gx, y=py,
                                          z=deck_top + (1 - depth) / 2))
            gx += pitch

    if P["bolt_holes"]:
        hz = P["base_thickness"] + 4
        for hx in (base_x - base_len / 2 + 7, base_x + base_len / 2 - 7):
            for hy in (20, -20):
                hole = lib3d.cylinder(1.7, hz)
                cutters.append(lib3d.move(hole, x=hx, y=hy,
                                          z=P["base_thickness"] / 2))

    if cutters:
        solid = lib3d.difference(solid, cutters)

    return solid


if __name__ == "__main__":
    lib3d.export(build(), "car_lift_164")
