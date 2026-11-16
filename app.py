from flask import (
    Flask,
    render_template,
    request,
    redirect,
    session,
    send_file,
    send_from_directory
)

import sqlite3
import os
import subprocess
import sys
import base64
import shutil
import re
import json
from datetime import datetime

from utils.attendance_service import mark_attendance_for_student
from utils.time_slot import format_time_for_display, get_active_slot_for_time
from utils.face_preprocess import preprocess_face
import cv2
import numpy as np
from flask import jsonify


def load_face_recognizer(model_path):
    try:
        face_module = getattr(cv2, "face", None)
        if face_module is None:
            return None
        recognizer = face_module.LBPHFaceRecognizer_create()
        if os.path.exists(model_path):
            recognizer.read(model_path)
        return recognizer
    except Exception:
        return None

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "smart_attendance_secret")

# Werkzeug 3.1+ limits non-file form fields to 500KB by default.
# Our signup form sends webcam-captured photos as base64 JSON in a
# hidden text field, which easily exceeds that limit with 3-5 photos
# and triggers "413 Request Entity Too Large". Raise the limit here.
app.request_class.max_form_memory_size = 15 * 1024 * 1024  # 15 MB
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # 25 MB overall request cap


def get_db_connection():
    conn = sqlite3.connect("database/attendance.db")
    conn.row_factory = sqlite3.Row
    return conn


def get_active_location():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM attendance_locations WHERE active = 1 ORDER BY id DESC LIMIT 1"
    )
    location = cursor.fetchone()
    conn.close()
    return location


def get_active_slot():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM attendance_slots ORDER BY id DESC")
    slot_rows = cursor.fetchall()
    conn.close()
    return get_active_slot_for_time(current_dt=datetime.now(), slot_rows=slot_rows)


def get_configured_slot():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM attendance_slots ORDER BY id DESC LIMIT 1")
    slot = cursor.fetchone()
    conn.close()
    return slot


def delete_student_dataset(roll_number):
    student_folder = os.path.join("dataset", "student_faces", str(roll_number))
    if os.path.isdir(student_folder):
        shutil.rmtree(student_folder)


def save_student_faces(roll_number, uploaded_files, captured_images_json):
    """Save multiple enrollment photos for a student.

    LBPH accuracy/stability improves a lot when trained on several photos
    per person (different angle/lighting) instead of just one. This saves
    every uploaded file plus every captured webcam frame into the
    student's dataset folder as face_1.jpg, face_2.jpg, ... (the first one
    is also duplicated as face.jpg so existing code that serves a single
    preview image, e.g. /student-face/<roll>, keeps working unchanged).

    Returns the number of images actually saved.
    """
    student_folder = os.path.join("dataset", "student_faces", str(roll_number))
    os.makedirs(student_folder, exist_ok=True)

    saved_count = 0

    # SAVE UPLOADED FILES (supports the <input type="file" multiple> case)
    if uploaded_files:
        for uploaded_file in uploaded_files:
            if not uploaded_file or uploaded_file.filename == "":
                continue
            saved_count += 1
            uploaded_file.save(
                os.path.join(student_folder, f"face_{saved_count}.jpg")
            )

    # SAVE CAPTURED WEBCAM FRAMES (JSON array of base64 data URLs)
    if captured_images_json:
        try:
            captured_list = json.loads(captured_images_json)
        except (ValueError, TypeError):
            captured_list = []

        for image_data_url in captured_list:
            if not image_data_url or "," not in image_data_url:
                continue
            image_data = image_data_url.split(",", 1)[1]
            saved_count += 1
            with open(
                os.path.join(student_folder, f"face_{saved_count}.jpg"), "wb"
            ) as file:
                file.write(base64.b64decode(image_data))

    # Keep a plain "face.jpg" copy of the first photo for legacy previews
    if saved_count > 0:
        first_photo = os.path.join(student_folder, "face_1.jpg")
        shutil.copyfile(first_photo, os.path.join(student_folder, "face.jpg"))

    return saved_count


def retrain_face_model():
    """Retrain the LBPH face-recognition model using every enrolled
    student's photos. Runs the same script the admin's "Retrain Model"
    button triggers, so it can be called automatically (e.g. right after
    a student signs up) without needing an admin to click anything.

    Returns (success, message) but never raises -- signup should still
    succeed even if retraining fails for some reason (e.g. missing
    opencv-contrib), so the caller can just log/ignore the message.
    """
    try:
        result = subprocess.run(
            [sys.executable, "-m", "utils.train_model"],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
    except Exception as exc:
        return False, f"Retraining could not be started: {exc}"

    if result.returncode == 0 and "Model Trained Successfully!" in result.stdout:
        return True, "Model retrained successfully using all enrolled student photos."

    return False, "Retraining failed. " + (result.stderr.strip() or result.stdout.strip() or "Unknown error.")


# =========================
# DATABASE INITIALIZATION
# =========================

def init_db():

    os.makedirs("database", exist_ok=True)
    os.makedirs("models", exist_ok=True)
    os.makedirs("dataset/student_faces", exist_ok=True)

    conn = sqlite3.connect("database/attendance.db")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admin_users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT DEFAULT 'admin',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        roll_number TEXT UNIQUE NOT NULL,
        aadhaar TEXT,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT,
        student_roll_number TEXT,
        date TEXT,
        time TEXT,
        slot_id INTEGER,
        slot_name TEXT,
        location_latitude REAL,
        location_longitude REAL,
        location_radius REAL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS attendance_locations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT DEFAULT 'Campus Location',
        latitude REAL NOT NULL,
        longitude REAL NOT NULL,
        allowed_radius REAL NOT NULL,
        active INTEGER DEFAULT 1,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS attendance_slots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slot_name TEXT NOT NULL,
        start_time TEXT NOT NULL,
        end_time TEXT NOT NULL,
        active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("PRAGMA table_info(students)")
    student_columns = [row[1] for row in cursor.fetchall()]
    if "active" not in student_columns:
        cursor.execute("ALTER TABLE students ADD COLUMN active INTEGER DEFAULT 1")

    cursor.execute("PRAGMA table_info(attendance)")
    attendance_columns = [row[1] for row in cursor.fetchall()]
    if "student_roll_number" not in attendance_columns:
        cursor.execute("ALTER TABLE attendance ADD COLUMN student_roll_number TEXT")
    if "slot_id" not in attendance_columns:
        cursor.execute("ALTER TABLE attendance ADD COLUMN slot_id INTEGER")
    if "slot_name" not in attendance_columns:
        cursor.execute("ALTER TABLE attendance ADD COLUMN slot_name TEXT")
    if "location_latitude" not in attendance_columns:
        cursor.execute("ALTER TABLE attendance ADD COLUMN location_latitude REAL")
    if "location_longitude" not in attendance_columns:
        cursor.execute("ALTER TABLE attendance ADD COLUMN location_longitude REAL")
    if "location_radius" not in attendance_columns:
        cursor.execute("ALTER TABLE attendance ADD COLUMN location_radius REAL")

    cursor.execute("SELECT * FROM admin_users WHERE username = ?", ("admin",))
    admin_exists = cursor.fetchone()
    if not admin_exists:
        cursor.execute(
            "INSERT INTO admin_users (username, password) VALUES (?, ?)",
            ("admin", "admin123")
        )

    cursor.execute("SELECT COUNT(*) FROM attendance_locations")
    location_count = cursor.fetchone()[0]
    if location_count == 0:
        cursor.execute(
            "INSERT INTO attendance_locations (latitude, longitude, allowed_radius) VALUES (?, ?, ?)",
            (25.148432703305623, 80.85475153217308, 30)
        )

    cursor.execute("SELECT COUNT(*) FROM attendance_slots")
    slot_count = cursor.fetchone()[0]
    if slot_count == 0:
        cursor.executemany(
            "INSERT INTO attendance_slots (slot_name, start_time, end_time) VALUES (?, ?, ?)",
            [
                ("Morning", "09:00:00", "09:15:00"),
                ("Afternoon", "12:00:00", "12:15:00"),
                ("Evening", "15:00:00", "15:15:00")
            ]
        )

    conn.commit()
    conn.close()


# =========================
# HOME PAGE
# =========================
@app.route("/")
def home():

    return render_template(
        "home.html"
    )


# =========================
# STUDENT SIGNUP
# =========================
@app.route(
    "/signup",
    methods=["GET", "POST"]
)
def signup():

    if request.method == "POST":

        # FORM DATA
        name = request.form["name"]

        roll_number = request.form[
            "roll_number"
        ]

        aadhaar = request.form[
            "aadhaar"
        ]

        email = request.form[
            "email"
        ]

        password = request.form[
            "password"
        ]

        # IMAGE DATA (multiple photos supported for better LBPH accuracy)
        face_images = request.files.getlist(
            "face_image"
        )

        captured_images_json = request.form.get(
            "captured_images"
        )

        conn = sqlite3.connect(
            "database/attendance.db"
        )

        cursor = conn.cursor()

        # CHECK DUPLICATE STUDENT
        cursor.execute("""
        SELECT *
        FROM students
        WHERE roll_number = ?
        """, (roll_number,))

        existing_student = cursor.fetchone()

        if existing_student:

            conn.close()

            return render_template("signup.html", error="A student with this roll number is already registered.")

        # SAVE ALL UPLOADED / CAPTURED PHOTOS
        saved_count = save_student_faces(
            roll_number,
            face_images,
            captured_images_json
        )

        if saved_count == 0:

            conn.close()

            return render_template("signup.html", error="Please upload or capture at least one face photo.")

        # SAVE STUDENT
        cursor.execute("""
        INSERT INTO students
        (
            name,
            roll_number,
            aadhaar,
            email,
            password
        )
        VALUES (?, ?, ?, ?, ?)
        """, (
            name,
            roll_number,
            aadhaar,
            email,
            password
        ))

        conn.commit()
        conn.close()

        # AUTO-RETRAIN: train the face-recognition model right away on
        # the new photos, so the student can mark attendance immediately
        # without an admin having to click "Retrain Model" manually.
        retrain_success, retrain_message = retrain_face_model()

        if retrain_success:
            return redirect("/login?registered=1")
        else:
            # Signup itself still succeeded -- just let the student know
            # face recognition isn't ready yet so they don't get confused
            # if attendance marking fails right after registering.
            return redirect("/login?registered=1&retrain_warning=1")


    return render_template(
        "signup.html"
    )


# =========================
# STUDENT LOGIN
# =========================
@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if request.method == "POST":

        email = request.form[
            "email"
        ]

        password = request.form[
            "password"
        ]

        conn = sqlite3.connect(
            "database/attendance.db"
        )

        cursor = conn.cursor()

        cursor.execute("""
        SELECT *
        FROM students
        WHERE email = ?
        AND password = ?
        """, (
            email,
            password
        ))

        student = cursor.fetchone()

        conn.close()

        if student:

            session["student_id"] = student[0]
            session["student_name"] = student[1]
            session["roll_number"] = student[2]

            return redirect(
                "/student-dashboard"
            )

        else:

            return render_template("login.html", error="Invalid email or password. Please try again.")

    return render_template(
        "login.html"
    )


@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    error = None
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, email FROM students WHERE email = ?', (email,))
        user = cursor.fetchone()
        conn.close()
        if not user:
            error = 'No student account found with that email address.'
        else:
            # Save email in session for the reset step
            session['pw_reset_email'] = email
            return render_template('reset_password.html', email=email)
    return render_template('forgot_password.html', error=error)


@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    error = None
    email = request.values.get('email') or session.get('pw_reset_email')
    if not email:
        return redirect('/forgot-password')
    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm = request.form.get('confirm', '')
        if password != confirm:
            error = 'Passwords do not match.'
        else:
            password_regex = re.compile(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$')
            if not password_regex.match(password):
                error = 'Password must contain at least 8 characters, including uppercase, lowercase, number, and special character.'
            else:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute('UPDATE students SET password = ?, updated_at = CURRENT_TIMESTAMP WHERE email = ?', (password, email))
                conn.commit()
                conn.close()
                session.pop('pw_reset_email', None)
                return redirect('/login?password_reset=1')
    return render_template('reset_password.html', error=error, email=email)


# =========================
# STUDENT DASHBOARD
# =========================
@app.route("/student-dashboard")
def student_dashboard():

    if "student_id" not in session:

        return redirect("/login")

    conn = sqlite3.connect(
        "database/attendance.db"
    )

    cursor = conn.cursor()

    roll_number = session[
        "roll_number"
    ]

    # GET STUDENT DATA
    cursor.execute("""
    SELECT *
    FROM students
    WHERE roll_number = ?
    """, (roll_number,))

    student = cursor.fetchone()

    # TODAY DATE
    today_date = datetime.now().strftime(
        "%Y-%m-%d"
    )

    # CHECK TODAY ATTENDANCE
    cursor.execute("""
    SELECT *
    FROM attendance
    WHERE student_id = ?
    AND date = ?
    """, (
        roll_number,
        today_date
    ))

    attendance = cursor.fetchone()

    conn.close()

    if attendance:

        attendance_status = "Present"

    else:

        attendance_status = "Not Marked"

    return render_template(
        "student_dashboard.html",
        student=student,
        attendance_status=attendance_status
    )


# =========================
# MARK ATTENDANCE PAGE
# =========================
@app.route("/mark-attendance")
def mark_attendance():

    active_location = get_active_location()
    active_slot = get_active_slot()
    configured_slot = get_configured_slot()

    return render_template(
        "mark_attendance.html",
        active_location=active_location,
        active_slot=active_slot,
        configured_slot=configured_slot
    )


@app.route('/student-face/<roll>')
def student_face(roll):
    # Serve the enrolled face image for a student (used in verification UI)
    try:
        path = os.path.join('dataset', 'student_faces', str(roll), 'face.jpg')
        if os.path.exists(path):
            return send_file(path)
        # fallback to a static illustration
        return send_from_directory('static/images', 'attendance-illustration.svg')
    except Exception:
        return send_from_directory('static/images', 'attendance-illustration.svg')


# =========================
# FACE IDENTITY API
# =========================
@app.route("/api/verify-attendance", methods=["POST"])
def api_verify_attendance():
    """Called from JS after face recognition to verify identity before marking attendance."""
    from flask import jsonify
    if "student_id" not in session:
        return jsonify({"success": False, "message": "Not logged in."}), 401

    data = request.get_json(silent=True) or {}
    recognized_roll = str(data.get("recognized_roll", "")).strip()
    logged_in_roll = str(session.get("roll_number", "")).strip()

    if recognized_roll and recognized_roll != logged_in_roll:
        return jsonify({"success": False, "message": "Face does not belong to the logged-in account."})

    # Proceed to mark attendance
    try:
        result = mark_attendance_for_student(
            student_roll_number=logged_in_roll,
            current_dt=datetime.now(),
        )
        message = (
            f"Attendance recorded for the {result['slot_name']} slot at {result.get('time_display', result['time'])} on {result['date']}."
        )
        return jsonify({"success": True, "message": message})
    except ValueError as exc:
        return jsonify({"success": False, "message": str(exc)})
    except Exception as exc:
        return jsonify({"success": False, "message": "Server error: " + str(exc)})


# =========================
# START ATTENDANCE
# =========================
@app.route("/start-attendance")
@app.route('/api/verify-face', methods=['POST'])
def api_verify_face():
    """Accepts a base64 image from the client, runs local face detection + recognizer and returns the recognized roll id."""
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in.'}), 401

    data = request.get_json(silent=True) or {}
    image_data = data.get('image') or ''

    if not image_data:
        return jsonify({'success': False, 'message': 'No image provided.'}), 400

    try:
        # strip data url prefix
        if ',' in image_data:
            image_data = image_data.split(',', 1)[1]
        img_bytes = base64.b64decode(image_data)
        arr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError('Could not decode image')

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)

        if len(faces) == 0:
            return jsonify({'success': False, 'message': 'No face detected.'}), 200

        x, y, w, h = faces[0]
        face = gray[y:y+h, x:x+w]
        face = preprocess_face(face)

        recognizer = load_face_recognizer('models/face_trainer.yml')
        if recognizer is None:
            return jsonify({'success': True, 'recognized_roll': str(session.get('roll_number', '')).strip(), 'confidence': 0.0, 'fallback': True})

        label, confidence = recognizer.predict(face)

        return jsonify({'success': True, 'recognized_roll': str(label), 'confidence': float(confidence)})

    except Exception as exc:
        return jsonify({'success': False, 'message': 'Server error: ' + str(exc)}), 500


def start_attendance():
    if "student_id" not in session:
        return redirect("/login")

    # Allow client-provided recognized_roll to bypass server camera if provided
    recognized_roll_param = request.args.get('recognized_roll')
    logged_in_roll = str(session.get("roll_number")).strip()

    if recognized_roll_param:
        recognized_roll_param = str(recognized_roll_param).strip()
        if recognized_roll_param != logged_in_roll:
            return render_template(
                "attendance_result.html",
                success=False,
                message="The recognized face does not match the logged-in student.",
                debug=f"recognized={recognized_roll_param}, logged_in={logged_in_roll}",
            )
        try:
            result = mark_attendance_for_student(
                student_roll_number=logged_in_roll,
                current_dt=datetime.now(),
            )
            message = (
                f"Attendance recorded successfully for the {result['slot_name']} slot at {result['time']} on {result['date']}."
            )
            return render_template("attendance_result.html", success=True, message=message, debug="")
        except ValueError as exc:
            return render_template(
                "attendance_result.html",
                success=False,
                message=f"Attendance could not be recorded: {exc}",
                debug="",
            )
        except Exception as exc:
            return render_template(
                "attendance_result.html",
                success=False,
                message="Attendance could not be recorded due to a server error.",
                debug=str(exc),
            )

    # Enforce live face verification using a one-shot recognizer script
    try:
        # run recognition script with a short timeout
        proc = subprocess.run(
            [sys.executable, "utils/recognize_once.py"],
            capture_output=True,
            timeout=15,
            text=True,
        )

        stdout = proc.stdout.strip()
        try:
            import json
            result_json = json.loads(stdout) if stdout else {}
        except Exception:
            result_json = {}

        if not result_json.get("success"):
            debug = result_json.get("error", proc.stderr)
            return render_template(
                "attendance_result.html",
                success=False,
                message="Face verification failed. Please ensure your face is visible to the camera and try again.",
                debug=str(debug),
            )

        recognized_roll = str(result_json.get("recognized_roll", "")).strip()

        if recognized_roll == "":
            return render_template(
                "attendance_result.html",
                success=False,
                message="No face recognized. Please try again.",
                debug=stdout or proc.stderr,
            )

        if recognized_roll != logged_in_roll:
            return render_template(
                "attendance_result.html",
                success=False,
                message="The recognized face does not match the logged-in student.",
                debug=f"recognized={recognized_roll}, logged_in={logged_in_roll}",
            )

        # If matched, mark attendance
        result = mark_attendance_for_student(
            student_roll_number=logged_in_roll,
            current_dt=datetime.now(),
        )

        message = (
            f"Attendance recorded successfully for the {result['slot_name']} slot at {result.get('time_display', result['time'])} on {result['date']}."
        )
        return render_template("attendance_result.html", success=True, message=message, debug="")

    except subprocess.TimeoutExpired:
        return render_template(
            "attendance_result.html",
            success=False,
            message="Face recognition timed out. Please try again.",
            debug="timeout",
        )
    except ValueError as exc:
        return render_template(
            "attendance_result.html",
            success=False,
            message=f"Attendance could not be recorded: {exc}",
            debug="",
        )
    except Exception as exc:
        return render_template(
            "attendance_result.html",
            success=False,
            message="Attendance could not be recorded due to a server error.",
            debug=str(exc),
        )


# =========================
# ADMIN LOGIN
# =========================
@app.route(
    "/admin-login",
    methods=["GET", "POST"]
)
def admin_login():

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if "@" not in username:
            return render_template(
                "admin/login.html",
                error="Username must include '@' (for example admin@domain)"
            )

        password_regex = re.compile(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*[^A-Za-z0-9]).+$')
        if not password_regex.match(password):
            return render_template(
                "admin/login.html",
                error="Password must include uppercase, lowercase, and a special character"
            )

        conn = sqlite3.connect(
            "database/attendance.db"
        )

        cursor = conn.cursor()

        cursor.execute("""
        SELECT *
        FROM admin_users
        WHERE username = ?
        AND password = ?
        """, (
            username,
            password
        ))

        admin = cursor.fetchone()

        conn.close()

        if admin:

            session["admin"] = username

            return redirect(
                "/admin-dashboard"
            )

        else:

            return render_template("admin/login.html", error="Invalid admin credentials.")

    return render_template(
        "admin/login.html"
    )


# =========================
# ADMIN DASHBOARD
# =========================
@app.route("/admin-dashboard")
def admin_dashboard():

    if "admin" not in session:

        return redirect(
            "/admin-login"
        )

    conn = get_db_connection()
    cursor = conn.cursor()

    total_students = cursor.execute(
        "SELECT COUNT(*) FROM students"
    ).fetchone()[0]

    active_students = cursor.execute(
        "SELECT COUNT(*) FROM students WHERE active = 1"
    ).fetchone()[0]

    inactive_students = total_students - active_students

    total_attendance = cursor.execute(
        "SELECT COUNT(*) FROM attendance"
    ).fetchone()[0]

    today_date = datetime.now().strftime("%Y-%m-%d")
    today_attendance = cursor.execute(
        "SELECT COUNT(DISTINCT student_id) FROM attendance WHERE date = ?",
        (today_date,)
    ).fetchone()[0]

    active_slot = get_active_slot()
    active_location = get_active_location()

    conn.close()

    return render_template(
        "admin/dashboard.html",
        total_students=total_students,
        total_attendance=total_attendance,
        active_slot=active_slot,
        active_location=active_location,
        active_students=active_students,
        inactive_students=inactive_students,
        today_attendance=today_attendance
    )


# =========================
# CREATE NEW ADMIN
# =========================
@app.route(
    "/admin/create-admin",
    methods=["GET", "POST"]
)
def create_admin():
    if "admin" not in session:
        return redirect("/admin-login")

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        # Validate username format (must start with "admin@")
        if not username.startswith("admin@"):
            return render_template(
                "admin/create_admin.html",
                error="Username must start with 'admin@' (e.g., admin@john)"
            )

        # Validate password complexity
        import re
        password_regex = re.compile(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$')
        if not password_regex.match(password):
            return render_template(
                "admin/create_admin.html",
                error="Password must contain at least 8 characters, including uppercase, lowercase, number, and special character (@$!%*&)"
            )

        # Check if username already exists
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM admin_users WHERE username = ?", (username,))
        existing_admin = cursor.fetchone()

        if existing_admin:
            conn.close()
            return render_template(
                "admin/create_admin.html",
                error="Username already exists"
            )

        # Create new admin
        cursor.execute(
            "INSERT INTO admin_users (username, password, role) VALUES (?, ?, ?)",
            (username, password, "admin")
        )
        conn.commit()
        conn.close()

        return render_template(
            "admin/create_admin.html",
            success="Admin created successfully!"
        )

    return render_template("admin/create_admin.html")


# =========================
# LIST ALL ADMINS
# =========================
@app.route("/admin/admins")
def list_admins():
    if "admin" not in session:
        return redirect("/admin-login")

    conn = get_db_connection()
    cursor = conn.cursor()
    admins = cursor.execute(
        "SELECT id, username, role, created_at FROM admin_users ORDER BY created_at DESC"
    ).fetchall()
    conn.close()

    return render_template("admin/admins.html", admins=admins)


# =========================
# DELETE ADMIN
# =========================
@app.route("/admin/admins/<int:admin_id>/delete", methods=["POST"])
def delete_admin(admin_id):
    if "admin" not in session:
        return redirect("/admin-login")

    # Prevent deleting the last admin or yourself
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check total admins
    total_admins = cursor.execute("SELECT COUNT(*) FROM admin_users").fetchone()[0]
    if total_admins <= 1:
        conn.close()
        return redirect("/admin/admins")
    
    # Get admin to delete
    cursor.execute("SELECT username FROM admin_users WHERE id = ?", (admin_id,))
    admin_to_delete = cursor.fetchone()
    
    if admin_to_delete and admin_to_delete["username"] == session.get("admin"):
        conn.close()
        return redirect("/admin/admins")
    
    # Delete admin
    cursor.execute("DELETE FROM admin_users WHERE id = ?", (admin_id,))
    conn.commit()
    conn.close()

    return redirect("/admin/admins")


# =========================
# ADMIN STUDENT MANAGEMENT
# =========================
@app.route("/admin/students", methods=["GET", "POST"])
@app.route("/students", methods=["GET", "POST"])
def admin_students():

    if "admin" not in session:
        return redirect("/admin-login")

    conn = get_db_connection()
    cursor = conn.cursor()

    query = request.form.get("query") if request.method == "POST" else request.args.get("query", "")

    if query:
        pattern = f"%{query}%"
        cursor.execute(
            """
            SELECT *
            FROM students
            WHERE name LIKE ?
            OR roll_number LIKE ?
            OR email LIKE ?
            ORDER BY active DESC, name ASC
            """,
            (pattern, pattern, pattern)
        )
    else:
        cursor.execute(
            "SELECT * FROM students ORDER BY active DESC, name ASC"
        )

    students = cursor.fetchall()
    conn.close()

    return render_template(
        "admin/students.html",
        students=students,
        query=query
    )


@app.route("/admin/retrain-model", methods=["POST"])
def admin_retrain_model():

    if "admin" not in session:
        return redirect("/admin-login")

    result = subprocess.run(
        [sys.executable, "-m", "utils.train_model"],
        capture_output=True,
        text=True,
        cwd=os.path.dirname(os.path.abspath(__file__))
    )

    if result.returncode == 0 and "Model Trained Successfully!" in result.stdout:
        retrain_message = "Model retrained successfully using all enrolled student photos."
        retrain_success = True
    else:
        retrain_message = "Retraining failed. " + (result.stderr.strip() or result.stdout.strip() or "Unknown error.")
        retrain_success = False

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM students ORDER BY active DESC, name ASC")
    students = cursor.fetchall()
    conn.close()

    return render_template(
        "admin/students.html",
        students=students,
        query="",
        retrain_message=retrain_message,
        retrain_success=retrain_success
    )


@app.route("/admin/students/new", methods=["GET", "POST"])
def admin_add_student():

    if "admin" not in session:
        return redirect("/admin-login")

    if request.method == "POST":
        name = request.form["name"]
        roll_number = request.form["roll_number"]
        aadhaar = request.form["aadhaar"]
        email = request.form["email"]
        password = request.form["password"]
        face_images = request.files.getlist("face_image")
        captured_images_json = request.form.get("captured_images")

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM students WHERE roll_number = ? OR email = ?",
            (roll_number, email)
        )
        if cursor.fetchone():
            conn.close()
            return "<h2>Student already exists. Please use a different roll number or email.</h2>"

        save_student_faces(roll_number, face_images, captured_images_json)

        cursor.execute(
            """
            INSERT INTO students
            (name, roll_number, aadhaar, email, password)
            VALUES (?, ?, ?, ?, ?)
            """,
            (name, roll_number, aadhaar, email, password)
        )
        conn.commit()
        conn.close()

        return redirect("/admin/students")

    return render_template("admin/student_form.html", student=None)


@app.route("/admin/students/<int:student_id>/edit", methods=["GET", "POST"])
def admin_edit_student(student_id):

    if "admin" not in session:
        return redirect("/admin-login")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM students WHERE id = ?", (student_id,))
    student = cursor.fetchone()

    if not student:
        conn.close()
        return "<h2>Student not found</h2>"

    if request.method == "POST":
        name = request.form["name"]
        roll_number = request.form["roll_number"]
        aadhaar = request.form["aadhaar"]
        email = request.form["email"]
        password = request.form["password"]
        active = 1 if request.form.get("active") == "on" else 0

        cursor.execute(
            """
            UPDATE students
            SET name = ?, roll_number = ?, aadhaar = ?, email = ?, password = ?, active = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (name, roll_number, aadhaar, email, password, active, student_id)
        )
        conn.commit()
        conn.close()
        return redirect("/admin/students")

    conn.close()
    return render_template("admin/student_form.html", student=student)


@app.route("/admin/students/<int:student_id>/delete", methods=["POST"])
def admin_delete_student(student_id):

    if "admin" not in session:
        return redirect("/admin-login")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT roll_number FROM students WHERE id = ?", (student_id,))
    student = cursor.fetchone()
    if student:
        roll_number = student["roll_number"]
        cursor.execute(
            "DELETE FROM attendance WHERE student_id = ? OR student_roll_number = ?",
            (roll_number, roll_number)
        )
        cursor.execute("DELETE FROM students WHERE id = ?", (student_id,))
        conn.commit()
        delete_student_dataset(roll_number)
    conn.close()
    return redirect("/admin/students")


@app.route("/admin/students/<int:student_id>/toggle-status", methods=["POST"])
def admin_toggle_student_status(student_id):

    if "admin" not in session:
        return redirect("/admin-login")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT active FROM students WHERE id = ?", (student_id,))
    student = cursor.fetchone()
    if student:
        new_status = 0 if student["active"] == 1 else 1
        cursor.execute("UPDATE students SET active = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (new_status, student_id))
        conn.commit()
    conn.close()
    return redirect("/admin/students")


@app.route("/admin/students/<int:student_id>/details")
def admin_student_details(student_id):

    if "admin" not in session:
        return redirect("/admin-login")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM students WHERE id = ?", (student_id,))
    student = cursor.fetchone()

    if not student:
        conn.close()
        return "<h2>Student not found</h2>"

    cursor.execute(
        """
        SELECT date, time,
            slot_name,
            location_latitude,
            location_longitude,
            location_radius
        FROM attendance
        WHERE student_id = ? OR student_roll_number = ?
        ORDER BY date DESC, time DESC
        """,
        (student["roll_number"], student["roll_number"])
    )
    records = cursor.fetchall()

    total_present = len(records)
    cursor.execute("SELECT COUNT(DISTINCT date || slot_name) FROM attendance")
    total_classes = cursor.fetchone()[0]
    percentage = round((total_present / total_classes) * 100, 2) if total_classes else 0

    conn.close()

    return render_template(
        "admin/student_detail.html",
        student=student,
        records=records,
        total_present=total_present,
        total_classes=total_classes,
        percentage=percentage
    )


@app.route("/admin/students/<int:student_id>/reset-attendance", methods=["POST"])
def admin_reset_student_attendance(student_id):

    if "admin" not in session:
        return redirect("/admin-login")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT roll_number FROM students WHERE id = ?", (student_id,))
    student = cursor.fetchone()
    if student:
        cursor.execute(
            "DELETE FROM attendance WHERE student_id = ? OR student_roll_number = ?",
            (student["roll_number"], student["roll_number"])
        )
        conn.commit()
    conn.close()
    return redirect(f"/admin/students/{student_id}/details")


@app.route("/admin/locations", methods=["GET", "POST"])
def admin_locations():

    if "admin" not in session:
        return redirect("/admin-login")

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == "POST":
        latitude = request.form["latitude"]
        longitude = request.form["longitude"]
        allowed_radius = request.form["allowed_radius"]
        name = request.form.get("name", "Campus Location")
        cursor.execute("UPDATE attendance_locations SET active = 0")
        cursor.execute(
            """
            INSERT INTO attendance_locations
            (name, latitude, longitude, allowed_radius, active)
            VALUES (?, ?, ?, ?, 1)
            """,
            (name, latitude, longitude, allowed_radius)
        )
        conn.commit()
        return redirect("/admin/locations")

    cursor.execute("SELECT * FROM attendance_locations ORDER BY id DESC LIMIT 1")
    location = cursor.fetchone()
    cursor.execute("SELECT * FROM attendance_locations ORDER BY id DESC LIMIT 5")
    history = cursor.fetchall()
    conn.close()

    return render_template(
        "admin/locations.html",
        location=location,
        history=history
    )


@app.route("/admin/slots")
def admin_slots():

    if "admin" not in session:
        return redirect("/admin-login")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM attendance_slots ORDER BY active DESC, id DESC")
    slots = cursor.fetchall()
    conn.close()

    return render_template("admin/slots.html", slots=slots)


@app.route("/admin/slots/new", methods=["GET", "POST"])
def admin_new_slot():

    if "admin" not in session:
        return redirect("/admin-login")

    if request.method == "POST":
        slot_name = request.form["slot_name"]
        start_time = request.form["start_time"]
        end_time = request.form["end_time"]
        active = 1 if request.form.get("active") == "on" else 0

        conn = get_db_connection()
        cursor = conn.cursor()
        if active == 1:
            cursor.execute("UPDATE attendance_slots SET active = 0")
        cursor.execute(
            "INSERT INTO attendance_slots (slot_name, start_time, end_time, active) VALUES (?, ?, ?, ?)",
            (slot_name, start_time, end_time, active)
        )
        conn.commit()
        conn.close()
        return redirect("/admin/slots")

    return render_template("admin/slot_form.html", slot=None)


@app.route("/admin/slots/<int:slot_id>/edit", methods=["GET", "POST"])
def admin_edit_slot(slot_id):

    if "admin" not in session:
        return redirect("/admin-login")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM attendance_slots WHERE id = ?", (slot_id,))
    slot = cursor.fetchone()

    if not slot:
        conn.close()
        return "<h2>Slot not found</h2>"

    if request.method == "POST":
        slot_name = request.form["slot_name"]
        start_time = request.form["start_time"]
        end_time = request.form["end_time"]
        active = 1 if request.form.get("active") == "on" else 0
        if active == 1:
            cursor.execute("UPDATE attendance_slots SET active = 0")
        cursor.execute(
            """
            UPDATE attendance_slots
            SET slot_name = ?, start_time = ?, end_time = ?, active = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (slot_name, start_time, end_time, active, slot_id)
        )
        conn.commit()
        conn.close()
        return redirect("/admin/slots")

    conn.close()
    return render_template("admin/slot_form.html", slot=slot)


@app.route("/admin/slots/<int:slot_id>/delete", methods=["POST"])
def admin_delete_slot(slot_id):

    if "admin" not in session:
        return redirect("/admin-login")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM attendance_slots WHERE id = ?", (slot_id,))
    conn.commit()
    conn.close()
    return redirect("/admin/slots")


# =========================
# ATTENDANCE RECORDS
# =========================
@app.route("/attendance-records")
@app.route("/admin/attendance-records")
def attendance_records():

    if "admin" not in session:
        return redirect("/admin-login")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT
        attendance.id,
        students.name,
        students.roll_number,
        attendance.date,
        attendance.time,
        attendance.slot_name AS slot
    FROM attendance
    INNER JOIN students
        ON attendance.student_roll_number = students.roll_number
        OR attendance.student_id = students.roll_number
    """)

    records = cursor.fetchall()

    conn.close()

    return render_template(
        "attendance_history.html",
        records=records
    )


# =========================
# STUDENT ATTENDANCE HISTORY
# =========================
@app.route(
    "/student-attendance/<roll_number>"
)
def student_attendance(roll_number):

    conn = sqlite3.connect(
        "database/attendance.db"
    )

    cursor = conn.cursor()

    # GET RECORDS
    cursor.execute("""
    SELECT
        students.name,
        students.roll_number,
        attendance.date,
        attendance.time,
        attendance.slot_name AS slot
    FROM attendance
    INNER JOIN students
        ON attendance.student_roll_number = students.roll_number
        OR attendance.student_id = students.roll_number
    WHERE students.roll_number = ?
    """, (roll_number,))

    records = cursor.fetchall()

    # TOTAL PRESENT
    total_present = len(records)

    # TOTAL CLASSES
    cursor.execute("""
    SELECT COUNT(DISTINCT date || slot_name)
    FROM attendance
    """)

    total_classes = cursor.fetchone()[0]

    # ATTENDANCE PERCENTAGE
    if total_classes > 0:

        percentage = round(
            (total_present / total_classes) * 100,
            2
        )

    else:

        percentage = 0

    # PROGRESS CLASS
    progress_value = round(
        percentage / 10
    ) * 10

    if progress_value > 100:

        progress_value = 100

    progress_class = (
        f"w-{progress_value}"
    )

    conn.close()

    return render_template(
        "student_details.html",
        records=records,
        total_present=total_present,
        total_classes=total_classes,
        percentage=percentage,
        progress_class=progress_class
    )


# =========================
# STUDENT LOGOUT
# =========================
@app.route("/student-logout")
def student_logout():

    session.clear()

    return redirect(
        "/login"
    )


# =========================
# ADMIN LOGOUT
# =========================
@app.route("/admin-logout")
def admin_logout():

    session.clear()

    return redirect(
        "/admin-login"
    )


# =========================
# RUN APP
# =========================
# init_db() is called at import time (not just inside __main__) so that the
# tables/default admin exist when the app is started via gunicorn on Render,
# which imports this module and never runs the __main__ block below.
init_db()

if __name__ == "__main__":

    app.run(debug=True, use_reloader=False)
