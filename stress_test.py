"""Stress test: generates random variations (angle, light, blur, wall, colours)
of the known boards and measures end-to-end accuracy. Run: python stress_test.py"""
import os, random, tempfile
import cv2
import database
import make_samples as ms
from pipeline import recognize_image

NAMES = {"MAIN BLOCK": "Main Block", "LIBRARY": "Central Library", "COMPUTER LAB": "Computer Lab",
         "CANTEEN": "Canteen", "HOSTEL": "Boys / Girls Hostel", "ADMIN OFFICE": "Administrative Office",
         "PARKING": "Parking Area", "AUDITORIUM": "Auditorium", "SPORTS GROUND": "Sports Ground"}
COLORS = [((20, 70, 140), (255, 255, 255)), ((20, 110, 60), (255, 255, 255)), ((150, 30, 40), (255, 255, 255)),
          ((245, 245, 240), (20, 30, 90)), ((30, 30, 30), (255, 220, 60)), ((110, 30, 110), (255, 255, 255))]
WALLS = ["brick", "plaster", "concrete", "paint"]

if __name__ == "__main__":
    rnd = random.Random(7)
    database.DB_PATH = os.path.join(tempfile.gettempdir(), "stress.db")
    if os.path.exists(database.DB_PATH):
        os.remove(database.DB_PATH)
    database.init_db()
    ms.OUT = tempfile.mkdtemp()
    ok = total = 0
    fails = []
    for i in range(40):
        text = rnd.choice(list(NAMES))
        bg, fg = rnd.choice(COLORS)
        kw = dict(angle=rnd.uniform(-6, 6), persp=rnd.uniform(-0.08, 0.08), dark=rnd.uniform(0.55, 1.0),
                  blur=rnd.choice([0, 0, 3, 5]), scale=rnd.uniform(0.45, 0.7))
        name = f"s{i}.jpg"
        ms.compose(name, text, bg, fg, rnd.choice(WALLS), 100 + i, **kw)
        r = recognize_image(cv2.imread(os.path.join(ms.OUT, name)))
        got = None
        if r["found"]:
            for it in r["results"]:
                if it["match"]:
                    got = it["match"]["location"]["name"]
                    break
        total += 1
        if got == NAMES[text]:
            ok += 1
        else:
            fails.append((text, got, {k: round(v, 2) if isinstance(v, float) else v for k, v in kw.items()}))
    print(f"Stress test accuracy: {ok}/{total} = {100*ok/total:.0f}%")
    for f in fails:
        print("  FAIL:", f)
    os.remove(database.DB_PATH)
