import os
import re
import shutil
import pytesseract
from pytesseract import Output

# Auto-detect Tesseract executable on Windows
if not shutil.which("tesseract"):
    candidates = [
        os.path.expanduser(r"~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"),
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]
    for cand in candidates:
        if os.path.exists(cand):
            pytesseract.pytesseract.tesseract_cmd = cand
            tessdata = os.path.join(os.path.dirname(cand), "tessdata")
            if os.path.exists(tessdata):
                os.environ.setdefault("TESSDATA_PREFIX", tessdata)
            break

from .preprocess import ocr_variants

_easy = None


def _easyocr_reader():
    global _easy
    if _easy is None:
        try:
            import easyocr
            _easy = easyocr.Reader(["en"], gpu=False)
        except Exception:
            _easy = False
    return _easy or None


def engines_available():
    names = ["Tesseract"]
    try:
        import easyocr  # noqa: F401
        names.append("EasyOCR (fallback)")
    except Exception:
        pass
    return names


def _tesseract_lines(img, psm):
    data = pytesseract.image_to_data(
        img, config=f"--oem 3 --psm {psm}", output_type=Output.DICT)
    lines = {}
    for i, word in enumerate(data["text"]):
        word = word.strip()
        try:
            conf = float(data["conf"][i])
        except ValueError:
            continue
        if not word or conf < 0:
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        lines.setdefault(key, []).append((word, conf))
    out = []
    for words in lines.values():
        text = " ".join(w for w, _ in words)
        conf = sum(c for _, c in words) / len(words) / 100.0
        out.append((text, conf))
    return out


def _valid(lines):
    good = []
    for text, conf in lines:
        alnum = re.sub(r"[^A-Za-z0-9]", "", text)
        if len(alnum) >= 2 and conf >= 0.35:
            good.append((text.strip(), conf))
    return good


def _score(lines):
    return sum(c * len(re.sub(r"[^A-Za-z0-9]", "", t)) for t, c in lines)


def read_text(crop):
    """Returns (lines, engine_name, variant_name)."""
    best, best_info = [], ("Tesseract", "none")
    for vname, img in ocr_variants(crop).items():
        for psm in (6, 7, 11):
            lines = _valid(_tesseract_lines(img, psm))
            if _score(lines) > _score(best):
                best, best_info = lines, ("Tesseract", f"{vname}/psm{psm}")
    avg = sum(c for _, c in best) / len(best) if best else 0.0
    if avg < 0.6 and _easyocr_reader():
        reader = _easyocr_reader()
        variants = ocr_variants(crop)
        raw = reader.readtext(variants["gray"], detail=1, paragraph=False)
        easy = _valid([(t, float(c)) for (_, t, c) in raw])
        if _score(easy) > _score(best):
            best, best_info = easy, ("EasyOCR", "gray")
    return best, best_info[0], best_info[1]
