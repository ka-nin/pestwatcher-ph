"""Ground area covered by a drone photo, read from the photo's own metadata.

A photo has no scale, so the area can only be recovered when the camera
recorded how high it was: DJI-style drone photos carry the height above the
take-off point (XMP RelativeAltitude) and a 35mm-equivalent focal length, which
fixes the field of view. Footprint = 2h*tan(hfov/2) x 2h*tan(vfov/2), assuming
the camera points straight down. Photos without that metadata, or taken at an
angle, return None: the caller then asks for the size instead of guessing.
"""
import math
import re
from pathlib import Path

from PIL import Image

_FOCAL_35MM_TAG = 0xA405  # FocalLengthIn35mmFilm
_EXIF_IFD = 0x8769
_NADIR_TOLERANCE_DEG = 20.0
_FULL_FRAME = (36.0, 24.0)  # mm, the frame a 35mm-equivalent focal length refers to


def _xmp_number(xmp: str, name: str) -> float | None:
    match = re.search(rf'{name}\s*=\s*"([-+]?\d+(?:\.\d+)?)"', xmp) or re.search(
        rf"<[\w-]+:{name}>\s*([-+]?\d+(?:\.\d+)?)\s*<", xmp
    )
    return float(match.group(1)) if match else None


def estimate_field_size_ha(path: Path) -> float | None:
    try:
        with Image.open(path) as img:
            width, height = img.size
            exif = img.getexif()
            focal35 = exif.get_ifd(_EXIF_IFD).get(_FOCAL_35MM_TAG)
            xmp = img.info.get("xmp") or b""
            if isinstance(xmp, bytes):
                xmp = xmp.decode("utf-8", errors="ignore")
            if not xmp:  # JPEG XMP lives in an APP1 segment
                raw = Path(path).read_bytes()
                start = raw.find(b"<x:xmpmeta")
                end = raw.find(b"</x:xmpmeta>")
                xmp = raw[start : end + 12].decode("utf-8", errors="ignore") if start != -1 and end != -1 else ""
    except Exception:
        return None

    altitude = _xmp_number(xmp, "RelativeAltitude")
    pitch = _xmp_number(xmp, "GimbalPitchDegree")
    if not focal35 or not altitude or altitude <= 0:
        return None
    if pitch is not None and abs(pitch + 90.0) > _NADIR_TOLERANCE_DEG:
        return None  # oblique shot: the ground is not a rectangle at this scale

    long_mm, short_mm = _FULL_FRAME
    frame_w, frame_h = (long_mm, short_mm) if width >= height else (short_mm, long_mm)
    ground_w = 2 * altitude * math.tan(math.atan(frame_w / 2 / float(focal35)))
    ground_h = 2 * altitude * math.tan(math.atan(frame_h / 2 / float(focal35)))
    hectares = ground_w * ground_h / 10_000
    return round(hectares, 2) if hectares > 0 else None


# ----------------------------------------------------------------------------
# Ground photos (no drone metadata)
#
# A photo taken from the ground has no scale either, so the ground it shows is
# worked out from the camera geometry: the lens's field of view (from the
# 35mm-equivalent focal length in EXIF; 26 mm, a typical phone main camera,
# when missing) and two ASSUMPTIONS, the camera height and how far it is
# tilted down. Each image row looks at the ground at its own angle, so rows
# near the bottom cover little ground and rows near the top cover a lot; the
# area of each grid cell is integrated over its rows. The result is the area of
# ground VISIBLE in the photo, not the whole field, and only as good as the
# two assumptions (the caller reports the range for plausible tilts).
# ----------------------------------------------------------------------------
DEFAULT_CAMERA_HEIGHT_M = 1.5  # a person holding a phone at chest to eye level
DEFAULT_TILT_DEG = 35.0  # camera axis, below the horizontal
FAR_LIMIT_M = 20.0  # rows looking beyond this are near the horizon; their ground is counted only to here
_DEFAULT_FOCAL35 = 26.0


def _fov(path: Path) -> tuple[float, float]:
    """(horizontal, vertical) field of view in radians for the photo as shown."""
    focal35 = _DEFAULT_FOCAL35
    try:
        with Image.open(path) as img:
            width, height = img.size
            value = img.getexif().get_ifd(_EXIF_IFD).get(_FOCAL_35MM_TAG)
            if value:
                focal35 = float(value)
    except Exception:
        width, height = 4, 3
    long_mm, short_mm = _FULL_FRAME
    frame_w, frame_h = (long_mm, short_mm) if width >= height else (short_mm, long_mm)
    return 2 * math.atan(frame_w / 2 / focal35), 2 * math.atan(frame_h / 2 / focal35)


def ground_area_by_cell(
    path: Path,
    rows: int,
    cols: int,
    camera_height_m: float = DEFAULT_CAMERA_HEIGHT_M,
    tilt_deg: float = DEFAULT_TILT_DEG,
) -> list[list[float]]:
    """Square metres of ground seen by each grid cell (row 0 = top = farthest)."""
    hfov, vfov = _fov(path)
    tilt = math.radians(tilt_deg)
    min_depression = math.atan(camera_height_m / FAR_LIMIT_M)
    steps = 40

    def width_and_dist(t: float) -> tuple[float, float]:
        # t: 0 at the top of the photo, 1 at the bottom
        depression = max(tilt + math.atan((t - 0.5) * 2 * math.tan(vfov / 2)), min_depression)
        dist = camera_height_m / math.tan(depression)
        depth = (camera_height_m / math.sin(depression)) * math.cos(depression - tilt)
        return 2 * depth * math.tan(hfov / 2), dist

    areas = []
    for r in range(rows):
        t0, t1 = r / rows, (r + 1) / rows
        total = 0.0
        prev_w, prev_d = width_and_dist(t0)
        for k in range(1, steps + 1):
            w, d = width_and_dist(t0 + (t1 - t0) * k / steps)
            total += (w + prev_w) / 2 * abs(prev_d - d)
            prev_w, prev_d = w, d
        areas.append([total / cols] * cols)
    return areas
