"""Generates a synthetic BPH hopperburn dataset by painting damage directly
onto real rice-field photos with PIL/numpy — no paid API required.

This is the free-tier fallback for generate_hopperburn_dataset.py (which
needs a billed Gemini API key — gemini-2.5-flash-image has zero free-tier
quota for image generation, confirmed via 429 RESOURCE_EXHAUSTED on every
call). Same idea as generate_coverage_dataset.py's procedural-damage mode
for RSB dead-hearts/white-ears: paint a stand-in instead of compositing a
real symptom photo, because no real hopperburn photos exist in this repo
either. Disclose this as a visual approximation wherever it's used for
training/evaluation, not a real hopperburn photo.

Follows the same damage spec given for the AI-edited version as closely as
PIL allows:
  - ONE roughly circular patch, ~8-30% of the frame, ragged/irregular edge
    (built from a jittered-radius polygon, not a smooth circle)
  - mottled straw-yellow / light-brown / dark-brown / grey-black coloring
    (randomized per-cell tint field, not one flat color)
  - a few surviving green cells poking through the patch
  - the patch recolors existing pixels (keeping their luminance/texture)
    rather than painting opaque shapes over them, so the original plant
    silhouette stays visible — a mild vertical squash approximates
    "collapsed/flattened" stems, but this can't actually bend plant
    geometry the way a generative edit could
  - everything outside the patch left pixel-identical to the source photo
  - only source photos with dense-enough green canopy are used (see
    MIN_GREEN_FRACTION) — on sparse/bare-mud photos this recolor technique
    has no texture to preserve and produces an unconvincing blurry blob

Outputs the same shape as generate_hopperburn_dataset.py (images/, masks/,
labels.csv, annotations.json) so downstream tooling doesn't care which
generator produced a given run.

Run from server-python/ml/synthetic/:
    .venv/Scripts/python.exe generate_hopperburn_procedural.py --n-images 35
"""

import argparse
import csv
import json
import math
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

STAGE1_DIR = Path(__file__).resolve().parent.parent / "new" / "train" / "stage1"
OUT_DIR = Path(__file__).resolve().parent / "datasets"
RUN_NAME = "bph_hopperburn_procedural"

COVERAGE_RANGE = (8, 30)  # percent, matches generate_hopperburn_dataset.py
POSITIONS = {
    "lower left": (0.25, 0.75), "lower right": (0.75, 0.75),
    "upper left": (0.25, 0.25), "upper right": (0.75, 0.25),
    "middle": (0.5, 0.5), "lower middle": (0.5, 0.75), "upper middle": (0.5, 0.25),
    "left middle": (0.25, 0.5), "right middle": (0.75, 0.5),
}

# Mottled tint palette the damaged pixels are pulled toward (not painted
# over) — straw-yellow and light brown dominate, darker brown and
# grey-black streak in, a few patches are left untouched to read as
# surviving green. Matches "vary the tone, not one uniform orange/yellow."
TINTS = [
    (214, 184, 94),   # straw-yellow — dominant
    (214, 184, 94),
    (214, 184, 94),
    (188, 146, 72),   # light brown
    (188, 146, 72),
    (120, 88, 48),    # darker brown
    (60, 55, 48),      # grey-black streak
]
TINT_WEIGHTS = [3, 3, 3, 3, 3, 2, 1]
SURVIVING_GREEN_FRACTION = 0.08  # share of in-mask cells left mostly undamaged

# The recolor approach pulls existing pixels toward a tint while keeping
# their luminance, so it only looks like dried vegetation where there was
# dense canopy texture to begin with. Tried on a sparse-seedling/mostly-mud
# source photo it produced a blurry painted-looking blob instead (no blade
# texture to preserve) — this filter keeps those photos out of the pick.
MIN_GREEN_FRACTION = 0.35


def _green_fraction(path: Path) -> float:
    with Image.open(path) as img:
        arr = np.asarray(img.convert("RGB")).astype(np.int16)
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    is_green = (g > r + 8) & (g > b + 8)
    return float(is_green.mean())


def pick_source_photos(n: int, rng: random.Random) -> list[Path]:
    """Returns a stratified-sampled candidate pool sized larger than `n` —
    paint_hopperburn() now rejects a meaningful fraction of attempts (no
    placement cleared MIN_PATCH_GREEN_FRACTION even after shrinking), so
    main() needs spare candidates to draw from to still reach n successes."""
    all_photos = sorted(STAGE1_DIR.glob("*.jpg"))
    if not all_photos:
        raise SystemExit(f"No photos found in {STAGE1_DIR}")

    all_photos = [p for p in all_photos if _green_fraction(p) >= MIN_GREEN_FRACTION]
    if not all_photos:
        raise SystemExit(f"No photos in {STAGE1_DIR} met MIN_GREEN_FRACTION={MIN_GREEN_FRACTION}")

    pool_size = min(len(all_photos), n * 3)

    by_stage: dict[str, list[Path]] = {}
    for p in all_photos:
        parts = p.stem.split("_")
        stage = parts[4] if len(parts) > 4 else "unknown"
        by_stage.setdefault(stage, []).append(p)

    picked: list[Path] = []
    for stage, photos in by_stage.items():
        share = max(1, round(pool_size * len(photos) / len(all_photos)))
        rng.shuffle(photos)
        picked.extend(photos[:share])

    rng.shuffle(picked)
    return picked[:pool_size]


def ragged_polygon(cx: float, cy: float, base_radius: float, rng: random.Random, n_points: int = 28) -> list[tuple[float, float]]:
    """Irregular, ragged-edge patch outline instead of a smooth circle —
    radius jittered per angle with low-frequency wobble (a few broad lobes)
    plus high-frequency jitter (small ragged notches), so the edge reads as
    torn/irregular rather than a scalloped circle."""
    lobe_count = rng.randint(3, 5)
    lobe_phase = rng.uniform(0, 2 * math.pi)
    lobe_amp = rng.uniform(0.15, 0.30)
    points = []
    for i in range(n_points):
        theta = 2 * math.pi * i / n_points
        wobble = 1 + lobe_amp * math.sin(lobe_count * theta + lobe_phase)
        jitter = 1 + rng.uniform(-0.12, 0.12)
        r = base_radius * wobble * jitter
        points.append((cx + r * math.cos(theta), cy + r * math.sin(theta)))
    return points


def _tint_field(w: int, h: int, cell: int, rng: random.Random) -> np.ndarray:
    """Builds a low-res grid of randomly chosen tints (one per `cell`x`cell`
    block), each block's exact RGB jittered a little, then upsamples with
    PIL's bilinear resize so neighbouring cells blend into each other
    instead of showing hard block edges — this is what makes the patch read
    as mottled dried vegetation instead of a tiled swatch."""
    gw, gh = max(1, w // cell + 2), max(1, h // cell + 2)
    grid = np.zeros((gh, gw, 3), dtype=np.uint8)
    for gy in range(gh):
        for gx in range(gw):
            if rng.random() < SURVIVING_GREEN_FRACTION:
                grid[gy, gx] = (80, 120, 55)  # surviving green patch, blended in like any other tint
                continue
            tint = rng.choices(TINTS, weights=TINT_WEIGHTS, k=1)[0]
            grid[gy, gx] = tuple(max(0, min(255, c + rng.randint(-18, 18))) for c in tint)
    small = Image.fromarray(grid, mode="RGB")
    upsampled = small.resize((gw * cell, gh * cell), resample=Image.BILINEAR)
    return np.array(upsampled)[:h, :w]


def _green_map(arr: np.ndarray) -> np.ndarray:
    r, g, b = arr[..., 0].astype(np.int16), arr[..., 1].astype(np.int16), arr[..., 2].astype(np.int16)
    return (g > r + 8) & (g > b + 8)


# Minimum green-pixel fraction a candidate patch footprint must clear to be
# accepted outright. Below this the earlier version still placed the patch
# "best available" even when that meant mostly sky/water — review of a
# first batch showed every such case looked unconvincing (floating blob,
# visible outline against a flat background). Candidates below this score
# are rejected and the radius is shrunk instead of settling for a bad spot.
MIN_PATCH_GREEN_FRACTION = 0.80
# Keep the patch away from the image border — edge-cropped patches lose
# the ragged-outline look and often clip into sky/horizon bands.
EDGE_MARGIN_FRACTION = 0.06


def _best_patch_center(
    green: np.ndarray, px_frac: float, py_frac: float, radius: float, rng: random.Random
) -> tuple[tuple[float, float], float]:
    """The requested `position` (e.g. "right middle") is only a rough
    preference — on a given photo that exact spot might be sky, water, a
    tree line, or bare mud, all of which the recolor technique renders as
    an unconvincing blurry blob (confirmed on a tree/sky photo: the patch
    landed mostly on sky because 'right middle' happened to be background
    there). This samples many candidate centers scattered around the
    requested position, scores each by in-footprint green fraction with a
    penalty for sitting near the frame edge, and returns the best one
    found plus its score — callers that don't clear MIN_PATCH_GREEN_FRACTION
    should shrink the radius and retry rather than use a bad placement."""
    h, w = green.shape
    margin_x, margin_y = EDGE_MARGIN_FRACTION * w, EDGE_MARGIN_FRACTION * h
    integral = np.zeros((h + 1, w + 1), dtype=np.int64)
    integral[1:, 1:] = np.cumsum(np.cumsum(green.astype(np.int64), axis=0), axis=1)

    def green_fraction(cx: float, cy: float) -> float:
        x0, y0 = max(0, int(cx - radius)), max(0, int(cy - radius))
        x1, y1 = min(w, int(cx + radius)), min(h, int(cy + radius))
        if x1 <= x0 or y1 <= y0:
            return 0.0
        box_sum = integral[y1, x1] - integral[y0, x1] - integral[y1, x0] + integral[y0, x0]
        return box_sum / ((x1 - x0) * (y1 - y0))

    def edge_penalty(cx: float, cy: float) -> float:
        dist_to_edge = min(cx, w - cx, cy, h - cy)
        if dist_to_edge >= margin_x + radius and dist_to_edge >= margin_y + radius:
            return 0.0
        return 0.15  # soft penalty, not a hard reject — still usable if green score is high

    best_center, best_score = (px_frac * w, py_frac * h), -1.0
    for _ in range(40):
        jx = rng.uniform(-0.22, 0.22)
        jy = rng.uniform(-0.22, 0.22)
        cx = min(max((px_frac + jx) * w, radius * 0.5), w - radius * 0.5)
        cy = min(max((py_frac + jy) * h, radius * 0.5), h - radius * 0.5)
        score = green_fraction(cx, cy) - edge_penalty(cx, cy)
        if score > best_score:
            best_center, best_score = (cx, cy), score
    return best_center, best_score


def paint_hopperburn(original: Image.Image, coverage_pct: float, position: str, rng: random.Random) -> tuple[Image.Image, Image.Image] | None:
    """Recolors the patch region in place (toward dried straw-yellow/brown
    tones) rather than painting opaque shapes over it, so the original
    plant silhouette, texture and lighting stay visible underneath — a
    photo of dried/collapsed rice still shows rice-shaped structure, it's
    just the wrong color, not replaced by abstract blobs. Returns
    (edited_image, mask), or None if no placement on this photo cleared
    MIN_PATCH_GREEN_FRACTION even after shrinking the patch — callers
    should skip the photo rather than use an unconvincing placement."""
    w, h = original.size
    area = w * h
    target_area = (coverage_pct / 100.0) * area
    base_radius = math.sqrt(target_area / math.pi)

    px_frac, py_frac = POSITIONS[position]
    green = _green_map(np.asarray(original))

    # Try the requested size first; if nothing scores well enough, shrink
    # the patch and retry — a smaller patch is far more likely to fit
    # entirely within a dense-canopy region than a large one, and a
    # smaller-but-convincing patch beats a larger unconvincing one.
    cx = cy = None
    radius = base_radius
    for _ in range(4):
        (cx, cy), score = _best_patch_center(green, px_frac, py_frac, radius, rng)
        if score >= MIN_PATCH_GREEN_FRACTION:
            break
        radius *= 0.75
    else:
        return None
    base_radius = radius

    polygon = ragged_polygon(cx, cy, base_radius, rng)

    mask_img = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask_img).polygon(polygon, fill=255)
    mask_img = mask_img.filter(ImageFilter.GaussianBlur(2))
    hard_mask = mask_img  # saved for coverage measurement before further softening
    soft_mask = mask_img.filter(ImageFilter.GaussianBlur(4))  # wider blend for the final composite

    src = np.asarray(original).astype(np.float32)
    # Scale tint-cell size to the patch radius so small patches get fine
    # mottling instead of a few oversized "polka dot" blobs that read as
    # an obvious pattern rather than organic discoloration (seen clearly
    # on small/distant patches in the first batch).
    tint_cell = max(6, min(18, int(base_radius / 6)))
    tint = _tint_field(w, h, cell=tint_cell, rng=rng).astype(np.float32)

    # Keep the source's own luminance (so texture/shading/stem edges stay
    # visible) but pull hue/brightness toward the tint field — a soft-light
    # style blend, not a flat overwrite.
    luminance = (0.299 * src[..., 0] + 0.587 * src[..., 1] + 0.114 * src[..., 2]) / 255.0
    luminance = np.clip(luminance * 1.1 + 0.08, 0.15, 1.05)[..., None]  # dried look reads slightly brighter/flatter
    recolored = tint * luminance

    # Light grain so it's not perfectly smooth.
    noise = rng_normal_noise(h, w, rng, scale=9.0)
    recolored = np.clip(recolored + noise[..., None], 0, 255)

    alpha = (np.asarray(soft_mask).astype(np.float32) / 255.0)[..., None]
    blended = src * (1 - alpha) + recolored * alpha
    blended_img = Image.fromarray(blended.astype(np.uint8), mode="RGB")

    # Mild vertical squash+restretch on just the patch region approximates
    # flattened/collapsed stems without needing per-stem geometry.
    squash_crop = blended_img.resize((w, max(1, int(h * 0.93))), resample=Image.BILINEAR).resize((w, h), resample=Image.BILINEAR)
    final = Image.composite(squash_crop, blended_img, soft_mask.point(lambda p: int(p * 0.5)))

    return final, hard_mask


def rng_normal_noise(h: int, w: int, rng: random.Random, scale: float) -> np.ndarray:
    seed = rng.randint(0, 2**31 - 1)
    return np.random.default_rng(seed).normal(0, scale, size=(h, w)).astype(np.float32)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-images", type=int, default=35)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if not 30 <= args.n_images <= 40:
        print(f"Warning: --n-images={args.n_images} is outside the intended 30-40 pilot batch size")

    rng = random.Random(args.seed)
    candidates = pick_source_photos(args.n_images, rng)

    run_dir = OUT_DIR / RUN_NAME
    images_dir = run_dir / "images"
    masks_dir = run_dir / "masks"
    images_dir.mkdir(parents=True, exist_ok=True)
    masks_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    skipped = 0
    for source_path in candidates:
        if len(rows) >= args.n_images:
            break

        target_coverage = rng.randint(*COVERAGE_RANGE)
        position = rng.choice(list(POSITIONS))

        with Image.open(source_path) as img:
            original = img.convert("RGB")
            result = paint_hopperburn(original, target_coverage, position, rng)

        if result is None:
            skipped += 1
            print(f"[skip] {source_path.name}: no convincing placement found")
            continue

        edited, mask = result
        white_pixels = sum(1 for p in mask.getdata() if p >= 128)
        measured_coverage = 100.0 * white_pixels / (mask.width * mask.height)

        i = len(rows)
        filename = f"{RUN_NAME}_{i:03d}.jpg"
        mask_filename = f"{RUN_NAME}_{i:03d}_mask.png"
        edited.save(images_dir / filename, quality=92)
        mask.save(masks_dir / mask_filename)

        rows.append({
            "filename": filename,
            "mask_filename": mask_filename,
            "source_photo": source_path.name,
            "target_coverage_pct": target_coverage,
            "measured_coverage_pct": round(measured_coverage, 2),
            "position": position,
        })
        print(f"[{i:03d}] {source_path.name} -> {filename} "
              f"(target {target_coverage}%, measured {measured_coverage:.1f}%)")

    if len(rows) < args.n_images:
        print(f"\nWarning: only {len(rows)}/{args.n_images} reached — ran out of candidate photos "
              f"({skipped} skipped as unconvincing). Try a larger --n-images pool or a different --seed.")

    labels_path = run_dir / "labels.csv"
    with labels_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "filename", "mask_filename", "source_photo",
            "target_coverage_pct", "measured_coverage_pct", "position",
        ])
        writer.writeheader()
        writer.writerows(rows)

    (run_dir / "annotations.json").write_text(json.dumps(rows, indent=2))

    print(f"\nWrote {len(rows)}/{args.n_images} images to {images_dir} "
          f"({skipped} candidate photos skipped as unconvincing)")
    print(f"Masks: {masks_dir}")
    print(f"Labels: {labels_path}")


if __name__ == "__main__":
    main()
