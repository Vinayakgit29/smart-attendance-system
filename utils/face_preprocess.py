import cv2

# Fixed size every face is normalized to before training/recognition.
# Using the SAME size + preprocessing on both sides is critical for LBPH -
# any mismatch (different crop size, no equalization) inflates the
# "confidence" (distance) value a lot, causing correct students to get
# rejected.
FACE_SIZE = (200, 200)


def preprocess_face(gray_face):
    """Resize + histogram-equalize a cropped grayscale face.

    Must be called identically during training (train_model.py) and
    during recognition (recognize_once.py, mark_attendance.py, app.py)
    so the LBPH distance is meaningful.
    """
    face = cv2.resize(gray_face, FACE_SIZE, interpolation=cv2.INTER_LINEAR)
    face = cv2.equalizeHist(face)
    return face
