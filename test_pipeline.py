"""Run the pipeline on every sample image and print a result table."""
import glob
import os
import cv2
import database
from pipeline import recognize_image

EXPECTED = {
    "sample_01_main_block.jpg": "Main Block", "sample_02_library.jpg": "Central Library",
    "sample_03_computer_lab.jpg": "Computer Lab", "sample_04_canteen.jpg": "Canteen",
    "sample_05_hostel_arrow.jpg": "Boys / Girls Hostel", "sample_06_admin_office.jpg": "Administrative Office",
    "sample_07_parking_dim.jpg": "Parking Area", "sample_08_auditorium_blur.jpg": "Auditorium",
    "sample_09_ai_ds_department.jpg": "AI & DS Department", "sample_10_sports_ground_left.jpg": "Sports Ground",
    "sample_11_unknown_board.jpg": None, "sample_12_no_board.jpg": None,
}

if __name__ == "__main__":
    os.environ.setdefault("CAMPUS_DB", "test_campus.db")
    database.DB_PATH = os.environ["CAMPUS_DB"]
    if os.path.exists(database.DB_PATH):
        os.remove(database.DB_PATH)
    database.init_db()
    ok = 0
    print(f"{'Image':36} {'OCR text':26} {'Matched':24} {'sec':>5}  Result")
    print("-" * 105)
    for f in sorted(glob.glob("samples/*.jpg")):
        name = os.path.basename(f)
        r = recognize_image(cv2.imread(f))
        got, text = None, "-"
        if r["found"]:
            first = r["results"][0]
            text = " | ".join(first["text"])[:25]
            for it in r["results"]:
                if it["match"]:
                    got = it["match"]["location"]["name"]
                    break
        good = got == EXPECTED[name]
        ok += good
        print(f"{name:36} {text:26} {str(got):24} {r['seconds']:>5}  {'PASS' if good else 'FAIL'}")
    print("-" * 105)
    print(f"Correct: {ok}/{len(EXPECTED)}  ({100*ok/len(EXPECTED):.0f}%)")
    os.remove(database.DB_PATH)
