import cv2

# LOAD FACE CASCADE
face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades +
    'haarcascade_frontalface_default.xml'
)

# LOAD TRAINED MODEL
recognizer = cv2.face.LBPHFaceRecognizer_create()

recognizer.read(
    "models/face_trainer.yml"
)

# OPEN WEBCAM
camera = cv2.VideoCapture(0)

while True:

    # READ FRAME
    success, frame = camera.read()

    if not success:
        break

    # CONVERT TO GRAY
    gray = cv2.cvtColor(
        frame,
        cv2.COLOR_BGR2GRAY
    )

    # DETECT FACES
    faces = face_cascade.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=5
    )

    # LOOP THROUGH FACES
    for (x, y, w, h) in faces:

        # EXTRACT FACE
        face = gray[y:y+h, x:x+w]

        # PREDICT FACE
        student_id, confidence = recognizer.predict(face)

        # DRAW RECTANGLE
        cv2.rectangle(
            frame,
            (x, y),
            (x+w, y+h),
            (0, 255, 0),
            2
        )

        # SHOW STUDENT ID
        cv2.putText(
            frame,
            f"ID: {student_id}",
            (x, y-10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 0),
            2
        )

       
    # SHOW WINDOW
    cv2.imshow(
        "Face Recognition",
        frame
    )

    # PRESS Q TO EXIT
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# RELEASE CAMERA
camera.release()

cv2.destroyAllWindows()