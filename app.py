"""Campus Signboard Recognition System - working prototype (Flask)."""
import os
import cv2
import numpy as np
from flask import Flask, jsonify, render_template, request, send_from_directory

import database
from pipeline import recognize_image, get_engine_info

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
SAMPLES = "samples"
ALLOWED = {"jpg", "jpeg", "png", "webp", "bmp"}


def _ensure_samples():
    if not os.path.isdir(SAMPLES) or not [f for f in os.listdir(SAMPLES) if f.endswith(".jpg")]:
        import make_samples
        for name, text, bg, fg, wk, seed, kw in make_samples.SPECS:
            make_samples.compose(name, text, bg, fg, wk, seed, **kw)


# Initialize DB and samples on startup (for both gunicorn and direct run)
database.init_db()
_ensure_samples()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/info")
def info():
    return jsonify(get_engine_info())


@app.route("/api/samples")
def samples():
    files = sorted(f for f in os.listdir(SAMPLES) if f.lower().endswith(".jpg"))
    return jsonify([{"file": f, "title": f[10:-4].replace("_", " ").title()} for f in files])


@app.route("/samples/<path:name>")
def sample_file(name):
    return send_from_directory(SAMPLES, name)


@app.route("/api/recognize", methods=["POST"])
def recognize():
    img = None
    sample = request.form.get("sample")
    if sample:
        path = os.path.join(SAMPLES, os.path.basename(sample))
        if os.path.exists(path):
            img = cv2.imread(path)
    else:
        f = request.files.get("image")
        if f is None or "." not in f.filename or f.filename.rsplit(".", 1)[1].lower() not in ALLOWED:
            return jsonify(error="Please upload a JPG, PNG or WEBP image."), 400
        img = cv2.imdecode(np.frombuffer(f.read(), np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return jsonify(error="The image could not be read."), 400
    return jsonify(recognize_image(img))


@app.route("/api/locations", methods=["GET", "POST"])
def locations():
    if request.method == "POST":
        data = request.get_json(force=True)
        if not data.get("board_text") or not data.get("name"):
            return jsonify(error="Board text and name are required."), 400
        try:
            new_id = database.add_location(data)
        except Exception:
            return jsonify(error="A location with this board text already exists."), 409
        return jsonify(id=new_id), 201
    return jsonify(database.all_locations())


@app.route("/api/locations/<int:loc_id>", methods=["GET", "DELETE"])
def one_location(loc_id):
    if request.method == "DELETE":
        database.delete_location(loc_id)
        return jsonify(deleted=loc_id)
    loc = database.get_location(loc_id)
    return (jsonify(loc), 200) if loc else (jsonify(error="Not found"), 404)


@app.route("/api/history")
def history():
    return jsonify(database.history())


@app.route("/api/stats")
def stats():
    return jsonify(database.stats())


if __name__ == "__main__":
    database.init_db()
    _ensure_samples()
    print("\n  Campus Signboard Recognition System")
    print("  Open http://127.0.0.1:5000 in your browser\n")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
