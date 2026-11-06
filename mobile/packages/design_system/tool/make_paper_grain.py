"""Regenerates assets/textures/paper_grain.png, the tile behind LpgBackdrop.

A 256 x 256 tile of fine speckle: each pixel is black or white with a random
strength in the alpha channel (most are faint, a few are strong). It tiles
without a seam because every pixel is independent. The widget decides how
much of it shows (see lpg_backdrop.dart), so the file carries no theme.

Usage: python tool/make_paper_grain.py   (needs Pillow)
"""
import random

from PIL import Image

SIZE = 256
random.seed(20261106)  # fixed, so the file regenerates identically

img = Image.new("RGBA", (SIZE, SIZE))
px = img.load()
for y in range(SIZE):
    for x in range(SIZE):
        n = random.gauss(0, 0.32)
        shade = 255 if n > 0 else 0
        alpha = min(255, int(abs(n) * 255))
        px[x, y] = (shade, shade, shade, alpha)

img.save("assets/textures/paper_grain.png", optimize=True)
print("wrote assets/textures/paper_grain.png")
