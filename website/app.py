from flask import Flask, render_template, request, redirect, url_for, flash
from pathlib import Path
import sqlite3
import os
from datetime import datetime, timezone


from Untitled_1 import OCREngine, UserDatabase, IDVerifier

BASE = Path(__file__).parent
UPLOAD_DIR = BASE / "uploads"
OCR_DIR = UPLOAD_DIR / "ocr"
VERIFY_DB = BASE / "verify.db"
USERS_DB_URL = f"sqlite:///{BASE / 'users.db'}"  # matches your create_db.py

for d in (UPLOAD_DIR, OCR_DIR):
    d.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.secret_key = "dev-secret"

def verify_connect():
    conn = sqlite3.connect(VERIFY_DB)
    conn.row_factory = sqlite3.Row
    return conn

def get_verification(cid):
    with verify_connect() as conn:
        cur = conn.execute("SELECT * FROM verifications WHERE candidate_id = ?", (cid,))
        row = cur.fetchone()
        return dict(row) if row else None

def upsert_verification(cid, status=None, ocr_value=None, db_value=None, ocr_path=None, face_score=None):
    now = datetime.now(timezone.utc).isoformat()
    with verify_connect() as conn:
        cur = conn.execute("SELECT 1 FROM verifications WHERE candidate_id = ?", (cid,))
        if cur.fetchone():
            conn.execute("""
                UPDATE verifications SET status=?, ocr_value=?, db_value=?, ocr_path=?, face_score=?, last_update=?
                WHERE candidate_id=?
            """, (status, ocr_value, db_value, ocr_path, face_score, now, cid))
        else:
            conn.execute("""
                INSERT INTO verifications (candidate_id, status, ocr_value, db_value, ocr_path, face_score, last_update)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (cid, status, ocr_value, db_value, ocr_path, face_score, now))
        conn.commit()

def get_user_record(uid):
    # Use the UserDatabase from your Untitled-1.py which expects a SQLAlchemy URL
    db = UserDatabase(USERS_DB_URL)
    try:
        rec = db.get_user_id_record(uid)
        return rec  # dict with 'id_type' and 'id_value'
    except Exception:
        return None

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/dashboard", methods=["POST"])
def dashboard():
    cid = request.form.get("candidate_id")
    try:
        cid_int = int(cid)
    except Exception:
        flash("Invalid candidate id")
        return redirect(url_for("index"))
    return redirect(url_for("candidate", cid=cid_int))

@app.route("/candidate/<int:cid>")
def candidate(cid):
    user = get_user_record(cid) or {}
    verification = get_verification(cid) or {}
    # build a display dict compatible with your templates
    display = {
        "candidate_id": cid,
        "name": user.get("name") if isinstance(user, dict) else "",
        "id_type": user.get("id_type"),
        "id_value": user.get("id_value"),
        "status": verification.get("status"),
        "ocr_value": verification.get("ocr_value"),
        "face_path": verification.get("face_path"),
        "face_attempt_path": verification.get("face_attempt_path"),
        "face_score": verification.get("face_score")
    }
    return render_template("candidate.html", candidate=display)

# Route that saves the uploaded hallticket, calls your Untitled-1 verifier, and writes status
@app.route("/api/ocr", methods=["POST"])
def api_ocr():
    cid = int(request.form.get("candidate_id"))
    file = request.files.get("ocr_file")
    if not file:
        flash("No file uploaded for OCR")
        return redirect(url_for("candidate", cid=cid))

    filename = f"{cid}_ocr_{int(datetime.utcnow().timestamp())}.jpg"
    path = OCR_DIR / filename
    file.save(path)

    # Run your verifier: it will read expected id from your users.db
    try:
        user_db = UserDatabase(USERS_DB_URL)
        ocr_engine = OCREngine()
        verifier = IDVerifier(user_db, ocr_engine)
        result = verifier.verify(str(path), cid)  # returns dict with status, ocr_value, db_value, etc.
        status = result.get("status")
        ocr_value = result.get("ocr_value")
        db_value = result.get("db_value")
    except Exception as e:
        status = "ERROR"
        ocr_value = None
        db_value = None
        flash(f"OCR/verifier error: {e}")

    # store into verify.db for UI/status tracking
    upsert_verification(cid, status=status, ocr_value=ocr_value, db_value=db_value, ocr_path=str(path))
    flash(f"OCR run completed — status: {status}")
    return redirect(url_for("candidate", cid=cid))

# simple manual status setter (useful after you run separate CV pipelines)
@app.route("/api/set_status", methods=["POST"])
def api_set_status():
    cid = int(request.form.get("candidate_id"))
    status = request.form.get("status")
    if status not in ("PASS", "FAIL", "PENDING", "OCR_UPLOADED"):
        flash("Invalid status")
        return redirect(url_for("candidate", cid=cid))
    upsert_verification(cid, status=status)
    flash(f"Status set to {status}")
    return redirect(url_for("candidate", cid=cid))

@app.route("/next/<int:cid>")
def next_candidate(cid):
    return redirect(url_for("candidate", cid=cid + 1))


@app.route("/report")
def report():
    # Read all users and their verification status, join users with verifications
    users_db_path = BASE / "users.db"
    users = []
    import sqlite3 as _sqlite
    # load users
    with _sqlite.connect(users_db_path) as conn:
        conn.row_factory = _sqlite.Row
        cur = conn.execute("SELECT user_id, id_type, id_value FROM users ORDER BY user_id")
        for r in cur.fetchall():
            users.append({"user_id": r["user_id"], "id_type": r["id_type"], "id_value": r["id_value"]})

    # enrich with verifications
    verifs = {}
    with verify_connect() as conn:
        cur = conn.execute("SELECT * FROM verifications")
        for r in cur.fetchall():
            verifs[r["candidate_id"]] = dict(r)

    rows = []
    total = 0
    passed = 0
    failed = 0
    for u in users:
        uid = u["user_id"]
        v = verifs.get(uid, {})
        status = v.get("status") or "PENDING"
        if status == "PASS":
            passed += 1
        if status == "FAIL":
            failed += 1
        total += 1
        # format last_update into a human-friendly string
        lu = v.get("last_update")
        if lu:
            try:
                parsed = datetime.fromisoformat(lu)
                # show as YYYY-MM-DD HH:MM:SS UTC if timezone aware, otherwise local
                if parsed.tzinfo is None:
                    formatted_lu = parsed.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    formatted_lu = parsed.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            except Exception:
                formatted_lu = lu
        else:
            formatted_lu = None

        rows.append({
            "user_id": uid,
            "id_type": u.get("id_type"),
            "id_value": u.get("id_value"),
            "status": status,
            "ocr_value": v.get("ocr_value"),
            "last_update": formatted_lu
        })

    pass_pct = (passed / total * 100) if total else 0
    fail_pct = (failed / total * 100) if total else 0

    return render_template("report.html", rows=rows, pass_pct=round(pass_pct, 1), fail_pct=round(fail_pct, 1))

if __name__ == "__main__":
    app.run(debug=True)