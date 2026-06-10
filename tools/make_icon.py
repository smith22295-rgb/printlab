"""Generate assets/icon.ico — amber hex-nut mark on a dark rounded tile."""
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).parents[1]
(ROOT / "assets").mkdir(exist_ok=True)


def tile(size):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = size * 0.22
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=r, fill=(18, 22, 28, 255))
    cx = cy = size / 2

    def hexpts(rad, rot=math.pi / 6):
        return [(cx + rad * math.cos(rot + i * math.pi / 3),
                 cy + rad * math.sin(rot + i * math.pi / 3)) for i in range(6)]

    d.polygon(hexpts(size * 0.36), outline=(240, 168, 67, 255),
              width=max(1, size // 16))
    d.polygon(hexpts(size * 0.20), fill=(240, 168, 67, 230))
    return img


if __name__ == "__main__":
    base = tile(256)
    base.save(ROOT / "assets" / "icon.ico",
              sizes=[(16, 16), (32, 32), (48, 48), (256, 256)])
    print("wrote", ROOT / "assets" / "icon.ico")
