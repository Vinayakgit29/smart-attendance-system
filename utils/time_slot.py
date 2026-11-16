from datetime import datetime


def _get_value(row, key):
    if hasattr(row, "keys"):
        try:
            return row[key]
        except Exception:
            pass
    if isinstance(row, dict):
        return row.get(key)
    return getattr(row, key, None)


def normalize_time(value):
    if not value:
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        if len(value) == 5:
            value = value + ":00"
        if len(value) == 8 and value.count(":") == 1:
            value = value + ":00"
    try:
        parsed = datetime.strptime(str(value), "%H:%M:%S")
    except ValueError:
        try:
            parsed = datetime.strptime(str(value), "%H:%M")
        except ValueError:
            return None
    return parsed.time()


def parse_time_to_seconds(value):
    parsed_time = normalize_time(value)
    if parsed_time is None:
        return None
    return parsed_time.hour * 3600 + parsed_time.minute * 60 + parsed_time.second


def get_active_slot_for_time(current_dt=None, slot_rows=None):
    if current_dt is None:
        current_dt = datetime.now()
    if slot_rows is None:
        return None

    now_seconds = current_dt.hour * 3600 + current_dt.minute * 60 + current_dt.second
    matching_slots = []
    for slot in slot_rows:
        start_seconds = parse_time_to_seconds(_get_value(slot, "start_time"))
        end_seconds = parse_time_to_seconds(_get_value(slot, "end_time"))
        if start_seconds is None or end_seconds is None:
            continue
        if start_seconds <= now_seconds <= end_seconds:
            matching_slots.append(slot)

    if not matching_slots:
        return None

    matching_slots.sort(key=lambda item: (_get_value(item, "active") == 1, _get_value(item, "id") or 0), reverse=True)
    return matching_slots[0]


def format_time_for_display(value):
    parsed_time = normalize_time(value)
    if parsed_time is None:
        return ""
    return parsed_time.strftime("%I:%M:%S %p").lstrip("0").replace(" 0", " ")
