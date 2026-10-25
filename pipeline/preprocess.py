"""Image preprocessing helpers (OpenCV)."""
import cv2
import numpy as np


def resize_max(img, max_side=1000):
    """Return resized image and the scale factor (new = old * scale)."""
    h, w = img.shape[:2]
    scale = min(1.0, max_side / max(h, w))
    if scale < 1.0:
        img = cv2.resize(img, (int(w * scale), int(h * scale)),
                         interpolation=cv2.INTER_AREA)
    return img, scale


def order_points(pts):
    pts = np.array(pts, dtype="float32")
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).ravel()
    return np.array([pts[np.argmin(s)], pts[np.argmin(d)],
                     pts[np.argmax(s)], pts[np.argmax(d)]], dtype="float32")


def warp_board(img, pts, margin=0.04):
    """Perspective-correct the board so that text lines become horizontal."""
    rect = order_points(pts)
    (tl, tr, br, bl) = rect
    w = int(max(np.linalg.norm(br - bl), np.linalg.norm(tr - tl)))
    h = int(max(np.linalg.norm(tr - br), np.linalg.norm(tl - bl)))
    if w < h:                       # board found rotated by 90 degrees
        rect = np.array([bl, tl, tr, br], dtype="float32")
        w, h = h, w
    dst = np.array([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]],
                   dtype="float32")
    M = cv2.getPerspectiveTransform(rect, dst)
    out = cv2.warpPerspective(img, M, (w, h))
    mx, my = int(w * margin), int(h * margin)       # cut the border frame
    if h > 2 * my + 10 and w > 2 * mx + 10:
        out = out[my:h - my, mx:w - mx]
    return out


def enhance(gray):
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    return clahe.apply(gray)


def ocr_variants(crop):
    """Several cleaned versions of the crop; the best one is chosen later."""
    h, w = crop.shape[:2]
    if h < 160:
        f = 160.0 / h
        crop = cv2.resize(crop, None, fx=f, fy=f, interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    gray = enhance(cv2.fastNlMeansDenoising(gray, None, 8, 7, 21))
    _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    # make text dark on white background (OCR engines prefer this)
    border = np.concatenate([otsu[0], otsu[-1], otsu[:, 0], otsu[:, -1]])
    if border.mean() < 127:
        otsu = cv2.bitwise_not(otsu)
    pad = lambda im: cv2.copyMakeBorder(im, 20, 20, 20, 20,
                                        cv2.BORDER_CONSTANT, value=255)
    return {"binary": pad(otsu), "gray": pad(gray),
            "inverted": pad(cv2.bitwise_not(gray))}
