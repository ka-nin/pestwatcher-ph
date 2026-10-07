"""One-time correction for ml/resnet/datasets/rsb_larva/_annotations.csv.

69 of its 86 images have their stored pixel data in landscape (e.g.
4000x3000) while the CSV's width/height columns — and the box coordinates
drawn against them — are in portrait (3000x4000): a clean, exact
width<->height swap on every affected row, not scattered corruption. This
matches EXIF orientation being applied at annotation time but stripped by
whatever re-exported these files afterward, leaving the pixels unrotated
while the recorded boxes stayed in the rotated frame.

Verified empirically (not assumed): cropping one affected image's box as-is
lands on empty leaf; rotating that same image 90 deg clockwise
(Image.ROTATE_270) before cropping lands squarely on the annotated larva.

This script rotates each affected file in place to match its CSV row, and
drops the one CSV row whose image file is missing entirely. After running,
every surviving row's width/height exactly matches its file's actual pixel
size, which is what ml/resnet/crops.py assumes.

Run once from server-python/:
    .venv/Scripts/python.exe -m ml.resnet.fix_rsb_larva_orientation
"""

from pathlib import Path

import pandas as pd
from PIL import Image

FOLDER = Path(__file__).resolve().parent / "datasets" / "rsb_larva"


def main() -> None:
    csv_path = FOLDER / "_annotations.csv"
    df = pd.read_csv(csv_path)

    rotated = 0
    dropped_missing = 0
    keep_mask = []

    for idx, row in df.iterrows():
        image_path = FOLDER / row["filename"]
        if not image_path.exists():
            print(f"DROP (missing file): {row['filename']}")
            dropped_missing += 1
            keep_mask.append(False)
            continue

        with Image.open(image_path) as img:
            actual_w, actual_h = img.size

        if (actual_w, actual_h) == (row["width"], row["height"]):
            keep_mask.append(True)
            continue

        if (actual_w, actual_h) != (row["height"], row["width"]):
            raise SystemExit(
                f"Unexpected mismatch (not a clean swap) for {row['filename']}: "
                f"file is {actual_w}x{actual_h}, CSV says {row['width']}x{row['height']}"
            )

        with Image.open(image_path) as img:
            img.convert("RGB").transpose(Image.ROTATE_270).save(image_path, quality=100)
        rotated += 1
        keep_mask.append(True)

    df = df[keep_mask].reset_index(drop=True)
    df.to_csv(csv_path, index=False)

    print(f"Rotated {rotated} images to match their CSV orientation.")
    print(f"Dropped {dropped_missing} row(s) for missing files.")
    print(f"{len(df)} rows remain in {csv_path}.")


if __name__ == "__main__":
    main()
