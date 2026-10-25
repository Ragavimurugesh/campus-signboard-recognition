"""Generates basic sample campus signboard photographs for the prototype.
Run:  python make_samples.py
The images imitate real photos: textured wall, board with border, shadows,
different colours, slight rotation / perspective, blur, low light and noise.
"""
import os
import random
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

OUT = "samples"
FONT_PATHS = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
              "C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/arial.ttf",
              "/Library/Fonts/Arial Bold.ttf"]


def get_font(size):
    for p in FONT_PATHS:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def wall(w, h, kind, rng):
    base = {"brick": (150, 86, 70), "plaster": (205, 198, 185),
            "concrete": (140, 140, 138), "paint": (225, 215, 190)}[kind]
    img = np.full((h, w, 3), base[::-1], np.uint8).astype(np.int16)  # RGB -> BGR
    noise = rng.normal(0, 9, (h, w, 1)).astype(np.int16)
    img += noise
    if kind == "brick":
        for y in range(0, h, 34):
            img[y:y + 3, :, :] = (img[y:y + 3, :, :] * 0.6).astype(np.int16)
            off = 0 if (y // 34) % 2 == 0 else 45
            for x in range(off, w, 90):
                img[y:y + 34, x:x + 2, :] = (img[y:y + 34, x:x + 2, :] * 0.6).astype(np.int16)
    grad = np.linspace(0.85, 1.1, w)[None, :, None]
    img = img * grad
    return np.clip(img, 0, 255).astype(np.uint8)


def board_image(text, bg, fg, w=640, h=260, arrow=None, sub=None):
    img = Image.new("RGB", (w, h), bg)
    d = ImageDraw.Draw(img)
    d.rectangle([6, 6, w - 7, h - 7], outline=fg, width=6)
    size = 78
    font = get_font(size)
    limit = w - (190 if arrow else 90)
    while d.textlength(text, font=font) > limit and size > 20:
        size -= 4
        font = get_font(size)
    tw = d.textlength(text, font=font)
    ty = (h - size) / 2 - (18 if sub else 4)
    tx = (w - tw) / 2 - (30 if arrow else 0)
    d.text((tx, ty), text, font=font, fill=fg)
    if sub:
        f2 = get_font(34)
        sw = d.textlength(sub, font=f2)
        d.text(((w - sw) / 2 - (30 if arrow else 0), h - 82), sub, font=f2, fill=fg)
    if arrow:
        ax, ay = w - 70, h // 2
        pts = {"right": [(ax - 30, ay - 10), (ax + 10, ay - 10), (ax + 10, ay - 28), (ax + 40, ay), (ax + 10, ay + 28), (ax + 10, ay + 10), (ax - 30, ay + 10)],
               "left": [(ax + 30, ay - 10), (ax - 10, ay - 10), (ax - 10, ay - 28), (ax - 40, ay), (ax - 10, ay + 28), (ax - 10, ay + 10), (ax + 30, ay + 10)]}[arrow]
        d.polygon(pts, fill=fg)
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def compose(name, text, bg, fg, wall_kind, seed, angle=0, persp=0.0, blur=0,
            dark=1.0, arrow=None, sub=None, scale=0.62):
    rng = np.random.default_rng(seed)
    W, H = 1000, 700
    scene = wall(W, H, wall_kind, rng)
    board = board_image(text, bg, fg, arrow=arrow, sub=sub)
    bh, bw = board.shape[:2]
    s = scale * W / bw
    board = cv2.resize(board, (int(bw * s), int(bh * s)), interpolation=cv2.INTER_AREA)
    bh, bw = board.shape[:2]
    # perspective + rotation of the board
    src = np.float32([[0, 0], [bw, 0], [bw, bh], [0, bh]])
    p = persp * bh
    dst = np.float32([[0, p], [bw, 0], [bw, bh], [0, bh - p]])
    M = cv2.getPerspectiveTransform(src, dst)
    warped = cv2.warpPerspective(board, M, (bw, bh), borderValue=(0, 0, 0))
    mask = cv2.warpPerspective(np.full((bh, bw), 255, np.uint8), M, (bw, bh))
    R = cv2.getRotationMatrix2D((bw / 2, bh / 2), angle, 1.0)
    pad = 60
    warped = cv2.copyMakeBorder(warped, pad, pad, pad, pad, cv2.BORDER_CONSTANT)
    mask = cv2.copyMakeBorder(mask, pad, pad, pad, pad, cv2.BORDER_CONSTANT)
    R = cv2.getRotationMatrix2D(((bw + 2 * pad) / 2, (bh + 2 * pad) / 2), angle, 1.0)
    warped = cv2.warpAffine(warped, R, (bw + 2 * pad, bh + 2 * pad))
    mask = cv2.warpAffine(mask, R, (bw + 2 * pad, bh + 2 * pad))
    x0 = (W - warped.shape[1]) // 2 + int(rng.integers(-40, 40))
    y0 = (H - warped.shape[0]) // 2 + int(rng.integers(-40, 40))
    # drop shadow
    shadow = cv2.GaussianBlur(mask, (31, 31), 0)
    sh_roi = scene[y0 + 10:y0 + 10 + mask.shape[0], x0 + 10:x0 + 10 + mask.shape[1]]
    sm = shadow[:sh_roi.shape[0], :sh_roi.shape[1], None] / 255.0 * 0.45
    scene[y0 + 10:y0 + 10 + sh_roi.shape[0], x0 + 10:x0 + 10 + sh_roi.shape[1]] = (sh_roi * (1 - sm)).astype(np.uint8)
    roi = scene[y0:y0 + mask.shape[0], x0:x0 + mask.shape[1]]
    m = (mask[:roi.shape[0], :roi.shape[1], None] > 128)
    roi[:] = np.where(m, warped[:roi.shape[0], :roi.shape[1]], roi)
    img = scene.astype(np.float32) * dark
    if blur:
        img = cv2.GaussianBlur(img, (blur, blur), 0)
    img += rng.normal(0, 4, img.shape)
    img = np.clip(img, 0, 255).astype(np.uint8)
    os.makedirs(OUT, exist_ok=True)
    cv2.imwrite(os.path.join(OUT, name), img, [cv2.IMWRITE_JPEG_QUALITY, 92])


SPECS = [
    ("sample_01_main_block.jpg", "MAIN BLOCK", (20, 70, 140), (255, 255, 255), "plaster", 1, dict()),
    ("sample_02_library.jpg", "LIBRARY", (20, 110, 60), (255, 255, 255), "brick", 2, dict(angle=-3)),
    ("sample_03_computer_lab.jpg", "COMPUTER LAB", (245, 245, 240), (20, 30, 90), "concrete", 3, dict(angle=2, sub="Floor 2")),
    ("sample_04_canteen.jpg", "CANTEEN", (150, 30, 40), (255, 255, 255), "paint", 4, dict(persp=0.08)),
    ("sample_05_hostel_arrow.jpg", "HOSTEL", (30, 30, 30), (255, 220, 60), "plaster", 5, dict(arrow="right")),
    ("sample_06_admin_office.jpg", "ADMIN OFFICE", (30, 90, 90), (255, 255, 255), "brick", 6, dict(angle=4, persp=-0.06)),
    ("sample_07_parking_dim.jpg", "PARKING", (20, 70, 140), (255, 255, 255), "concrete", 7, dict(dark=0.55)),
    ("sample_08_auditorium_blur.jpg", "AUDITORIUM", (110, 30, 110), (255, 255, 255), "paint", 8, dict(blur=5, angle=-2)),
    ("sample_09_ai_ds_department.jpg", "AI & DS DEPARTMENT", (245, 245, 240), (150, 30, 40), "plaster", 9, dict(sub="Block C")),
    ("sample_10_sports_ground_left.jpg", "SPORTS GROUND", (20, 110, 60), (255, 255, 255), "concrete", 10, dict(arrow="left", persp=0.05)),
    ("sample_11_unknown_board.jpg", "SWIMMING POOL", (20, 70, 140), (255, 255, 255), "plaster", 11, dict()),
]

if __name__ == "__main__":
    for name, text, bg, fg, wk, seed, kw in SPECS:
        compose(name, text, bg, fg, wk, seed, **kw)
    # one photo without any signboard
    rng = np.random.default_rng(99)
    cv2.imwrite(os.path.join(OUT, "sample_12_no_board.jpg"), wall(1000, 700, "brick", rng))
    print("Created", len(SPECS) + 1, "sample images in", OUT)
