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
