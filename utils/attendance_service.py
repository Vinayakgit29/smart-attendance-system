import sqlite3
from datetime import datetime

from utils.time_slot import format_time_for_display, get_active_slot_for_time


def mark_attendance_for_student(student_roll_number, current_dt=None, db_path="database/attendance.db"):
    if current_dt is None:
        current_dt = datetime.now()

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        current_date = current_dt.strftime("%Y-%m-%d")
        current_time = current_dt.strftime("%H:%M:%S")

        cursor.execute(
            """
            SELECT *
            FROM attendance_slots
            ORDER BY id DESC
            """
        )
        all_slots = cursor.fetchall()
        active_slot = get_active_slot_for_time(current_dt=current_dt, slot_rows=all_slots)

        if not active_slot:
            raise ValueError("No active attendance slot configured")

        cursor.execute(
            """
            SELECT *
            FROM attendance_locations
            WHERE active = 1
            ORDER BY id DESC
            LIMIT 1
            """
        )
        active_location = cursor.fetchone()

        if not active_location:
            raise ValueError("No active attendance location configured")

        cursor.execute(
            """
            SELECT *
            FROM attendance
            WHERE (student_id = ? OR student_roll_number = ?)
              AND date = ?
              AND slot_name = ?
            """,
            (student_roll_number, student_roll_number, current_date, active_slot["slot_name"]),
        )
        existing_attendance = cursor.fetchone()

        if existing_attendance:
            raise ValueError("Attendance already marked")

        cursor.execute(
            """
            INSERT INTO attendance
            (student_id, student_roll_number, date, time, slot_id, slot_name, location_latitude, location_longitude, location_radius)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                student_roll_number,
                student_roll_number,
                current_date,
                current_time,
                active_slot["id"],
                active_slot["slot_name"],
                active_location["latitude"],
                active_location["longitude"],
                active_location["allowed_radius"],
            ),
        )
        conn.commit()

        return {
            "student_roll_number": student_roll_number,
            "date": current_date,
            "time": current_time,
            "time_display": format_time_for_display(current_time),
            "slot_id": active_slot["id"],
            "slot_name": active_slot["slot_name"],
            "location_latitude": active_location["latitude"],
            "location_longitude": active_location["longitude"],
            "location_radius": active_location["allowed_radius"],
        }
    finally:
        conn.close()
