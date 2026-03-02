#Untitled 2
"""
STRICT STUDENT ID + FACE VERIFICATION PIPELINE
(INSIGHTFACE / ARCFACE BASED)
---------------------------------------------
Rules:
1. Student must bring SAME ID type uploaded earlier
2. ID number must EXACTLY match DB
3. Face on ID must match live captured face
"""

import re
import cv2
import pytesseract
import numpy as np
from sqlalchemy import create_engine, text
from insightface.app import FaceAnalysis


# =========================
# 1. ID FORMAT DEFINITIONS
# =========================
class IndianIDFormats:
    PATTERNS = {
        "aadhaar": re.compile(r"\b[2-9][0-9]{3}\s?[0-9]{4}\s?[0-9]{4}\b"),
        "pan": re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"),
    }

    @staticmethod
    def normalize(value: str) -> str:
        return value.upper().replace(" ", "")


# =========================
# 2. OCR ENGINE
# =========================
class OCREngine:
    def __init__(self, tesseract_path=None):
        if tesseract_path:
            pytesseract.pytesseract.tesseract_cmd = tesseract_path

    def extract_text(self, image_path: str) -> str:
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError("Invalid image path")

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.threshold(
            gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )[1]

        return pytesseract.image_to_string(gray, config="--psm 6")


# =========================
# 3. FACE ENGINE (INSIGHTFACE)
# =========================
class InsightFaceEngine:
    def __init__(self):
        self.app = FaceAnalysis(
            name="buffalo_l",
            providers=["CPUExecutionProvider"]
        )
        self.app.prepare(ctx_id=0, det_size=(640, 640))

    def extract_embedding(self, image_path: str):
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError("Invalid image path")

        faces = self.app.get(img)

        if len(faces) != 1:
            raise ValueError("Image must contain exactly ONE face")

        return faces[0].embedding

    def compare(self, emb1, emb2, threshold=0.4):
        emb1 = emb1 / np.linalg.norm(emb1)
        emb2 = emb2 / np.linalg.norm(emb2)

        cosine_sim = float(np.dot(emb1, emb2))

        return {
            "similarity": cosine_sim,
            "match": cosine_sim >= threshold
        }


# =========================
# 4. DATABASE ACCESS
# =========================
class UserDatabase:
    def __init__(self, db_url: str):
        self.engine = create_engine(db_url)
    
    def get_user_record(self, user_id: int):
        """
        DB MUST STORE:
        - id_type
        - id_value
        """
        q = text("""
        SELECT id_type, id_value
        FROM users
        WHERE user_id = :uid
    """)

        with self.engine.connect() as conn:
            row = conn.execute(q, {"uid": user_id}).fetchone()

        if row is None:
            raise ValueError("User not found")

        record = dict(row._mapping)
        # Construct path to reference face image for verification
        # Face images are stored in uploads/facever/<user_id>.jpg
        record["id_face_image_path"] = f"uploads/facever/{user_id}.jpg"
        return record

# =========================
# 5. ID EXTRACTION
# =========================
class IDExtractor:
    def extract_expected_id(self, ocr_text: str, expected_id_type: str):
        pattern = IndianIDFormats.PATTERNS.get(expected_id_type)
        if pattern is None:
            raise ValueError("Unsupported ID type")

        matches = pattern.findall(ocr_text.upper())
        if not matches:
            return None

        return max(matches, key=len)


# =========================
# 6. VERIFICATION PIPELINE
# =========================
class StudentVerifier:
    def __init__(self, db: UserDatabase):
        self.db = db
        self.ocr = OCREngine()
        self.face = InsightFaceEngine()
        self.extractor = IDExtractor()

    def verify(self, id_image_path: str, live_image_path: str, user_id: int):
        # --------------------
        # Load DB truth
        # --------------------
        record = self.db.get_user_record(user_id)

        expected_id_type = record["id_type"].lower()
        expected_id_value = IndianIDFormats.normalize(record["id_value"])

        # --------------------
        # OCR + ID match
        # --------------------
        ocr_text = self.ocr.extract_text(id_image_path)

        extracted_id = self.extractor.extract_expected_id(
            ocr_text, expected_id_type
        )

        if extracted_id is None:
            return {"status": "FAIL", "reason": "Expected ID not found"}

        extracted_id = IndianIDFormats.normalize(extracted_id)

        if extracted_id != expected_id_value:
            return {"status": "FAIL", "reason": "ID number mismatch"}

        # --------------------
        # Face verification
        # --------------------
        id_face_emb = self.face.extract_embedding(
            record["id_face_image_path"]
        )

        live_face_emb = self.face.extract_embedding(
            live_image_path
        )

        face_result = self.face.compare(
            id_face_emb, live_face_emb
        )

        if not face_result["match"]:
            return {
                "status": "FAIL",
                "reason": "Face mismatch",
                "similarity": face_result["similarity"]
            }

        # --------------------
        # SUCCESS
        # --------------------
        return {
            "status": "PASS",
            "id_type": expected_id_type,
            "id_value": expected_id_value,
            "face_similarity": face_result["similarity"]
        }


# =========================
# 7. EXAMPLE USAGE
# =========================
if __name__ == "__main__":
    """
    Tests verification against:
    - ID image: uploads/ocr/ad<id>.jpg (aadhaar) or pa<id>.jpg (pan)
    - Face image: uploads/facever/<id>.jpg
    """

    db = UserDatabase("sqlite:///users.db")
    verifier = StudentVerifier(db)
    
    # Test with seeded users (all are aadhaar)
    test_users = [103, 200, 201, 202, 203]
    
    for uid in test_users:
        # Get the ID type to construct correct path
        record = db.get_user_record(uid)
        id_type = record["id_type"].lower()
        prefix = "ad" if id_type == "aadhaar" else "pa" if id_type == "pan" else id_type[:2]
        
        id_path = f"uploads/ocr/{prefix}{uid}.jpg"
        face_path = f"uploads/facever/{uid}.jpg"
        
        try:
            result = verifier.verify(
                id_image_path=id_path,
                live_image_path=face_path,
                user_id=uid
            )
            print(f"User {uid}: {result}")
        except Exception as e:
            print(f"User {uid}: ERROR - {e}")
