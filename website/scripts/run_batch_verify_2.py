import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

# save as scripts/run_batch_verify.py
from Untitled_2 import UserDatabase, StudentVerifier
db = UserDatabase('sqlite:///users.db')
v = StudentVerifier(db)
test_ids = [103,200,201,202,203]   # edit as needed
for uid in test_ids:
    rec = db.get_user_record(uid)
    prefix = 'ad' if rec['id_type'].lower()=='aadhaar' else 'pa'
    idp = f'uploads/ocr/{prefix}{uid}.jpg'
    facep = rec.get('id_face_image_path') or f'uploads/facever/{uid}.jpg'
    try:
        print(uid, v.verify(idp, facep, uid))
    except Exception as e:
        print(uid, 'ERROR', e)