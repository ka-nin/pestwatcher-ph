"""Tells brown planthopper field damage (hopperburn) from stem-borer damage by its PATTERN.

The two look different from a distance:
  hopperburn   plants dry out in one or a few large, solid patches that are clearly browner than
               the canopy around them (a green field with a brown patch, or a yellowing field
               with a darker brown one). Often circular, spreading outward.
  stem borer   whiteheads and dead hearts are scattered through the canopy: many small pale
               panicles among green plants, never one big dried block.

The stem-borer field model (resnet50_rsb_field_damage_pct) is trained on scattered
whiteheads, so it also fires on a big brown patch and would call hopperburn RSB. This module
looks at the photo's colours and the shape of the dried area instead, so a photo with one
large browner patch is reported as BPH.

The patch is found RELATIVE to the rest of the canopy (a hue shift towards brown), not against
fixed "green" and "dry" colours, because the surrounding canopy can be green (a field in the
vegetative stage) or already yellow (a field close to ripening).

It is a HAND-WRITTEN colour-and-shape screen, not a trained model, and it was checked on only
three real hopperburn photos (there is no public labelled set). Treat the result as a
suggestion for a technologist.

Field-scale gate: the same colours appear on brown stems and soil in a CLOSE-UP, and without a
gate the screen called many real close-up stem-borer photos "hopperburn". A photo counts as
field scale when its texture is fine (stalks are a few pixels wide, so the fine-scale detail
dominates the mid-scale detail) or when sky fills the top of the frame and none of the bottom.
Close-ups of leaves and panicles have big smooth shapes and fail both tests. Its cost: a
photo taken from far away with very little detail, or an aerial photo with coarse texture, may
not pass and falls back to the stem-borer model. Other weak spots: shadows and mud can read as
dried plants; a field that is partly harvested may look like a brown patch.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

WORK_SIDE = 360  # the longer side the photo is shrunk to before analysis
GRID = 3

# Colour classes in HSV (hue in degrees, saturation and value 0..1).
SKY_HUE = (170.0, 270.0)
VEG_HUE = (8.0, 170.0)  # straw yellow through green: anything that can be a plant
VEG_SAT_MIN = 0.12
VEG_VALUE_MIN = 0.15
SMOOTH_SIGMA = 3.0  # blur applied to the hue map so single stalks do not make speckle

# Field-scale gate.
MIN_TEXTURE_RATIO = 1.0  # fine-scale detail / mid-scale detail
MIN_SKY_SHARE = 0.06  # alternative gate: sky over the whole frame
MIN_TOP_SKY = 0.15  # ...and over the top third
MAX_BOTTOM_SKY = 0.05  # ...but not the bottom third (a sky-filled bottom is a sideways photo)

# Hopperburn rule: one dominant solid patch that is clearly browner than the canopy around it.
PATCH_HUE_MAX = 44.0  # the patch itself is brown / orange, not just a different green or yellow
MIN_HUE_CONTRAST = 12.0  # degrees of hue between the patch and the rest of the canopy
MIN_PATCH_SHARE = 0.03  # patch / canopy at least this
MAX_PATCH_SHARE = 0.85  # above this the whole canopy is brown: nothing to compare with
MIN_LARGEST_PATCH = 0.60  # the biggest patch holds at least this share of all patch area
MIN_PATCH_OF_FRAME = 0.025  # ...and covers at least this share of the photo
CELL_AFFECTED_MIN_PCT = 5.0  # a grid cell counts as affected when this share of it is dried


@dataclass
class HopperburnReading:
    hopperburn: bool
    field_scale: bool  # fine texture or sky over the top: a view of a field, not a close-up
    dry_share_pct: float  # the patch as a share of the plant canopy in view
    largest_patch_share: float  # 0..1, share of patch area that sits in the biggest patch
    green_share_pct: float  # the rest of the canopy
    cell_values: list[list[float]]  # % of each grid cell that is dried plants
    reason: str


def _load(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """(hsv, gray) at the working size. Hue in degrees, saturation and value 0..1, gray 0..255."""
    with Image.open(path) as img:
        img = img.convert("RGB")
        scale = WORK_SIDE / max(img.size)
        if scale < 1:
            img = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))), Image.LANCZOS)
        hsv = np.asarray(img.convert("HSV"), dtype=np.float32)
        gray = np.asarray(img.convert("L"), dtype=np.float32)
    hsv[..., 0] *= 360.0 / 255.0
    hsv[..., 1] /= 255.0
    hsv[..., 2] /= 255.0
    return hsv, gray


def texture_ratio(gray: np.ndarray) -> float:
    """Fine-scale detail over mid-scale detail. About 0.4 for close-ups of leaves and panicles
    (big smooth shapes), about 1.1 to 1.5 for a standing view of a field (stalks a few pixels wide)."""
    g1 = ndimage.gaussian_filter(gray, 1.2)
    g2 = ndimage.gaussian_filter(gray, 5.0)
    fine = float(np.abs(gray - g1).mean())
    mid = float(np.abs(g1 - g2).mean())
    return fine / (mid + 1e-6)


def read_photo(path: Path) -> HopperburnReading:
    hsv, gray = _load(path)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    sky = ((h >= SKY_HUE[0]) & (h <= SKY_HUE[1]) & (s > 0.08)) | ((s < 0.10) & (v > 0.80))
    veg = (h >= VEG_HUE[0]) & (h <= VEG_HUE[1]) & (s >= VEG_SAT_MIN) & (v >= VEG_VALUE_MIN) & ~sky

    rows, cols = veg.shape
    empty_cells = [[0.0] * GRID for _ in range(GRID)]
    sky_gate = (
        float(sky.mean()) >= MIN_SKY_SHARE
        and float(sky[: rows // 3].mean()) >= MIN_TOP_SKY
        and float(sky[2 * rows // 3:].mean()) < MAX_BOTTOM_SKY
    )
    field_scale = texture_ratio(gray) >= MIN_TEXTURE_RATIO or sky_gate

    veg_px = int(veg.sum())
    if veg_px < 0.1 * veg.size:
        return HopperburnReading(False, field_scale, 0.0, 0.0, 0.0, empty_cells, "too little vegetation in the photo")

    # Hue averaged over the neighbourhood, using plant pixels only (sky and soil are left out).
    weight = ndimage.gaussian_filter(veg.astype(np.float32), SMOOTH_SIGMA)
    hue_smooth = ndimage.gaussian_filter(np.where(veg, h, 0.0), SMOOTH_SIGMA) / np.maximum(weight, 1e-3)
    canopy_hue = float(np.median(h[veg]))
    patch = veg & (weight > 0.3) & (hue_smooth <= min(PATCH_HUE_MAX, canopy_hue - MIN_HUE_CONTRAST))
    patch = ndimage.binary_opening(patch, structure=np.ones((3, 3)))
    patch = ndimage.binary_closing(patch, structure=np.ones((9, 9))) & veg

    cell_values = [
        [
            round(100.0 * float(patch[r * rows // GRID:(r + 1) * rows // GRID, c * cols // GRID:(c + 1) * cols // GRID].mean()), 2)
            for c in range(GRID)
        ]
        for r in range(GRID)
    ]
    patch_px = int(patch.sum())
    if patch_px == 0:
        return HopperburnReading(False, field_scale, 0.0, 0.0, 100.0, cell_values, "no patch browner than the rest of the canopy")

    patch_share = patch_px / veg_px
    labels, n = ndimage.label(patch)
    sizes = ndimage.sum(patch, labels, index=range(1, n + 1))
    largest = float(sizes.max()) / patch_px
    largest_frame = float(sizes.max()) / patch.size
    rest = veg & ~patch
    contrast = float(h[rest].mean() - h[patch].mean()) if rest.any() else 0.0

    reasons = []
    if not field_scale:
        reasons.append("not a field-scale photo: looks like a close-up")
    if patch_share < MIN_PATCH_SHARE:
        reasons.append("very little browner canopy")
    if patch_share > MAX_PATCH_SHARE or contrast < MIN_HUE_CONTRAST:
        reasons.append("no clearly greener canopy to compare with (looks like a ripening field)")
    if largest < MIN_LARGEST_PATCH:
        reasons.append("the dried plants are scattered, not one patch")
    if largest_frame < MIN_PATCH_OF_FRAME:
        reasons.append("the dried patch is small in the frame")
    return HopperburnReading(
        hopperburn=not reasons,
        field_scale=field_scale,
        dry_share_pct=round(100.0 * patch_share, 2),
        largest_patch_share=round(largest, 3),
        green_share_pct=round(100.0 * (1 - patch_share), 2),
        cell_values=cell_values,
        reason="; ".join(reasons) or "one large patch, clearly browner than the canopy around it",
    )
