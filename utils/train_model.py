import cv2
import os
import numpy as np

from utils.face_preprocess import preprocess_face

# LOAD FACE CASCADE
face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades +
    'haarcascade_frontalface_default.xml'
)

# CREATE RECOGNIZER
face_module = getattr(cv2, "face", None)
if face_module is None:
    raise SystemExit(
        "cv2.face is not available. Your installed OpenCV build is missing the "
        "'face' (contrib) module.\n"
        "Fix: pip uninstall opencv-python opencv-python-headless opencv-contrib-python -y\n"
        "     pip install opencv-contrib-python"
    )

recognizer = face_module.LBPHFaceRecognizer_create()

faces = []
labels = []

dataset_path = "dataset/student_faces"

# LOOP THROUGH STUDENTS
for student_id in os.listdir(dataset_path):

    student_folder = os.path.join(
        dataset_path,
        student_id
    )

    # LOOP THROUGH IMAGES
    for image_name in os.listdir(student_folder):

        image_path = os.path.join(
            student_folder,
            image_name
        )

        print(f"Reading Image: {image_path}")

        # READ IMAGE
        image = cv2.imread(image_path)

        # CHECK IMAGE
        if image is None:
            print("Image Not Loaded")
            continue

        # CONVERT TO GRAY
        gray = cv2.cvtColor(
            image,
            cv2.COLOR_BGR2GRAY
        )

        # DETECT FACES
        detected_faces = face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5
        )

        print(
            f"Faces Detected: {len(detected_faces)}"
        )

        # EXTRACT FACE
        for (x, y, w, h) in detected_faces:

            face = gray[y:y+h, x:x+w]
            face = preprocess_face(face)

            faces.append(face)

            labels.append(int(student_id))

# CHECK BEFORE TRAINING
if len(faces) == 0:

    print("No faces found for training!")

else:

    recognizer.train(
        faces,
        np.array(labels)
    )

    recognizer.save(
        "models/face_trainer.yml"
    )

    print("Model Trained Successfully!")