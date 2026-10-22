"""Picks usable healthy field photos from a folder (e.g. the Roboflow rice set).

A background must be canopy-dominant: mostly green plants, little sky, mud or
water, in focus, and not rotated sideways. Whiteheads and hopperburn are only
believable on a rice canopy, so pasting onto a photo of a road or a puddle
would teach the model nonsense.

Heuristics on a 160-px thumbnail (cheap, deterministic):
  green fraction   excess-green index 2G - R - B above a threshold
  sky fraction     bright, low-saturation pixels
  rotated          a border strip (left/right) much skyer than the top strip
  sharpness        variance of a Laplacian
"""

from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
THUMB = 160


def stats(path: Path) -> dict:
    with Image.open(path) as im:
        thumb = im.convert("RGB").resize((THUMB, THUMB), Image.BILINEAR)
    a = np.asarray(thumb, dtype=np.float32)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    exg = 2 * g - r - b
    green = (exg > 25) & (g > 60)
    mx, mn = a.max(axis=2), a.min(axis=2)
    sat = (mx - mn) / np.maximum(mx, 1)
    sky = (mx > 170) & (sat < 0.28)
    gray = np.asarray(thumb.convert("L").filter(ImageFilter.FIND_EDGES), dtype=np.float32)
    s = THUMB // 5
    sky_top, sky_left, sky_right = sky[:s].mean(), sky[:, :s].mean(), sky[:, -s:].mean()
    nc = ~green  # "not canopy": sky, trees, soil, water
    nc_top, nc_left, nc_right = nc[:s].mean(), nc[:, :s].mean(), nc[:, -s:].mean()
    return {
        "green": float(green.mean()),
        "green_lower": float(green[THUMB * 2 // 5:].mean()),
        "sky": float(sky.mean()),
        # Sideways photo: a side strip is mostly non-canopy while the top strip is canopy.
        "rotated": bool(max(sky_left, sky_right) > sky_top + 0.2 or (max(nc_left, nc_right) > 0.45 and nc_top < max(nc_left, nc_right) - 0.2)),
        "sharp": float(gray.var()),
    }


def usable(st: dict) -> bool:
    return st["green"] >= 0.40 and st["green_lower"] >= 0.62 and st["sky"] <= 0.35 and not st["rotated"] and st["sharp"] >= 25


def find_backgrounds(root: Path, exclude_dirs: tuple[str, ...] = ("delete",)) -> list[tuple[Path, dict]]:
    out = []
    for p in sorted(root.rglob("*")):
        if p.suffix.lower() not in EXTENSIONS or any(d in p.parts for d in exclude_dirs):
            continue
        st = stats(p)
        if usable(st):
            out.append((p, st))
    return out
