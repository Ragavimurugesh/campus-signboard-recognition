"""SQLite database for campus locations, directions and scan history."""
import os
import sqlite3
from contextlib import closing

DB_PATH = os.environ.get("CAMPUS_DB", "campus.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS location (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    board_text TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    block TEXT,
    floor TEXT,
    category TEXT,
    description TEXT,
    timings TEXT,
    latitude REAL,
    longitude REAL
);
CREATE TABLE IF NOT EXISTS direction (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_id INTEGER NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    to_id INTEGER NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    instruction TEXT NOT NULL,
    distance_m INTEGER
);
CREATE TABLE IF NOT EXISTS scan_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    location_id INTEGER,
    read_text TEXT,
    confidence REAL,
    seconds REAL,
    created TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_location_text ON location(board_text);
"""

LOCATIONS = [
    ("MAIN BLOCK", "Main Block", "A", "Ground", "Building", "Administrative offices, principal room and reception.", "9:00 AM - 5:00 PM", 13.011200, 80.235100),
    ("LIBRARY", "Central Library", "B", "First", "Facility", "Books, journals, digital library and reading hall.", "9:00 AM - 6:00 PM", 13.011850, 80.236100),
    ("COMPUTER LAB", "Computer Lab", "C", "Second", "Department", "AI and Data Science programming laboratory.", "9:00 AM - 4:30 PM", 13.012100, 80.234600),
    ("CANTEEN", "Canteen", "D", "Ground", "Facility", "Tea, snacks and meals for students and staff.", "8:00 AM - 5:00 PM", 13.010500, 80.235600),
    ("HOSTEL", "Boys / Girls Hostel", "H", "Ground", "Residence", "Student accommodation with mess and common room.", "Gate closes 9:00 PM", 13.009100, 80.236800),
    ("ADMIN OFFICE", "Administrative Office", "A", "Ground", "Office", "Fee payment, certificates and general enquiries.", "9:30 AM - 4:30 PM", 13.011300, 80.235000),
    ("PARKING", "Parking Area", "P", "Ground", "Facility", "Two-wheeler and four-wheeler parking.", "6:00 AM - 8:00 PM", 13.011700, 80.234500),
    ("AUDITORIUM", "Auditorium", "E", "Ground", "Facility", "Seminars, cultural events and guest lectures.", "As per event schedule", 13.009800, 80.234800),
    ("AI & DS DEPARTMENT", "AI & DS Department", "C", "Second", "Department", "Staff rooms, classrooms and project lab of AI and Data Science.", "9:00 AM - 4:30 PM", 13.012250, 80.234800),
    ("SPORTS GROUND", "Sports Ground", "S", "Ground", "Facility", "Cricket, football, athletics track and indoor courts.", "6:00 AM - 7:00 PM", 13.007500, 80.238000),
]

DIRECTIONS = [
    ("MAIN BLOCK", "LIBRARY", "Walk straight for 120 m and turn right at the fountain.", 120),
    ("MAIN BLOCK", "CANTEEN", "Go around the Main Block and walk behind it.", 90),
    ("MAIN BLOCK", "COMPUTER LAB", "Cross the central lawn and take the stairs on the left to the second floor.", 150),
    ("MAIN BLOCK", "PARKING", "Exit through the main gate side path and turn left.", 80),
    ("LIBRARY", "COMPUTER LAB", "Take the staircase on your left and go up to the second floor.", 60),
    ("LIBRARY", "MAIN BLOCK", "Turn left from the entrance and walk straight for 120 m.", 120),
    ("LIBRARY", "CANTEEN", "Walk past the reading garden; the canteen is on the right.", 100),
    ("COMPUTER LAB", "AI & DS DEPARTMENT", "Walk along the corridor to the end; the department is the last door.", 30),
    ("COMPUTER LAB", "LIBRARY", "Go down the staircase and turn right.", 60),
    ("CANTEEN", "HOSTEL", "Take the road on the right and walk for 200 m.", 200),
    ("CANTEEN", "AUDITORIUM", "Walk straight past the parking area to the large building.", 150),
    ("HOSTEL", "CANTEEN", "Walk back along the main road for 200 m.", 200),
    ("HOSTEL", "SPORTS GROUND", "Turn left at the hostel gate and follow the track.", 250),
    ("ADMIN OFFICE", "MAIN BLOCK", "The Main Block entrance is straight ahead.", 20),
    ("PARKING", "MAIN BLOCK", "Walk up the ramp to the Main Block entrance.", 80),
    ("AUDITORIUM", "CANTEEN", "Walk back through the garden and turn left.", 150),
    ("SPORTS GROUND", "HOSTEL", "Follow the track back and turn right at the gate.", 250),
    ("AI & DS DEPARTMENT", "COMPUTER LAB", "Walk back along the corridor to the first lab door.", 30),
]


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with closing(connect()) as conn:
        conn.executescript(SCHEMA)
        # Automatic migration: ensure latitude and longitude columns exist
        cols = [r[1] for r in conn.execute("PRAGMA table_info(location)").fetchall()]
        if "latitude" not in cols:
            conn.execute("ALTER TABLE location ADD COLUMN latitude REAL")
        if "longitude" not in cols:
            conn.execute("ALTER TABLE location ADD COLUMN longitude REAL")

        if conn.execute("SELECT COUNT(*) FROM location").fetchone()[0] == 0:
            conn.executemany(
                "INSERT INTO location(board_text,name,block,floor,category,description,timings,latitude,longitude) VALUES (?,?,?,?,?,?,?,?,?)",
                LOCATIONS)
            ids = {r["board_text"]: r["id"] for r in conn.execute("SELECT id, board_text FROM location")}
            conn.executemany(
                "INSERT INTO direction(from_id,to_id,instruction,distance_m) VALUES (?,?,?,?)",
                [(ids[a], ids[b], ins, d) for a, b, ins, d in DIRECTIONS])
        else:
            # Update default GPS coordinates if missing
            for loc in LOCATIONS:
                conn.execute(
                    "UPDATE location SET latitude=?, longitude=? WHERE board_text=? AND (latitude IS NULL OR longitude IS NULL)",
                    (loc[7], loc[8], loc[0]))
        conn.commit()


def candidates():
    with closing(connect()) as conn:
        return [(r["id"], r["board_text"]) for r in conn.execute("SELECT id, board_text FROM location")]


def get_location(loc_id):
    with closing(connect()) as conn:
        loc = conn.execute("SELECT * FROM location WHERE id=?", (loc_id,)).fetchone()
        if not loc:
            return None
        dirs = conn.execute(
            "SELECT d.to_id, l.name AS destination, d.instruction, d.distance_m "
            "FROM direction d JOIN location l ON l.id=d.to_id WHERE d.from_id=? ORDER BY d.distance_m",
            (loc_id,)).fetchall()
        out = dict(loc)
        out["directions"] = [dict(d) for d in dirs]
        return out


def all_locations():
    with closing(connect()) as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM location ORDER BY name")]


def add_location(data):
    with closing(connect()) as conn:
        lat = data.get("latitude")
        lng = data.get("longitude")
        lat_val = float(lat) if lat not in (None, "") else None
        lng_val = float(lng) if lng not in (None, "") else None
        cur = conn.execute(
            "INSERT INTO location(board_text,name,block,floor,category,description,timings,latitude,longitude) VALUES (?,?,?,?,?,?,?,?,?)",
            (data["board_text"].strip().upper(), data["name"].strip(), data.get("block", ""),
             data.get("floor", ""), data.get("category", ""), data.get("description", ""),
             data.get("timings", ""), lat_val, lng_val))
        conn.commit()
        return cur.lastrowid


def delete_location(loc_id):
    with closing(connect()) as conn:
        conn.execute("DELETE FROM location WHERE id=?", (loc_id,))
        conn.commit()


def log_scan(loc_id, text, conf, seconds):
    with closing(connect()) as conn:
        conn.execute("INSERT INTO scan_log(location_id,read_text,confidence,seconds) VALUES (?,?,?,?)",
                     (loc_id, text, conf, seconds))
        conn.commit()


def history(limit=30):
    with closing(connect()) as conn:
        rows = conn.execute(
            "SELECT s.id, s.read_text, s.confidence, s.seconds, s.created, l.name AS location "
            "FROM scan_log s LEFT JOIN location l ON l.id=s.location_id ORDER BY s.id DESC LIMIT ?",
            (limit,)).fetchall()
        return [dict(r) for r in rows]


def stats():
    with closing(connect()) as conn:
        total = conn.execute("SELECT COUNT(*) FROM scan_log").fetchone()[0]
        ok = conn.execute("SELECT COUNT(*) FROM scan_log WHERE location_id IS NOT NULL").fetchone()[0]
        avg = conn.execute("SELECT AVG(seconds) FROM scan_log").fetchone()[0] or 0
        top = conn.execute(
            "SELECT l.name, COUNT(*) c FROM scan_log s JOIN location l ON l.id=s.location_id "
            "GROUP BY l.name ORDER BY c DESC LIMIT 5").fetchall()
        return {"total": total, "recognized": ok, "avg_seconds": round(avg, 2),
                "top": [dict(r) for r in top]}
