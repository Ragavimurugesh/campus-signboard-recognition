# Campus Signboard Recognition and Information Extraction System
### Computer Vision + OCR + GPS Navigation for Campus Wayfinding

Take / upload / live-stream a photo of a campus signboard -> the system **detects the board**, **reads the text (Tesseract OCR)**,
**matches it with the campus database** and shows **location details, voice directions, and interactive GPS maps with Google Maps navigation**.

```
Photo / Webcam -> Preprocess -> Detect board (OpenCV / YOLO) -> Perspective crop -> OCR (Tesseract / EasyOCR)
               -> Clean text + fuzzy match -> SQLite campus database -> Result page + GPS map + Google Maps navigation
```

### ✨ Key Features
- **Live Camera & Webcam Stream**: Real-time camera feed with target crosshairs and snapshot capture.
- **Robust Signboard Detection**: Edge and contour detection with perspective warp correction.
- **Multi-Mode OCR**: Tesseract OCR engine (PSM 6, 7, 11) with image variant scoring.
- **Interactive GPS Maps**: Embedded Leaflet.js / OpenStreetMap campus mapping.
- **Live Distance & Geolocation**: Real-time user GPS tracking using the Haversine formula (`📏 You are ~X meters away`).
- **Google Maps Navigation**: One-click turn-by-turn walking directions link.
- **Voice Speech Directions**: Text-to-Speech audio navigation using the Web Speech API.


## 1. Install (once)

**a) Python 3.9+** and **Tesseract OCR program**

| OS | Command |
|----|---------|
| Windows | Install from https://github.com/UB-Mannheim/tesseract/wiki (tick "add to PATH"), restart terminal |
| Ubuntu / Debian | `sudo apt install tesseract-ocr` |
| macOS | `brew install tesseract` |

> Windows only: if Tesseract is not on PATH, add this line at the top of `pipeline/ocr.py`:
> `pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"`

**b) Python libraries**
```
python -m venv venv
venv\Scripts\activate          (Windows)      source venv/bin/activate   (Linux / macOS)
pip install -r requirements.txt
```

## 2. Run
```
python app.py
```
Open **http://127.0.0.1:5000** (on a phone in the same Wi-Fi: `http://<your-PC-IP>:5000` - the camera button opens the phone camera).
Windows: double-click `run.bat`. Linux/macOS: `bash run.sh`.

## 3. How to demo
1. **Scan Signboard** tab -> click any *sample image* (or upload / capture your own) -> **Scan Signboard**.
2. See the boxed board, the OCR text, confidence bars, location info, directions, **Speak directions** button.
3. Try *Unknown Board* (Swimming Pool) -> **Add this board to the database** -> save -> scan again: now recognized.
4. Try *No Board* sample -> system says no signboard found (no wrong answer).
5. **Locations** tab: add / delete boards.  **History & Stats** tab: scan log, accuracy, average time.

## 4. Test from the command line
```
python test_pipeline.py     # runs all 12 sample images, prints a result table
python stress_test.py       # 40 random variations (angle, light, blur, wall, colour)
python make_samples.py      # regenerates the sample images
```
Measured on the included synthetic samples: **12/12** correct and **40/40** on the stress test
(these are generated images - real photos will be harder, see section 6).

## 5. Project structure
```
app.py                Flask server + REST API
database.py           SQLite schema, seed data (10 campus locations, directions), scan log
pipeline/
  preprocess.py       resize, perspective correction, CLAHE, denoise, binarize (OpenCV)
  detector.py         board detector: edge+contour -> colour-cluster fallback -> optional YOLO
  ocr.py              Tesseract (3 image variants x 3 modes) + optional EasyOCR fallback
  matcher.py          text cleaning, OCR-confusion fix (0/O, 1/I), fuzzy matching
  core.py             end-to-end pipeline + annotated output image
templates/ static/    web user interface
samples/              12 sample signboard photos (generated)
docs/                 screenshots of the working application
models/               put trained YOLO weights here (optional)
```

REST API: `POST /api/recognize` (form field `image` or `sample`), `GET/POST /api/locations`,
`DELETE /api/locations/<id>`, `GET /api/history`, `GET /api/stats`, `GET /api/info`.

## 6. Using it with your own campus
1. **Photos:** take real photos of your campus boards (different time / angle / distance).
2. **Database:** Locations tab -> add each board's text exactly as written on the board + directions
   (directions can be edited in `database.py` seed lists or extended with a form).
3. **Accuracy on real photos:** the default detector is classical computer vision (works well for
   rectangular boards with clear contrast). For tougher real-world images train YOLO:
   - label 200-500 board photos (Roboflow / LabelImg), then
     `yolo detect train data=data.yaml model=yolov8n.pt epochs=80 imgsz=640`
   - copy `runs/detect/train/weights/best.pt` to `models/signboard_best.pt` and `pip install ultralytics`
   - restart: the badge on the page changes to **Detector: YOLO (trained)** automatically.
4. **Better OCR:** `pip install easyocr` - it is used automatically when Tesseract confidence is low.

## 7. Known limitations (be honest in your viva)
- Works best for printed, rectangular boards in English; very small, heavily curved or decorative boards may fail.
- Directions are stored text, not live GPS navigation (listed as future work).
- The sample images are synthetic; report real-photo accuracy after testing your own dataset.
