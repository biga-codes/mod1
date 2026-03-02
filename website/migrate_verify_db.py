"""
Run this ONCE to add the new columns to verify.db.
Safe to re-run — uses ALTER TABLE IF NOT EXISTS style (catches errors silently).
"""
import sqlite3
from pathlib import Path

VERIFY_DB = Path(__file__).parent / "verify.db"

NEW_COLUMNS = [
    ("face_path",         "TEXT"),
    ("face_attempt_path", "TEXT"),
    ("db_value",          "TEXT"),
    ("ocr_path",          "TEXT"),
    ("ocr_status",        "TEXT DEFAULT 'PENDING'"),   # tracks OCR sub-result independently
]

with sqlite3.connect(VERIFY_DB) as conn:
    # Create table if it doesn't exist yet at all
    conn.execute("""
        CREATE TABLE IF NOT EXISTS verifications (
            candidate_id     INTEGER PRIMARY KEY,
            status           TEXT,
            ocr_value        TEXT,
            db_value         TEXT,
            ocr_path         TEXT,
            ocr_status       TEXT DEFAULT 'PENDING',
            face_score       REAL,
            face_path        TEXT,
            face_attempt_path TEXT,
            last_update      TEXT
        )
    """)

    # Add any missing columns to an already-existing table
    existing = {row[1] for row in conn.execute("PRAGMA table_info(verifications)")}
    for col_name, col_type in NEW_COLUMNS:
        if col_name not in existing:
            conn.execute(f"ALTER TABLE verifications ADD COLUMN {col_name} {col_type}")
            print(f"  Added column: {col_name}")
        else:
            print(f"  Already exists: {col_name}")

    conn.commit()

print("verify.db migration complete.")












