import os
import sqlite3
import tempfile
import unittest
from datetime import datetime
from unittest.mock import patch

import app as app_module
from utils.attendance_service import mark_attendance_for_student


class AttendanceServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "attendance.db")
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

        self.cursor.execute("""
        CREATE TABLE attendance_locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT DEFAULT 'Campus Location',
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            allowed_radius REAL NOT NULL,
            active INTEGER DEFAULT 1,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)
        self.cursor.execute("""
        CREATE TABLE attendance_slots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slot_name TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)
        self.cursor.execute("""
        CREATE TABLE attendance (
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

        self.cursor.execute(
            "INSERT INTO attendance_locations (latitude, longitude, allowed_radius, active) VALUES (?, ?, ?, ?)",
            (25.0, 80.0, 30.0, 1),
        )
        self.cursor.execute(
            "INSERT INTO attendance_slots (slot_name, start_time, end_time, active) VALUES (?, ?, ?, ?)",
            ("Morning", "08:00:00", "10:00:00", 1),
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        self.temp_dir.cleanup()

    def test_marks_attendance_when_slot_is_active(self):
        result = mark_attendance_for_student(
            student_roll_number="1001",
            current_dt=datetime(2026, 6, 29, 9, 0, 0),
            db_path=self.db_path,
        )

        self.assertEqual(result["student_roll_number"], "1001")
        self.assertEqual(result["slot_name"], "Morning")

        self.cursor.execute("SELECT COUNT(*) FROM attendance WHERE student_roll_number = ?", ("1001",))
        self.assertEqual(self.cursor.fetchone()[0], 1)

    def test_marks_attendance_when_slot_matches_current_time_even_if_not_marked_active(self):
        self.cursor.execute("UPDATE attendance_slots SET active = 0 WHERE slot_name = ?", ("Morning",))
        self.conn.commit()

        result = mark_attendance_for_student(
            student_roll_number="1001",
            current_dt=datetime(2026, 6, 29, 9, 0, 0),
            db_path=self.db_path,
        )

        self.assertEqual(result["slot_name"], "Morning")
        self.cursor.execute("SELECT COUNT(*) FROM attendance WHERE student_roll_number = ?", ("1001",))
        self.assertEqual(self.cursor.fetchone()[0], 1)

    def test_load_face_recognizer_returns_none_when_cv2_face_is_unavailable(self):
        with patch.object(app_module.cv2, "face", None, create=True):
            self.assertIsNone(app_module.load_face_recognizer("models/face_trainer.yml"))

    def test_raises_when_attendance_is_already_marked(self):
        mark_attendance_for_student(
            student_roll_number="1001",
            current_dt=datetime(2026, 6, 29, 9, 0, 0),
            db_path=self.db_path,
        )

        with self.assertRaises(ValueError):
            mark_attendance_for_student(
                student_roll_number="1001",
                current_dt=datetime(2026, 6, 29, 9, 5, 0),
                db_path=self.db_path,
            )


if __name__ == "__main__":
    unittest.main()
