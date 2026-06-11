"""1:64 diecast service lift — drive-on 4-post lift.

Two runways the car's wheels sit on, raised on four posts over an open bay so
you can see underneath (the whole point of a lift). Each runway is one solid
side-profile (ramp wedge -> flat deck -> back wheel stop) so it's watertight by
construction. Cross beams tie the post pairs into a frame; a base plate keeps it
from tipping. Drives on from the table at one end, wheel stops at the far end.

Reference car: Hot Wheels / Matchbox 1:64 ~ 78 x 32 x 25 mm, wheel track ~26 mm.
Print flat on the bed. The deck underside is a horizontal overhang — light
supports under the two runways come out clean (use the X2D's nozzle-2 support
filament).
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

    return lib3d.union(parts)


if __name__ == "__main__":
    lib3d.export(build(), "car_lift_164")
