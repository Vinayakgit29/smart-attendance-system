from datetime import datetime
import sqlite3
from utils.attendance_service import mark_attendance_for_student

conn = sqlite3.connect('database/attendance.db')
cur = conn.cursor()
cur.execute("SELECT id, slot_name, start_time, end_time FROM attendance_slots WHERE active=1 ORDER BY id DESC LIMIT 1")
row = cur.fetchone()
print('Active slot row:', row)
if row:
    slot_start = row[2]
    today = datetime.now().date()
    parts = slot_start.split(':')
    h = int(parts[0])
    m = int(parts[1]) if len(parts)>1 else 0
    s = int(parts[2]) if len(parts)>2 else 0
    dt = datetime(today.year, today.month, today.day, h, m, s)
    try:
        res = mark_attendance_for_student('1001', current_dt=dt)
        print('Mark attendance result:', res)
    except Exception as e:
        print('Mark attendance error:', type(e).__name__, str(e))
else:
    print('No active slot found')
