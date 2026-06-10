"""Name keychain — rounded tag, raised text, keyring loop."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

import lib3d

P = {
    "name": "SMITH",
    "text_size": 16,      # font size, mm (cap height ~70% of this)
    "base_thick": 4,
    "text_raise": 1.6,    # how far letters stand proud of the tag
    "pad": 6,             # border around the text
    "ring_outer": 7,      # keyring loop radii
    "ring_inner": 3.5,
}


def build():
    text_2d = lib3d.text_polygons(P["name"], P["text_size"])
    minx, miny, maxx, maxy = text_2d.bounds
    tw, th = maxx - minx, maxy - miny

    base_w = tw + 2 * P["pad"]
    base_h = th + 2 * P["pad"]
    base = lib3d.extrude(lib3d.rounded_rect(base_w, base_h, 5), P["base_thick"])

    text = lib3d.extrude(text_2d, P["text_raise"])
    text.apply_translation([-(minx + tw / 2), -(miny + th / 2), P["base_thick"]])

    ring = lib3d.difference(
        lib3d.cylinder(P["ring_outer"], P["base_thick"]),
        lib3d.cylinder(P["ring_inner"], P["base_thick"] * 3),
    )
    ring.apply_translation([-(base_w / 2 + P["ring_outer"] - 3), 0,
                            P["base_thick"] / 2])

    return lib3d.union(base, text, ring)


if __name__ == "__main__":
    lib3d.export(build(), "keychain_smith")
