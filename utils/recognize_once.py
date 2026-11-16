import cv2
import sys
import json

from utils.face_preprocess import preprocess_face


def load_face_recognizer(model_path):
    face_module = getattr(cv2, "face", None)
    if face_module is None:
        return None
    recognizer = face_module.LBPHFaceRecognizer_create()
    if model_path:
        recognizer.read(model_path)
    return recognizer


def main():
    try:
        face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )

        recognizer = load_face_recognizer("models/face_trainer.yml")
        if recognizer is None:
            print(json.dumps({"success": False, "error": "cv2.face_unavailable"}))
            sys.exit(4)

        camera = cv2.VideoCapture(0)

        # read a few frames to allow camera auto-adjust
        for _ in range(3):
            success, frame = camera.read()

        success, frame = camera.read()

        if not success or frame is None:
            print(json.dumps({"success": False, "error": "camera_failed"}))
            sys.exit(1)

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)

        if len(faces) == 0:
            print(json.dumps({"success": False, "error": "no_face_detected"}))
            sys.exit(2)

        # use first detected face
        x, y, w, h = faces[0]
        face = gray[y:y+h, x:x+w]
        face = preprocess_face(face)

        try:
            label, confidence = recognizer.predict(face)
            print(json.dumps({"success": True, "recognized_roll": str(label), "confidence": float(confidence)}))
            sys.exit(0)
        except Exception as exc:
            print(json.dumps({"success": False, "error": str(exc)}))
            sys.exit(3)
    finally:
        try:
            camera.release()
        except Exception:
            pass

if __name__ == '__main__':
    main()
