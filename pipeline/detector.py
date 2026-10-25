"""Signboard detector.

Default: classical computer vision (edges + rectangular contour analysis).
It needs no training, so the prototype runs out of the box.

Optional: if a trained YOLO file exists (models/signboard_best.pt) and the
'ultralytics' package is installed, YOLO is used instead.
"""
import os
import cv2
import numpy as np

from .preprocess import resize_max

YOLO_PATH = os.environ.get("YOLO_WEIGHTS", "models/signboard_best.pt")
_yolo = None


def _load_yolo():
    global _yolo
    if _yolo is None and os.path.exists(YOLO_PATH):
        try:
            from ultralytics import YOLO
            _yolo = YOLO(YOLO_PATH)
        except Exception:
            _yolo = False
    return _yolo or None


def detector_name():
    return "YOLO (trained)" if _load_yolo() else "OpenCV contour detector"


def _detect_yolo(img):
    model = _load_yolo()
    res = model.predict(img, conf=0.35, verbose=False)[0]
    out = []
    for b in res.boxes:
        x1, y1, x2, y2 = [float(v) for v in b.xyxy[0].tolist()]
        pts = np.array([[x1, y1], [x2, y1], [x2, y2], [x1, y2]], np.float32)
        out.append({"points": pts, "score": float(b.conf[0]), "method": "yolo"})
    return out


def _detect_classical(img):
    small, scale = resize_max(img, 900)
    H, W = small.shape[:2]
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 9, 60, 60)
    found = []
    # two edge settings: strong edges first, softer edges for dim photos
    for lo, hi in ((60, 160), (25, 80)):
        edges = cv2.Canny(gray, lo, hi)
        edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE,
                                 cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7)))
        cnts, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_SIMPLE)
        for c in cnts:
            area = cv2.contourArea(c)
            if area < 0.02 * W * H or area > 0.85 * W * H:
                continue
            rect = cv2.minAreaRect(c)
            (rw, rh) = rect[1]
            if min(rw, rh) < 20:
                continue
            ratio = max(rw, rh) / min(rw, rh)
            if ratio < 1.15 or ratio > 9:
                continue
            fill = area / (rw * rh)                      # rectangularity
            if fill < 0.80:
                continue
            box = cv2.boxPoints(rect)
            # the board must be fairly uniform in colour: low variance of
            # the border ring compared with a strong text contrast inside
            mask = np.zeros((H, W), np.uint8)
            cv2.fillPoly(mask, [box.astype(np.int32)], 255)
            inside = gray[mask > 0]
            if inside.size == 0:
                continue
            contrast = float(inside.std())
            score = fill * (area / (W * H)) ** 0.5 * min(contrast / 40.0, 1.5)
            found.append({"points": (box / scale).astype(np.float32),
                          "score": float(score), "method": "contour"})
    return _nms(found)


def _detect_smooth_regions(img):
    """Fallback for textured walls (brick, stone) where edges are noisy:
    cluster the colours (k-means) and look for a rectangular colour island."""
    small, scale = resize_max(img, 900)
    H, W = small.shape[:2]
    tiny = cv2.resize(small, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
    lab = cv2.cvtColor(cv2.GaussianBlur(tiny, (5, 5), 0), cv2.COLOR_BGR2LAB)
    data = lab.reshape(-1, 3).astype(np.float32)
    found = []
    for K in (4, 6):
        crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
        _, labels, _ = cv2.kmeans(data, K, None, crit, 2, cv2.KMEANS_PP_CENTERS)
        labels = labels.reshape(tiny.shape[:2])
        for k in range(K):
            mask = (labels == k).astype(np.uint8) * 255
            mask = cv2.resize(mask, (W, H), interpolation=cv2.INTER_NEAREST)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE,
                                    cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15)))
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,
                                    cv2.getStructuringElement(cv2.MORPH_RECT, (11, 11)))
            cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for c in cnts:
                area = cv2.contourArea(c)
                if area < 0.03 * W * H or area > 0.6 * W * H:
                    continue
                rect = cv2.minAreaRect(c)
                (rw, rh) = rect[1]
                if min(rw, rh) < 20:
                    continue
                ratio = max(rw, rh) / min(rw, rh)
                fill = area / (rw * rh)
                if ratio < 1.15 or ratio > 9 or fill < 0.88:
                    continue
                box = cv2.boxPoints(rect)
                found.append({"points": (box / scale).astype(np.float32),
                              "score": float(fill * (area / (W * H)) ** 0.5),
                              "method": "contour"})
    return _nms(found)


def _iou(a, b):
    ra = cv2.boundingRect(a.astype(np.int32))
    rb = cv2.boundingRect(b.astype(np.int32))
    x1, y1 = max(ra[0], rb[0]), max(ra[1], rb[1])
    x2 = min(ra[0] + ra[2], rb[0] + rb[2])
    y2 = min(ra[1] + ra[3], rb[1] + rb[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    union = ra[2] * ra[3] + rb[2] * rb[3] - inter
    return inter / union if union else 0


def _nms(items, thr=0.4):
    items = sorted(items, key=lambda d: d["score"], reverse=True)
    keep = []
    for it in items:
        if all(_iou(it["points"], k["points"]) < thr for k in keep):
            keep.append(it)
    return keep


def detect_signboards(img, max_boards=3):
    if _load_yolo():
        boards = _detect_yolo(img)
    else:
        boards = _detect_classical(img)
        if not boards:                 # textured wall: try the fallback
            boards = _detect_smooth_regions(img)
    boards = sorted(boards, key=lambda d: d["score"], reverse=True)[:max_boards]
    # normalise score to a 0..1 "confidence"
    for b in boards:
        b["confidence"] = round(min(0.99, 0.55 + b["score"] * 0.6), 2) \
            if b["method"] == "contour" else round(b["score"], 2)
    return boards
