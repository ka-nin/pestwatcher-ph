"""Generates a labeled synthetic image dataset for two tasks neither pest's
real data can train yet: pest-coverage % (the "hectares affected" estimator)
and, for RSB only, dead-heart/white-ear damage % (the data gap flagged during
the SOP/SA revision — the real RSB dataset is moth/larva photos, not photos
of damaged plant tissue).

Two modes:

  crop-paste — builds a canvas from real, guaranteed-insect-free background
  patches (ml/resnet/datasets/processed/{pest}/*/negative/*_bg*.jpg, already
  extracted by ml/resnet/crops.py's extract_background()), then pastes real
  positive crops (ml/resnet/datasets/processed/{pest}/*/positive/*.jpg) onto
  it at random positions. Every pixel involved — backdrop and pasted insects
  — is real; only the ARRANGEMENT is synthetic. Coverage % and count are
  known exactly because this script placed them.

  procedural-damage — RSB only. No real dead-heart/white-ear photos exist
  anywhere in this repo (confirmed: ml/resnet/sb and rsb_larva are photos of
  the insect, not the plant symptom), so there is nothing real to paste.
  This paints soft-edged tinted patches onto the same real backdrops to
  APPROXIMATE the visual effect (browned/wilted for dead hearts, pale/
  bleached for white ears). This is a rougher stand-in than crop-paste and
  should be disclosed as such — see the module docstring in train usage, not
  presented as equivalent to compositing real symptom photographs.

Run from server-python/:
    .venv/Scripts/python.exe -m ml.synthetic.generate_coverage_dataset --pest BPH --mode crop-paste --n-images 200
    .venv/Scripts/python.exe -m ml.synthetic.generate_coverage_dataset --pest RSB --mode crop-paste --n-images 200
    .venv/Scripts/python.exe -m ml.synthetic.generate_coverage_dataset --pest RSB --mode procedural-damage --n-images 200
"""

import argparse
import csv
import json
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

RESNET_DIR = Path(__file__).resolve().parent.parent / "resnet"
PROCESSED_DIR = RESNET_DIR / "datasets" / "processed"
OUT_DIR = Path(__file__).resolve().parent / "datasets"

TILE_SIZE = 96  # each background patch is resized to this before tiling
GRID = 5  # GRID x GRID tiles -> canvas is GRID*TILE_SIZE square
CANVAS_SIZE = GRID * TILE_SIZE
MAX_PLACEMENT_ATTEMPTS = 40
MAX_OVERLAP_FRACTION = 0.15  # how much a new paste may overlap an existing one

# Real annotated crop widths in this dataset range from ~14px to a full
# 416px (a handful of source photos are extreme macro shots where the insect
# fills nearly the whole frame) — pasting those at their own native size
# would make one "insect" swallow the whole canvas. Target size is instead a
# small fraction of the CANVAS, not the crop's own arbitrary original size,
# so a BPH looks like an insect in a wider field photo regardless of how
# tightly its source photo happened to be framed.
MIN_PASTE_FRACTION = 0.04
MAX_PASTE_FRACTION = 0.12

# A first version of this generator only ever produced the "scattered"
# style below — every training image was many small insects on a busy
# background. Spot-checked against 3 real farmer photos (one real BPH per
# frame, large and close-up, the way a phone camera actually gets used),
# the resulting count/coverage models predicted ~0 on all of them: they had
# never seen a frame dominated by one big insect, only ever small scattered
# ones, and had no signal for the opposite case. CLOSEUP_* mixes in that
# missing case — few insects, pasted large — alongside the original
# scattered case, so training data spans both ways a photo of a pest
# actually gets taken.
CLOSEUP_FRACTION = 0.35  # share of generated images using the close-up style
CLOSEUP_MIN_COUNT = 1
CLOSEUP_MAX_COUNT = 3
CLOSEUP_MIN_PASTE_FRACTION = 0.25
CLOSEUP_MAX_PASTE_FRACTION = 0.70

# A visible fraction of the extracted bg patches turned out to be plain
# white studio backdrops or (in at least one observed case) a dataset
# title-card fragment that got cropped like any other "no insect" region —
# extract_background() only checks that a patch avoids annotated boxes, not
# that the source photo is an actual field scene. Grayscale patches (near-
# zero HSV saturation covers both plain white/grey backdrops and black/white
# text, since hue+saturation ignore brightness) are excluded here so the
# tiled canvas stays plausibly field-like.
MIN_BACKGROUND_SATURATION = 25


def _list_images(pattern: str) -> list[Path]:
    paths = sorted(PROCESSED_DIR.glob(pattern))
    if not paths:
        raise SystemExit(f"No files matched {PROCESSED_DIR / pattern} — run ml.resnet.prepare_dataset first")
    return paths


def _mean_saturation(path: Path) -> float:
    with Image.open(path) as img:
        pixels = list(img.convert("HSV").getdata())
    return sum(p[1] for p in pixels) / len(pixels)


def backgrounds_for(pest: str) -> list[Path]:
    candidates = _list_images(f"{pest.lower()}/*/negative/*_bg*.jpg")
    plausible = [p for p in candidates if _mean_saturation(p) >= MIN_BACKGROUND_SATURATION]
    if not plausible:
        raise SystemExit(f"All background patches for {pest} were filtered out as non-field-like")
    return plausible


def positive_crops_for(pest: str) -> list[Path]:
    return _list_images(f"{pest.lower()}/*/positive/*.jpg")


def build_canvas(bg_pool: list[Path], rng: random.Random) -> Image.Image:
    """Tiles GRID x GRID randomly-sampled real background patches into one
    bigger, insect-free canvas. A single bg patch is only ~50-90px (sized to
    match insect-crop dimensions, not meant to stand alone as a scene) — the
    patches come from different source photos, so seams are visible; this
    trades perfect visual continuity for a guaranteed-clean, real-pixel base
    to paste onto, which is what the coverage label's correctness depends on.
    """
    canvas = Image.new("RGB", (CANVAS_SIZE, CANVAS_SIZE))
    for row in range(GRID):
        for col in range(GRID):
            tile_path = rng.choice(bg_pool)
            with Image.open(tile_path) as tile:
                tile = tile.convert("RGB").resize((TILE_SIZE, TILE_SIZE))
                canvas.paste(tile, (col * TILE_SIZE, row * TILE_SIZE))
    return canvas


def _overlaps_too_much(box, placed_boxes, max_fraction: float) -> bool:
    x0, y0, x1, y1 = box
    area = max(1, (x1 - x0) * (y1 - y0))
    for px0, py0, px1, py1 in placed_boxes:
        ix0, iy0 = max(x0, px0), max(y0, py0)
        ix1, iy1 = min(x1, px1), min(y1, py1)
        if ix0 < ix1 and iy0 < iy1:
            if ((ix1 - ix0) * (iy1 - iy0)) / area > max_fraction:
                return True
    return False


def composite_crop_paste(
    bg_pool: list[Path], crop_pool: list[Path], count: int, rng: random.Random, closeup: bool = False
) -> tuple[Image.Image, list[tuple[int, int, int, int]]]:
    """Pastes `count` real positive crops onto a real, insect-free tiled
    canvas at random non-overlapping-ish positions. Returns the composited
    image and the exact placement boxes (so callers get both a coverage %
    and, for free, per-insect boxes usable as object-detection labels).

    `closeup` switches the paste-size range to CLOSEUP_* (few, large) instead
    of MIN/MAX_PASTE_FRACTION (many, small) — see CLOSEUP_FRACTION's
    docstring for why both styles need to exist in training data."""
    canvas = build_canvas(bg_pool, rng)
    placed_boxes: list[tuple[int, int, int, int]] = []
    min_frac, max_frac = (CLOSEUP_MIN_PASTE_FRACTION, CLOSEUP_MAX_PASTE_FRACTION) if closeup else (
        MIN_PASTE_FRACTION, MAX_PASTE_FRACTION
    )

    for _ in range(count):
        crop_path = rng.choice(crop_pool)
        with Image.open(crop_path) as crop:
            crop = crop.convert("RGB")
            target_w = rng.uniform(min_frac, max_frac) * CANVAS_SIZE
            aspect = crop.height / crop.width
            w = max(8, int(target_w))
            h = max(8, int(target_w * aspect))
            # Some real crops are much taller than wide (or vice versa) —
            # without this, a tall crop's height could exceed the canvas
            # entirely, leaving most of it pasted off-frame while the
            # recorded box still counted its full (invisible) area toward
            # coverage_pct. Clamp both dimensions to the canvas, preserving
            # aspect ratio as closely as the clamp allows.
            if h > CANVAS_SIZE:
                w, h = max(8, int(w * CANVAS_SIZE / h)), CANVAS_SIZE
            if w > CANVAS_SIZE:
                w, h = CANVAS_SIZE, max(8, int(h * CANVAS_SIZE / w))
            crop = crop.resize((w, h))

            for _attempt in range(MAX_PLACEMENT_ATTEMPTS):
                x = rng.randint(0, max(0, CANVAS_SIZE - w))
                y = rng.randint(0, max(0, CANVAS_SIZE - h))
                box = (x, y, x + w, y + h)
                if not _overlaps_too_much(box, placed_boxes, MAX_OVERLAP_FRACTION):
                    canvas.paste(crop, (x, y))
                    placed_boxes.append(box)
                    break
            # If every attempt overlapped too much, this one is skipped —
            # count below reflects what was ACTUALLY placed, not requested.

    return canvas, placed_boxes


def composite_procedural_damage(
    bg_pool: list[Path], style: str, target_coverage_pct: float, rng: random.Random, closeup: bool = False
) -> tuple[Image.Image, list[tuple[int, int, int, int]]]:
    """RSB-only approximation for dead-heart ('wilt') / white-ear ('bleach')
    symptoms: no real photos of either exist in this repo to paste instead.
    Paints soft-edged elliptical patches directly onto the canvas, tinted
    toward brown (wilt) or pale/white (bleach), until the painted area
    reaches roughly `target_coverage_pct` of the frame. This is a visual
    stand-in, not a simulation grounded in real symptom photos — flagged
    here and in the output folder name so it's never mistaken for the same
    quality of evidence as crop-paste mode.

    `closeup` paints one or two big patches instead of many small ellipses —
    same reasoning as composite_crop_paste's closeup arg: a real close-up
    photo of a single wilted shoot or bleached panicle looks like one large
    discolored region, not a scatter of small spots, and training data needs
    to include that shape too."""
    canvas = build_canvas(bg_pool, rng)
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    placed_boxes: list[tuple[int, int, int, int]] = []

    target_area = (target_coverage_pct / 100.0) * CANVAS_SIZE * CANVAS_SIZE
    painted_area = 0.0
    tint = (120, 90, 50, 165) if style == "wilt" else (235, 235, 225, 175)

    if closeup:
        n_patches = rng.randint(1, 2)
        for i in range(n_patches):
            remaining_area = target_area - painted_area
            if remaining_area <= 0:
                break
            # Roughly circular patch sized to hit this share of the
            # remaining target area on its own.
            radius = max(6, int((remaining_area / 3.14159) ** 0.5))
            w = min(CANVAS_SIZE, radius * 2)
            h = min(CANVAS_SIZE, int(radius * 2 * rng.uniform(0.7, 1.1)))
            x = rng.randint(0, max(0, CANVAS_SIZE - w))
            y = rng.randint(0, max(0, CANVAS_SIZE - h))
            draw.ellipse([x, y, x + w, y + h], fill=tint)
            placed_boxes.append((x, y, x + w, y + h))
            painted_area += 3.14159 * (w / 2) * (h / 2)
    else:
        while painted_area < target_area:
            w = rng.randint(14, 34)
            h = rng.randint(10, 26)
            x = rng.randint(0, max(0, CANVAS_SIZE - w))
            y = rng.randint(0, max(0, CANVAS_SIZE - h))
            draw.ellipse([x, y, x + w, y + h], fill=tint)
            placed_boxes.append((x, y, x + w, y + h))
            painted_area += 3.14159 * (w / 2) * (h / 2)

    overlay = overlay.filter(ImageFilter.GaussianBlur(2))
    composited = Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")
    return composited, placed_boxes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pest", choices=["BPH", "RSB"], required=True)
    parser.add_argument("--mode", choices=["crop-paste", "procedural-damage"], required=True)
    parser.add_argument("--n-images", type=int, default=200)
    parser.add_argument("--min-count", type=int, default=0, help="crop-paste only")
    parser.add_argument("--max-count", type=int, default=25, help="crop-paste only")
    parser.add_argument("--min-coverage-pct", type=float, default=1.0, help="procedural-damage only")
    parser.add_argument("--max-coverage-pct", type=float, default=35.0, help="procedural-damage only")
    parser.add_argument(
        "--damage-style", choices=["wilt", "bleach"], default="wilt",
        help="procedural-damage only — 'wilt' approximates dead hearts, 'bleach' approximates white ears",
    )
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if args.mode == "procedural-damage" and args.pest != "RSB":
        raise SystemExit("procedural-damage mode is RSB-only — BPH has no analogous plant-symptom target")

    rng = random.Random(args.seed)
    bg_pool = backgrounds_for(args.pest)

    run_name = f"{args.pest.lower()}_{args.mode}" + (f"_{args.damage_style}" if args.mode == "procedural-damage" else "")
    run_dir = OUT_DIR / run_name
    images_dir = run_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    annotations = []

    n_closeup = 0
    if args.mode == "crop-paste":
        crop_pool = positive_crops_for(args.pest)
        for i in range(args.n_images):
            closeup = rng.random() < CLOSEUP_FRACTION
            n_closeup += closeup
            target_count = (
                rng.randint(CLOSEUP_MIN_COUNT, CLOSEUP_MAX_COUNT) if closeup
                else rng.randint(args.min_count, args.max_count)
            )
            image, boxes = composite_crop_paste(bg_pool, crop_pool, target_count, rng, closeup=closeup)
            filename = f"{run_name}_{i:05d}.jpg"
            image.save(images_dir / filename, quality=90)
            coverage_pct = 100.0 * sum((x1 - x0) * (y1 - y0) for x0, y0, x1, y1 in boxes) / (CANVAS_SIZE**2)
            rows.append(
                {"filename": filename, "pest": args.pest, "mode": args.mode,
                 "count": len(boxes), "coverage_pct": round(coverage_pct, 3)}
            )
            annotations.append({"filename": filename, "boxes": boxes})
    else:
        for i in range(args.n_images):
            closeup = rng.random() < CLOSEUP_FRACTION
            n_closeup += closeup
            target_coverage = rng.uniform(args.min_coverage_pct, args.max_coverage_pct)
            image, boxes = composite_procedural_damage(bg_pool, args.damage_style, target_coverage, rng, closeup=closeup)
            filename = f"{run_name}_{i:05d}.jpg"
            image.save(images_dir / filename, quality=90)
            rows.append(
                {"filename": filename, "pest": args.pest, "mode": args.mode,
                 "count": len(boxes), "coverage_pct": round(target_coverage, 3)}
            )
            annotations.append({"filename": filename, "boxes": boxes})

    labels_path = run_dir / "labels.csv"
    with labels_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["filename", "pest", "mode", "count", "coverage_pct"])
        writer.writeheader()
        writer.writerows(rows)

    (run_dir / "annotations.json").write_text(json.dumps(annotations, indent=2))

    print(f"Wrote {len(rows)} images to {images_dir} ({n_closeup} close-up style, {len(rows) - n_closeup} scattered style)")
    print(f"Labels: {labels_path}")
    print(f"Per-insect/patch boxes: {run_dir / 'annotations.json'}")


if __name__ == "__main__":
    main()
