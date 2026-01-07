from pathlib import Path
import sqlite3
from datetime import datetime
import sys
sys.path.append(str(Path(__file__).parent.parent))

BASE = Path(__file__).parent.parent
OCR_DIR = BASE / "uploads" / "ocr"

from Untitled_1 import OCREngine, UserDatabase, IDVerifier

USERS_DB_URL = f"sqlite:///{BASE / 'users.db'}"


def get_user_list(db_path):
    users = []
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT user_id FROM users ORDER BY user_id")
        for r in cur.fetchall():
            users.append(int(r["user_id"]))
    return users


def find_image_for(user_id, position):
    # Prefer mapping by last two digits of the candidate id: e.g. 216 -> ad16
    last = user_id % 100
    for ext in (".jpg", ".png"):
        p_last = OCR_DIR / f"ad{last}{ext}"
        if p_last.exists():
            return p_last

    # Fallback: ad{position}.(jpg|png) (ad1..adN map to list positions)
    for ext in (".jpg", ".png"):
        p_pos = OCR_DIR / f"ad{position}{ext}"
        if p_pos.exists():
            return p_pos

    # Final fallback: explicit ad{user_id}.(jpg|png)
    for ext in (".jpg", ".png"):
        p_id = OCR_DIR / f"ad{user_id}{ext}"
        if p_id.exists():
            return p_id

    return None

def main():
    users_db = BASE / "users.db"
    if not users_db.exists():
        print(f"users.db not found at {users_db}")
        return

    users = get_user_list(users_db)
    if not users:
        print("No users found in users.db")
        return

    db = UserDatabase(USERS_DB_URL)
    ocr = OCREngine()
    verifier = IDVerifier(db, ocr)

    for idx, uid in enumerate(users, start=1):
        img = find_image_for(uid, idx)
        if img is None:
            print(f"Skipping candidate {uid}: no matching ad file (tried ad{uid}.jpg and ad{idx}.jpg)")
            continue

        try:
            res = verifier.verify(str(img), uid)
            status = res.get('status')
            ocr_val = res.get('ocr_value')
            db_val = res.get('db_value')
            print(f"Candidate {uid}: file={img.name} -> status={status}, ocr_value={ocr_val}, db_value={db_val}")
            # upsert into verify.db so candidate page reflects the result
            now = datetime.utcnow().isoformat()
            with sqlite3.connect(BASE / "verify.db") as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO verifications
                    (candidate_id, status, ocr_value, db_value, ocr_path, last_update)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    uid,
                    res.get('status'),
                    res.get('ocr_value'),
                    res.get('db_value'),
                    str(img),
                    now
                ))
                conn.commit()
        except Exception as e:
            print(f"Candidate {uid}: file={img.name} -> ERROR: {e}")



if __name__ == '__main__':
    main()
