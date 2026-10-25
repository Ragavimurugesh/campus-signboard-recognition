"""Clean OCR text and match it with the campus location database."""
import re
from difflib import SequenceMatcher

CONFUSIONS = {"0": "O", "1": "I", "5": "S", "8": "B", "|": "I"}
MIN_SCORE = 0.72


def clean(text):
    text = text.upper().replace("|", "I")
    text = re.sub(r"[^A-Z0-9& ]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def fix_confusions(text):
    chars = list(text)
    for i, ch in enumerate(chars):
        if ch in CONFUSIONS:
            left = chars[i - 1].isalpha() if i > 0 else False
            right = chars[i + 1].isalpha() if i + 1 < len(chars) else False
            if left and right:
                chars[i] = CONFUSIONS[ch]
    return "".join(chars)


def _sim(a, b):
    return SequenceMatcher(None, a, b).ratio()


def _score(text, target):
    score = _sim(text, target)
    if target in text.split() or f" {target} " in f" {text} ":
        score = max(score, 0.93)
    elif target in text:
        score = max(score, 0.85)
    return score


def match(lines, candidates):
    """lines: [(text, conf)], candidates: [(id, text_content)].
    Returns (id, text, score, matched_ocr_text) or None."""
    options = [t for t, _ in lines]
    if len(options) > 1:
        options.append(" ".join(options))
    best = None
    for raw in options:
        text = fix_confusions(clean(raw))
        if len(text) < 2:
            continue
        for cid, target in candidates:
            s = _score(text, clean(target))
            if best is None or s > best[2]:
                best = (cid, target, s, raw)
    if best and best[2] >= MIN_SCORE:
        return best
    return None
