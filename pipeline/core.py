"""End-to-end pipeline: image -> detect -> crop -> OCR -> match -> result."""
import base64
import time
import cv2
import numpy as np

import database
from .detector import detect_signboards, detector_name
from .matcher import match
from .ocr import read_text, engines_available
from .preprocess import warp_board, resize_max


def get_engine_info():
    return {"detector": detector_name(), "ocr": engines_available()}


def _b64(img, quality=88):
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return "data:image/jpeg;base64," + base64.b64encode(buf).decode()


def recognize_image(img):
    t0 = time.time()
    img, _ = resize_max(img, 1600)
    annotated = img.copy()
    boards = detect_signboards(img)
    cands = database.candidates()
    results = []
    for i, b in enumerate(boards):
        crop = warp_board(img, b["points"])
        lines, engine, variant = read_text(crop)
        m = match(lines, cands)
        item = {
            "confidence": b["confidence"],
            "method": b["method"],
            "text": [t for t, _ in lines],
            "ocr_confidence": round(sum(c for _, c in lines) / len(lines), 2) if lines else 0,
            "engine": engine, "variant": variant,
            "crop": _b64(crop, 85), "match": None,
        }
        color = (60, 180, 75)
        if m:
            loc = database.get_location(m[0])
            item["match"] = {"score": round(m[2], 2), "location": loc}
        else:
            color = (0, 140, 255)
        pts = b["points"].astype(np.int32)
        cv2.polylines(annotated, [pts], True, color, 4)
        label = (item["match"]["location"]["name"] if item["match"] else "Unknown board")
        x, y = int(pts[:, 0].min()), int(pts[:, 1].min())
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)
        y0 = max(y - th - 14, 0)
        cv2.rectangle(annotated, (x, y0), (x + tw + 12, y0 + th + 12), color, -1)
        cv2.putText(annotated, label, (x + 6, y0 + th + 3),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)
        results.append(item)

    # keep only boards that gave readable text; a board with no text is noise
    results_ok = [r for r in results if r["text"]]
    secs = round(time.time() - t0, 2)
    best = next((r for r in results_ok if r["match"]), None)
    if best:
        database.log_scan(best["match"]["location"]["id"], " ".join(best["text"]),
                          best["confidence"], secs)
    elif results_ok:
        database.log_scan(None, " ".join(results_ok[0]["text"]), results_ok[0]["confidence"], secs)
    if not results_ok:
        return {"found": False, "seconds": secs, "annotated": _b64(annotated),
                "message": "No signboard with readable text was found. Please retake the photo."}
    return {"found": True, "seconds": secs, "annotated": _b64(annotated),
            "results": results_ok}
