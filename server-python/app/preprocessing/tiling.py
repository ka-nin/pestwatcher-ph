"""Non-learned photo tiling for the BPH ResNet-50 classifier.

The BPH classifier was trained on tight crops of single insects (median ~40px
in a 416px photo, see ml/resnet/prepare_dataset.py), so feeding it a wide
field photo squeezed to 224x224 makes every insect a few pixels. For photos
bigger than one insect close-up, the photo is cut into overlapping square
tiles instead, the classifier scores each tile, and neighbouring hits are
merged into one group so a single insect (which overlaps up to four tiles)
isn't counted four times.

This is only preprocessing and bookkeeping — no second model. The result is a
"grid count" (number of hit groups), an approximate density hint, NOT an exact
insect count: two insects closer than a tile apart merge into one group, and
one tile can hold several insects. The forecast's hoppers/hill still comes
from LGU-verified reports (app/decision/report_anchor.py), never from this.

All the numbers below are starting values, tuned against labeled photos by
ml/resnet/evaluate_grid.py.
"""

from dataclasses import dataclass

from PIL import Image

# Photos whose longer side is at most this go to the classifier whole — same
# framing as the ~416px training photos.
WHOLE_MAX_SIDE_PX = 480

# Bigger photos are shrunk to this longer side before tiling so a 12MP phone
# photo doesn't become thousands of tiles (each is a full ResNet-50 pass).
GRID_WORKING_LONG_SIDE_PX = 832

TILE_SIDE_PX = 64
TILE_STRIDE_PX = 32  # half a tile: any insect fits fully inside at least one tile

# Stricter than the whole-photo 0.5 cutoff — one photo yields hundreds of
# tiles, so a small per-tile false-positive rate would otherwise add up.
# 0.99 with at least 4 tiles per group is the safest pair measured by
# ml/resnet/evaluate_grid.py on 832px mosaics of held-out photos (83% of BPH
# scenes found, 17% false alarms on BPH-free scenes); looser pairs gave
# 60-100% false alarms. Still an interim setting — see ml/weights/bph/
# resnet50_bph_grid_eval.json for the full sweep.
TILE_HIT_THRESHOLD = 0.99

# A real insect overlaps several tiles and so fires several at once; a
# lone false hit on leaf texture usually fires just one. Groups smaller than
# this are dropped as noise.
MIN_GROUP_TILES = 4


@dataclass(frozen=True)
class Tile:
    x: int
    y: int
    side: int


@dataclass(frozen=True)
class HitGroup:
    x0: int
    y0: int
    x1: int
    y1: int
    score: float  # highest tile score in the group
    tile_count: int


def needs_grid(width: int, height: int) -> bool:
    return max(width, height) > WHOLE_MAX_SIDE_PX


def prepare_for_grid(img: Image.Image) -> Image.Image:
    """Downscales (never upscales) so the longer side is at most
    GRID_WORKING_LONG_SIDE_PX."""
    longest = max(img.size)
    if longest <= GRID_WORKING_LONG_SIDE_PX:
        return img
    scale = GRID_WORKING_LONG_SIDE_PX / longest
    return img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))), Image.LANCZOS)


def _positions(length: int, side: int, stride: int) -> list[int]:
    if length <= side:
        return [0]
    positions = list(range(0, length - side + 1, stride))
    if positions[-1] != length - side:
        positions.append(length - side)  # cover the far edge
    return positions


def make_tiles(width: int, height: int, side: int = TILE_SIDE_PX, stride: int = TILE_STRIDE_PX) -> list[Tile]:
    side = min(side, width, height)
    return [Tile(x, y, side) for y in _positions(height, side, stride) for x in _positions(width, side, stride)]


def _overlaps(a: Tile, b: Tile) -> bool:
    return not (a.x + a.side <= b.x or b.x + b.side <= a.x or a.y + a.side <= b.y or b.y + b.side <= a.y)


def group_hits(
    tiles: list[Tile],
    scores: list[float],
    threshold: float = TILE_HIT_THRESHOLD,
    min_tiles: int = MIN_GROUP_TILES,
) -> list[HitGroup]:
    """Merges hit tiles (score >= threshold) that overlap each other into
    groups, dropping groups of fewer than `min_tiles` tiles. Deterministic
    union-find; groups come back top-to-bottom, left-to-right."""
    hits = [(tile, score) for tile, score in zip(tiles, scores) if score >= threshold]
    parent = list(range(len(hits)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(hits)):
        for j in range(i + 1, len(hits)):
            if _overlaps(hits[i][0], hits[j][0]):
                parent[find(j)] = find(i)

    members: dict[int, list[int]] = {}
    for i in range(len(hits)):
        members.setdefault(find(i), []).append(i)

    groups = []
    for indices in members.values():
        group_tiles = [hits[i][0] for i in indices]
        groups.append(
            HitGroup(
                x0=min(t.x for t in group_tiles),
                y0=min(t.y for t in group_tiles),
                x1=max(t.x + t.side for t in group_tiles),
                y1=max(t.y + t.side for t in group_tiles),
                score=max(hits[i][1] for i in indices),
                tile_count=len(indices),
            )
        )
    return sorted((g for g in groups if g.tile_count >= min_tiles), key=lambda g: (g.y0, g.x0))
