import sqlite3
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).parent
VERIFY_DB = BASE / "verify.db"

schema = """
CREATE TABLE IF NOT EXISTS verifications (
    candidate_id INTEGER PRIMARY KEY,
    status TEXT,
    ocr_value TEXT,
    db_value TEXT,
    ocr_path TEXT,
    face_path TEXT,
    face_attempt_path TEXT,
    face_score REAL,
    last_update TEXT
);
"""

def create_db():
    with sqlite3.connect(VERIFY_DB) as conn:
        conn.executescript(schema)
        conn.commit()
    print(f"verify.db created at {VERIFY_DB}")

if __name__ == "__main__":
    create_db()