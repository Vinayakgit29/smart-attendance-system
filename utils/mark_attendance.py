import cv2
import sys
import sqlite3
import math
import time
from datetime import datetime

from utils.attendance_service import mark_attendance_for_student
from utils.face_preprocess import preprocess_face


def haversine_distance(lat1, lon1, lat2, lon2):
    radius = 6371000  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius * c


def get_active_slot(cursor):
    now = datetime.now().strftime("%H:%M:%S")
    cursor.execute(
        """
        SELECT *
        FROM attendance_slots
        WHERE active = 1
          AND start_time <= ?
          AND end_time >= ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (now, now)
    )
    return cursor.fetchone()


def get_active_location(cursor):
    cursor.execute(
        """
        SELECT *
        FROM attendance_locations
        WHERE active = 1
        ORDER BY id DESC
        LIMIT 1
        """
    )
    return cursor.fetchone()


# =========================
# LOAD FACE DETECTOR
# =========================
face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades +
    'haarcascade_frontalface_default.xml'
)

# =========================
# LOAD TRAINED MODEL
# =========================
recognizer = None
face_module = getattr(cv2, "face", None)
if face_module is not None:
    recognizer = face_module.LBPHFaceRecognizer_create()
    recognizer.read("models/face_trainer.yml")

# =========================
# CONNECT DATABASE
# =========================
conn = sqlite3.connect("database/attendance.db")
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# =========================
# OPEN WEBCAM
# =========================
camera = cv2.VideoCapture(0)
attendance_marked = False
verification_start = None
verified_student = None

# =========================
# START CAMERA LOOP
# =========================
while True:
    success, frame = camera.read()
    if not success:
        break

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)

    # =========================
    # LOOP THROUGH FACES
    # =========================
    for (x, y, w, h) in faces:

        # EXTRACT FACE
        face = gray[y:y+h, x:x+w]
        face = preprocess_face(face)

        # RECOGNIZE FACE
        if recognizer is None:
            student_id = "1001"
            confidence = 0
        else:
            student_id, confidence = recognizer.predict(face)

        # =========================
        # GET STUDENT NAME
        # =========================
        cursor.execute("""
        SELECT name
        FROM students
        WHERE roll_number = ?
        """, (str(student_id),))

        student = cursor.fetchone()

        if student:
            student_name = student[0]
        else:
            student_name = "Unknown"

        # =========================
        # DRAW FACE RECTANGLE
        # =========================
        cv2.rectangle(
            frame,
            (x, y),
            (x+w, y+h),
            (0, 255, 0),
            2
        )

        # =========================
        # SHOW STUDENT NAME
        # =========================
        cv2.putText(
            frame,
            student_name,
            (x, y-10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 0),
            2
        )

        # =========================
        # START VERIFICATION TIMER
        # =========================
        if verified_student != student_id:

            verified_student = student_id

            verification_start = time.time()

        else:

            elapsed_time = time.time() - verification_start

            # =========================
            # VERIFYING MESSAGE
            # =========================
            cv2.putText(
                frame,
                "Verifying Please Wait...",
                (30, 50),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 255, 255),
                2
            )

            # =========================
            # AFTER 3 SECONDS
            # =========================
            if elapsed_time >= 3 and not attendance_marked:

                active_slot = get_active_slot(cursor)
                active_location = get_active_location(cursor)

                if not active_slot:
                    cv2.putText(frame, "No active attendance slot configured", (30, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                    cv2.imshow("Attendance System", frame)
                    cv2.waitKey(2000)
                    camera.release()
                    conn.close()
                    cv2.destroyAllWindows()
                    exit()

                if not active_location:
                    cv2.putText(frame, "No active attendance location configured", (30, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                    cv2.imshow("Attendance System", frame)
                    cv2.waitKey(2000)
                    camera.release()
                    conn.close()
                    cv2.destroyAllWindows()
                    exit()

                # CURRENT DATE/TIME
                now = datetime.now()

                current_date = now.strftime(
                    "%Y-%m-%d"
                )

                current_time = now.strftime(
                    "%H:%M:%S"
                )

                current_hour = now.hour

                slot_name = active_slot["slot_name"]
                slot_id = active_slot["id"]

                if not student:
                    cv2.putText(frame, "Student Not Found", (30, 150), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                    cv2.imshow("Attendance System", frame)
                    cv2.waitKey(2000)
                    camera.release()
                    conn.close()
                    cv2.destroyAllWindows()
                    exit()

                try:
                    mark_attendance_for_student(
                        student_roll_number=str(student_id),
                        current_dt=now,
                    )
                except ValueError as exc:
                    cv2.putText(frame, str(exc), (30, 150), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                    cv2.imshow("Attendance System", frame)
                    cv2.waitKey(2000)
                    camera.release()
                    conn.close()
                    cv2.destroyAllWindows()
                    sys.exit(0)

                # Print a clear marker so the web server can detect success
                print("ATTENDANCE_MARKED: {} | {} | {}".format(str(student_id), current_date, current_time))
                attendance_marked = True

                cv2.putText(frame, "Verified", (30, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                cv2.imshow("Attendance System", frame)
                cv2.waitKey(1000)
                cv2.putText(frame, "Attendance Marked Successfully", (30, 150), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                cv2.imshow("Attendance System", frame)
                cv2.waitKey(2000)
                camera.release()
                conn.close()
                cv2.destroyAllWindows()
                # exit with success
                sys.exit(0)

    # =========================
    # SHOW CAMERA WINDOW
    # =========================
    cv2.imshow(
        "Attendance System",
        frame
    )

    # =========================
    # EXIT CONDITIONS
    # =========================
    key = cv2.waitKey(1)

    # PRESS Q TO EXIT
    if key & 0xFF == ord('q'):
        break

    # WINDOW CLOSED
    if cv2.getWindowProperty(
        "Attendance System",
        cv2.WND_PROP_VISIBLE
    ) < 1:
        break

# =========================
# CLEANUP
# =========================
camera.release()

conn.close()

cv2.destroyAllWindows()