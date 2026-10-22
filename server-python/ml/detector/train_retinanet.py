"""Trains a RetinaNet (ResNet-50 backbone) that finds each brown planthopper in a
photo, so the scan can draw a box on every insect and report a count.

Data: the Roboflow "brown planthopper" set exported as RetinaNet CSV
(image,x1,y1,x2,y2,label; CC BY 4.0, universe.roboflow.com/insect-detection-8dlt5/
brown-planthopper-ahxwj). Roboflow exports each photo twice (an augmented copy), so
photos are grouped by their source name and split by SOURCE so a photo never sits in
both train and test.

Never overwrites an existing model: weights go to ml/weights/bph/retinanet_bph.pt.

Run from server-python/ (SSL_CERT_FILE set to certifi's bundle so the pretrained
weights can download):
    .venv/bin/python -m ml.detector.train_retinanet --data /path/to/export --epochs 12
"""

import argparse
import csv
import json
import random
import time
import zlib
from collections import defaultdict
from pathlib import Path

import torch
import torchvision
from PIL import Image
from torchvision.models.detection import RetinaNet_ResNet50_FPN_Weights, retinanet_resnet50_fpn
from torchvision.models.detection.retinanet import RetinaNetClassificationHead
from torchvision.transforms.functional import to_tensor

from ml.config import WEIGHTS_DIR

OUT = WEIGHTS_DIR / "bph" / "retinanet_bph.pt"
IMAGE_MIN_SIDE = 640  # the insects are ~17 px in a 300 px photo; the net upsamples
SCORE_THRESHOLD = 0.4


def source_of(name: str) -> str:
    return name.split(".rf.")[0]


def split_for(source: str) -> str:
    bucket = zlib.crc32(source.encode()) % 100
    return "train" if bucket < 75 else "val" if bucket < 88 else "test"


def read_boxes(data: Path) -> dict[str, list[list[float]]]:
    boxes: dict[str, list[list[float]]] = defaultdict(list)
    for row in csv.reader((data / "train" / "_annotations.csv").open()):
        if len(row) >= 6 and row[1] != "":
            x0, y0, x1, y1 = map(float, row[1:5])
            if x1 - x0 >= 2 and y1 - y0 >= 2:
                boxes[row[0]].append([x0, y0, x1, y1])
    return boxes


class Photos(torch.utils.data.Dataset):
    def __init__(self, root: Path, items: list[tuple[str, list[list[float]]]], train: bool):
        self.root, self.items, self.train = root, items, train

    def __len__(self):
        return len(self.items)

    def __getitem__(self, i):
        name, boxes = self.items[i]
        img = Image.open(self.root / name).convert("RGB")
        w, _ = img.size
        box = torch.tensor(boxes, dtype=torch.float32).reshape(-1, 4)
        x = to_tensor(img)
        if self.train and random.random() < 0.5:  # horizontal flip
            x = x.flip(-1)
            box = torch.stack([w - box[:, 2], box[:, 1], w - box[:, 0], box[:, 3]], 1)
        return x, {"boxes": box, "labels": torch.ones(len(box), dtype=torch.int64)}


def build_model(pretrained: bool = True):
    weights = RetinaNet_ResNet50_FPN_Weights.COCO_V1 if pretrained else None
    model = retinanet_resnet50_fpn(weights=weights, weights_backbone=None, min_size=IMAGE_MIN_SIDE, max_size=IMAGE_MIN_SIDE * 2, score_thresh=0.05)
    anchors = model.head.classification_head.num_anchors
    model.head.classification_head = RetinaNetClassificationHead(model.backbone.out_channels, anchors, num_classes=2)
    return model


@torch.no_grad()
def evaluate(model, items, root: Path, score: float = SCORE_THRESHOLD) -> dict:
    """Box-level precision/recall at IoU 0.5 and the per-photo count error."""
    model.eval()
    tp = fp = fn = 0
    abs_err = []
    for name, gt in items:
        x = to_tensor(Image.open(root / name).convert("RGB"))
        out = model([x])[0]
        keep = out["scores"] >= score
        pred = out["boxes"][keep]
        gt_t = torch.tensor(gt, dtype=torch.float32).reshape(-1, 4)
        matched = set()
        for p in pred:
            if len(gt_t):
                ious = torchvision.ops.box_iou(p[None], gt_t)[0]
                j = int(ious.argmax())
                if ious[j] >= 0.5 and j not in matched:
                    matched.add(j)
                    tp += 1
                    continue
            fp += 1
        fn += len(gt_t) - len(matched)
        abs_err.append(abs(len(pred) - len(gt_t)))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {
        "photos": len(items), "gt_boxes": tp + fn, "precision": round(precision, 3), "recall": round(recall, 3),
        "count_mae": round(sum(abs_err) / len(abs_err), 2), "score_threshold": score,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--epochs", type=int, default=12)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    random.seed(args.seed)
    torch.manual_seed(args.seed)

    boxes = read_boxes(args.data)
    by_split: dict[str, list] = {"train": [], "val": [], "test": []}
    seen_eval: set[str] = set()
    for name in sorted(boxes):
        src = source_of(name)
        split = split_for(src)
        if split != "train":  # evaluate on one copy per source photo
            if src in seen_eval:
                continue
            seen_eval.add(src)
        by_split[split].append((name, boxes[name]))
    print({k: len(v) for k, v in by_split.items()}, "photos;", sum(len(b) for _, b in by_split["train"]), "train boxes")

    root = args.data / "train"
    loader = torch.utils.data.DataLoader(
        Photos(root, by_split["train"], True), batch_size=4, shuffle=True, collate_fn=lambda b: tuple(zip(*b))
    )
    model = build_model()
    params = [p for p in model.parameters() if p.requires_grad]
    optimizer = torch.optim.AdamW(params, lr=args.lr, weight_decay=1e-4)
    best, history, started = -1.0, [], time.time()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    for epoch in range(1, args.epochs + 1):
        model.train()
        total = 0.0
        for images, targets in loader:
            losses = model(list(images), list(targets))
            loss = sum(losses.values())
            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(params, 10.0)
            optimizer.step()
            total += float(loss)
        val = evaluate(model, by_split["val"], root)
        f1 = 2 * val["precision"] * val["recall"] / max(val["precision"] + val["recall"], 1e-9)
        history.append({"epoch": epoch, "loss": round(total / len(loader), 4), **val, "f1": round(f1, 3)})
        print(history[-1], f"{time.time() - started:.0f}s", flush=True)
        if f1 > best:
            best = f1
            torch.save(model.state_dict(), OUT)

    model.load_state_dict(torch.load(OUT))
    test = evaluate(model, by_split["test"], root)
    print("TEST", test)
    (OUT.parent / "retinanet_bph_test_metrics.json").write_text(
        json.dumps({"test": test, "best_val_f1": round(best, 3), "history": history, "train_seconds": round(time.time() - started),
                    "note": "Roboflow brown planthopper set (CC BY 4.0); split by source photo; box IoU 0.5."}, indent=1)
    )


if __name__ == "__main__":
    main()
