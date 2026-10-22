"""Generates a photorealistic synthetic BPH hopperburn dataset by editing
real rice-field photos with Gemini 2.5 Flash Image ("Nano Banana").

Why this exists: no real hopperburn photos exist anywhere in this repo (the
BPH data is insect photos, not photos of the plant damage the insect
causes) — the same gap `generate_coverage_dataset.py`'s procedural-damage
mode fills for RSB dead-hearts/white-ears by painting tinted ellipses. That
approach is disclosed there as a rough visual stand-in. This script aims
for a materially better stand-in for BPH: an image-editing model asked to
render actual collapsed/dried rice texture (bent stems, straw-yellow/brown
mottling, ragged patch edge) onto a real healthy-canopy photo, rather than
a painted ellipse. It is still synthetic damage on a real background, not a
real photo of hopperburn — disclose it as such wherever this dataset is
used for training or evaluation.

Coverage % and patch position/size are known exactly because this script
chose them and put them in the prompt; the mask is NOT trusted to be what
Gemini thinks it drew — it is recomputed from the actual pixel difference
between the original and edited image, so the label matches the real
output even when the model over- or under-shoots the requested coverage.

Requires GEMINI_API_KEY (or GOOGLE_API_KEY) in server-python/.env and the
google-genai package. google-genai needs pydantic>=2.12.5, which conflicts
with the server's pinned pydantic==2.12.4 (app/ breaks if you install
google-genai into server-python/.venv) — use a separate venv just for this
script instead of the server's:
    cd server-python/ml/synthetic
    python -m venv .venv
    .venv/Scripts/pip.exe install google-genai pillow python-dotenv

Run from server-python/ml/synthetic/:
    .venv/Scripts/python.exe generate_hopperburn_dataset.py --n-images 35
"""

import argparse
import csv
import json
import os
import random
import time
from io import BytesIO
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image, ImageChops, ImageFilter

STAGE1_DIR = Path(__file__).resolve().parent.parent / "new" / "train" / "stage1"
OUT_DIR = Path(__file__).resolve().parent / "datasets"
RUN_NAME = "bph_hopperburn_gemini-edit"

MODEL = "gemini-2.5-flash-image"

COVERAGE_RANGE = (8, 30)  # percent
POSITIONS = [
    "lower left", "lower right", "upper left", "upper right",
    "middle", "lower middle", "upper middle", "left middle", "right middle",
]

# Pixel-difference threshold (0-255, per-channel max-diff) above which a
# pixel counts as "edited" for the recomputed mask. Chosen empirically to
# ignore JPEG re-encoding noise (Gemini returns re-compressed images even
# for untouched regions) while still catching the damage patch's strong
# yellow/brown recoloring.
DIFF_THRESHOLD = 30
MASK_CLOSE_RADIUS = 3  # GaussianBlur radius used to clean up speckle in the diff mask

PROMPT_TEMPLATE = """Edit this rice field photo to show brown planthopper hopperburn.

Cover about {coverage}% of the image with ONE roughly circular patch, centred
{position}, with an irregular, ragged edge.

Inside the patch the rice plants should look dried out and collapsed, not just
recoloured: bent and flattened, leaning in different directions, and thinner
than the healthy plants around them. Colours: mostly straw-yellow and light
brown, with patches of darker brown, a few grey-black streaks, and a few
surviving green plants poking through. Vary the tone across the patch. Do not
use one uniform orange or yellow.

Keep everything outside the patch identical: the healthy green plants, the
water or soil, the lighting, the camera angle and the sharpness. Blend the
patch edge naturally. No purple or grey colour cast, no blur, no cartoon look."""


def pick_source_photos(n: int, rng: random.Random) -> list[Path]:
    """Stratified sample across growth-stage labels encoded in the stage1
    filenames (…_<stage>_<timestamp>_jpg.rf...), proportional to each
    stage's share of the folder, so the picked set isn't all `flowering`
    just because that stage dominates stage1."""
    all_photos = sorted(STAGE1_DIR.glob("*.jpg"))
    if not all_photos:
        raise SystemExit(f"No photos found in {STAGE1_DIR}")

    by_stage: dict[str, list[Path]] = {}
    for p in all_photos:
        parts = p.stem.split("_")
        stage = parts[4] if len(parts) > 4 else "unknown"
        by_stage.setdefault(stage, []).append(p)

    picked: list[Path] = []
    for stage, photos in by_stage.items():
        share = round(n * len(photos) / len(all_photos))
        share = max(1, share)
        rng.shuffle(photos)
        picked.extend(photos[:share])

    rng.shuffle(picked)
    return picked[:n]


def edit_with_gemini(client, image_path: Path, coverage: int, position: str) -> Image.Image | None:
    from google.genai import types

    with Image.open(image_path) as img:
        original = img.convert("RGB")

    prompt = PROMPT_TEMPLATE.format(coverage=coverage, position=position)
    buf = BytesIO()
    original.save(buf, format="PNG")

    response = client.models.generate_content(
        model=MODEL,
        contents=[
            types.Part.from_bytes(data=buf.getvalue(), mime_type="image/png"),
            prompt,
        ],
    )

    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            return Image.open(BytesIO(part.inline_data.data)).convert("RGB")
    return None


def compute_mask(original: Image.Image, edited: Image.Image) -> tuple[Image.Image, float]:
    """Recomputes the damage mask from the actual pixel difference instead
    of trusting Gemini to report where it edited — the model is asked for
    a photorealistic edit, not a mask, and its own notion of the patch
    boundary is not guaranteed to match what it actually rendered."""
    edited = edited.resize(original.size)
    diff = ImageChops.difference(original, edited)
    diff_gray = diff.convert("L")
    mask = diff_gray.point(lambda p: 255 if p >= DIFF_THRESHOLD else 0)
    mask = mask.filter(ImageFilter.GaussianBlur(MASK_CLOSE_RADIUS)).point(lambda p: 255 if p >= 128 else 0)

    white_pixels = sum(1 for p in mask.getdata() if p == 255)
    coverage_pct = 100.0 * white_pixels / (mask.width * mask.height)
    return mask, coverage_pct


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-images", type=int, default=35)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--retries", type=int, default=2, help="per-image retries on API failure")
    args = parser.parse_args()

    if not 30 <= args.n_images <= 40:
        print(f"Warning: --n-images={args.n_images} is outside the intended 30-40 pilot batch size")

    load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise SystemExit("Set GEMINI_API_KEY (or GOOGLE_API_KEY) in server-python/.env")

    from google import genai
    client = genai.Client(api_key=api_key)

    rng = random.Random(args.seed)
    sources = pick_source_photos(args.n_images, rng)

    run_dir = OUT_DIR / RUN_NAME
    images_dir = run_dir / "images"
    masks_dir = run_dir / "masks"
    images_dir.mkdir(parents=True, exist_ok=True)
    masks_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for i, source_path in enumerate(sources):
        target_coverage = rng.randint(*COVERAGE_RANGE)
        position = rng.choice(POSITIONS)

        edited = None
        for attempt in range(args.retries + 1):
            try:
                edited = edit_with_gemini(client, source_path, target_coverage, position)
                if edited is not None:
                    break
            except Exception as exc:
                print(f"[{i:03d}] {source_path.name}: attempt {attempt} failed: {exc}")
                time.sleep(2 ** attempt)

        if edited is None:
            print(f"[{i:03d}] {source_path.name}: SKIPPED (no image returned)")
            continue

        with Image.open(source_path) as original:
            original = original.convert("RGB")
            mask, measured_coverage = compute_mask(original, edited)

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

    labels_path = run_dir / "labels.csv"
    with labels_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "filename", "mask_filename", "source_photo",
            "target_coverage_pct", "measured_coverage_pct", "position",
        ])
        writer.writeheader()
        writer.writerows(rows)

    (run_dir / "annotations.json").write_text(json.dumps(rows, indent=2))

    print(f"\nWrote {len(rows)}/{len(sources)} images to {images_dir}")
    print(f"Masks: {masks_dir}")
    print(f"Labels: {labels_path}")


if __name__ == "__main__":
    main()
