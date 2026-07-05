from datetime import datetime, timedelta
import re


def add_minutes(time_str: str, minutes: int) -> str:
    base = datetime.strptime(time_str, "%H:%M")
    return (base + timedelta(minutes=minutes)).strftime("%H:%M")


def to_minutes(time_str: str) -> int:
    h, m = time_str.split(":")
    return int(h) * 60 + int(m)


def minutes_to_time(minutes: int) -> str:
    minutes = minutes % (24 * 60)
    h = minutes // 60
    m = minutes % 60
    return f"{h:02d}:{m:02d}"


def parse_duration_minutes(duration_text: str, default: int = 60) -> int:
    text = str(duration_text or "").strip().lower()
    if not text:
        return default

    hour_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:hr|hrs|hour|hours|h)\b", text)
    if hour_match:
        return max(15, int(round(float(hour_match.group(1)) * 60)))

    minute_match = re.search(r"(\d+)\s*(?:min|mins|minute|minutes|m)\b", text)
    if minute_match:
        return max(15, int(minute_match.group(1)))

    return default


def awake_window_bounds(wake_time: str, sleep_time: str):
    wake = to_minutes(wake_time)
    sleep = to_minutes(sleep_time)
    if sleep <= wake:
        sleep += 24 * 60
    return wake, sleep


def clamp_minutes(value: int, lower: int, upper: int):
    if upper < lower:
        return lower
    return max(lower, min(value, upper))


def _outside_office_candidate(before_candidate: int, after_candidate: int, office_start: int, office_end: int):
    before_valid = before_candidate < office_start
    after_valid = after_candidate > office_end

    if before_valid and after_valid:
        before_gap = office_start - before_candidate
        after_gap = after_candidate - office_end
        return before_candidate if before_gap >= after_gap else after_candidate
    if before_valid:
        return before_candidate
    if after_valid:
        return after_candidate
    return after_candidate


def _compact_day_schedule(wake_minutes: int, sleep_minutes: int):
    span = max(0, sleep_minutes - wake_minutes)
    ratios = {
        "breakfast": 0.12,
        "lunch": 0.28,
        "tea": 0.42,
        "workout": 0.54,
        "dinner": 0.68,
        "reading": 0.82,
        "meditation": 0.92,
    }
    order = ["breakfast", "lunch", "tea", "workout", "dinner", "reading", "meditation"]

    if span <= 0:
        return {key: wake_minutes for key in order}

    compact_times = {}
    current = wake_minutes
    for index, key in enumerate(order):
        remaining_slots = len(order) - index
        latest_allowed = sleep_minutes - (remaining_slots * 5)
        target = wake_minutes + round(span * ratios[key])
        current = max(current + 5, min(target, latest_allowed))
        compact_times[key] = current

    return compact_times


def _normalize_workout_mode(workout_timing: str = "", planning_notes: str = "") -> str:
    text = f"{workout_timing or ''} {planning_notes or ''}".lower()
    if any(token in text for token in ["morning and evening", "morning & evening", "split", "two sessions", "2 sessions", "both morning and evening"]):
        return "split"
    if "after office" in text or "after-office" in text or "after_office" in text:
        return "after office"
    if "morning" in text:
        return "morning"
    if "evening" in text:
        return "evening"
    return "flexible"


def _make_workout_session(time_minutes: int, duration_minutes: int, label: str):
    return {
        "time": minutes_to_time(time_minutes),
        "duration_minutes": duration_minutes,
        "label": label,
    }


def _allocate_split_sessions(
    wake_minutes: int,
    sleep_minutes: int,
    office_start: int | None,
    office_end: int | None,
    workout_duration_minutes: int,
    workout_label: str,
    workout_mode: str,
):
    sessions = []
    morning_window_end = office_start - 30 if office_start is not None else sleep_minutes - 180
    morning_start = max(wake_minutes + 30, wake_minutes + 45)
    morning_duration = workout_duration_minutes

    if office_start is not None:
        morning_start = min(morning_start, max(wake_minutes + 30, office_start - 150))
        available = max(30, morning_window_end - morning_start)
        morning_duration = min(workout_duration_minutes, available)

    if workout_mode == "split" or workout_mode == "morning":
        sessions.append(_make_workout_session(morning_start, morning_duration, f"{workout_label} - morning session"))

    if workout_mode in {"split", "evening", "after office", "flexible"}:
        if office_end is not None:
            evening_start = max(office_end + 30, morning_start + morning_duration + 360)
        else:
            evening_start = max(morning_start + morning_duration + 360, wake_minutes + 11 * 60)

        evening_start = min(evening_start, sleep_minutes - 150)
        evening_duration = min(workout_duration_minutes, max(30, sleep_minutes - 120 - evening_start))
        if workout_mode != "morning" and evening_duration > 0:
            sessions.append(_make_workout_session(evening_start, evening_duration, f"{workout_label} - evening session"))

    if not sessions:
        start = max(wake_minutes + 45, wake_minutes + 30)
        end_limit = sleep_minutes - 180
        if office_start is not None:
            end_limit = max(wake_minutes + 60, office_start - 45)
        start = min(start, max(wake_minutes + 30, end_limit - workout_duration_minutes))
        duration = min(workout_duration_minutes, max(30, end_limit - start))
        sessions.append(_make_workout_session(start, duration, workout_label))

    return sessions


def _office_day_schedule(wake_minutes: int, sleep_minutes: int, office_start: int, office_end: int, workout_pref: str):
    """
    Build a compact office-friendly schedule that keeps meals and exercise
    outside office hours while preserving a sensible daily order.
    """
    breakfast_minutes = clamp_minutes(
        wake_minutes + 30,
        wake_minutes + 30,
        office_start - 30,
    )

    if breakfast_minutes >= office_start:
        breakfast_minutes = clamp_minutes(
            office_end + 30,
            office_end + 15,
            sleep_minutes - 330,
        )

    if workout_pref == "morning" and office_start - wake_minutes >= 180:
        workout_minutes = clamp_minutes(
            wake_minutes + 45,
            wake_minutes + 30,
            office_start - 120,
        )
        breakfast_minutes = clamp_minutes(
            max(workout_minutes + 45, wake_minutes + 30),
            workout_minutes + 30,
            office_start - 30,
        )
    else:
        workout_minutes = None

    lunch_minutes = max(office_end + 30, breakfast_minutes + 120)
    tea_minutes = lunch_minutes + 30

    if workout_minutes is None:
        workout_minutes = tea_minutes + 30

    dinner_minutes = workout_minutes + 75
    reading_minutes = dinner_minutes + 30
    meditation_minutes = reading_minutes + 30

    return {
        "breakfast": breakfast_minutes,
        "lunch": lunch_minutes,
        "tea": tea_minutes,
        "workout": workout_minutes,
        "dinner": dinner_minutes,
        "reading": reading_minutes,
        "meditation": meditation_minutes,
    }


def parse_office_time(office_text: str):
    """
    Supports:
    - 9 AM to 7 PM
    - office 9am - 7pm
    - 09:30 to 18:30
    - 10 to 6
    """

    text = (office_text or "").lower().strip()

    if not text:
        return None

    # Case 1: 9 AM to 7 PM
    matches = re.findall(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)", text)

    if len(matches) >= 2:
        start_h = int(matches[0][0])
        start_m = int(matches[0][1] or 0)
        start_ampm = matches[0][2]

        end_h = int(matches[1][0])
        end_m = int(matches[1][1] or 0)
        end_ampm = matches[1][2]

        if start_ampm == "pm" and start_h != 12:
            start_h += 12
        if start_ampm == "am" and start_h == 12:
            start_h = 0

        if end_ampm == "pm" and end_h != 12:
            end_h += 12
        if end_ampm == "am" and end_h == 12:
            end_h = 0

        return {
            "start": f"{start_h:02d}:{start_m:02d}",
            "end": f"{end_h:02d}:{end_m:02d}",
        }

    # Case 2: 09:30 to 18:30
    matches_24h = re.findall(r"(\d{1,2}):(\d{2})", text)

    if len(matches_24h) >= 2:
        start_h = int(matches_24h[0][0])
        start_m = int(matches_24h[0][1])
        end_h = int(matches_24h[1][0])
        end_m = int(matches_24h[1][1])

        return {
            "start": f"{start_h:02d}:{start_m:02d}",
            "end": f"{end_h:02d}:{end_m:02d}",
        }

    # Case 3: office 10 to 6
    nums = re.findall(r"\b(\d{1,2})\b", text)

    if len(nums) >= 2:
        start_h = int(nums[0])
        end_h = int(nums[1])

        # Simple assumption for office:
        # start is AM, end is PM
        if start_h < 12:
            start_h = start_h

        if end_h <= 12:
            end_h += 12

        return {
            "start": f"{start_h:02d}:00",
            "end": f"{end_h:02d}:00",
        }

    return None


def validate_awake_office_alignment(wake_time: str, sleep_time: str, office_time: str = ""):
    office = parse_office_time(office_time)
    if not office:
        return []

    errors = []
    wake = to_minutes(wake_time)
    sleep = to_minutes(sleep_time)
    office_start = to_minutes(office["start"])
    office_end = to_minutes(office["end"])

    if office_start < wake:
        errors.append("Office timing starts before the user wakes up.")

    return errors


def build_fixed_schedule(
    wake_time: str,
    sleep_time: str,
    fitness_type: str,
    workout_duration: str,
    workout_timing: str = "",
    office_time: str = "",
    planning_notes: str = "",
):
    wake_minutes, sleep_minutes = awake_window_bounds(wake_time, sleep_time)
    workout_pref = _normalize_workout_mode(workout_timing, planning_notes)
    workout_duration_minutes = parse_duration_minutes(workout_duration, default=60)
    workout_label = (
        "Gym workout"
        if fitness_type == "Gym"
        else "Yoga session"
        if fitness_type == "Yoga"
        else "Gym + yoga"
    )

    awake_span = sleep_minutes - wake_minutes
    if awake_span <= 240:
        compact_times = _compact_day_schedule(wake_minutes, sleep_minutes)
        compact_sessions = [
            _make_workout_session(
                compact_times["workout"],
                min(workout_duration_minutes, max(30, sleep_minutes - compact_times["workout"] - 120)),
                workout_label,
            )
        ]
        return {
            "wake": wake_time,
            "breakfast": minutes_to_time(compact_times["breakfast"]),
            "lunch": minutes_to_time(compact_times["lunch"]),
            "tea": minutes_to_time(compact_times["tea"]),
            "workout": minutes_to_time(compact_times["workout"]),
            "dinner": minutes_to_time(compact_times["dinner"]),
            "reading": minutes_to_time(compact_times["reading"]),
            "meditation": minutes_to_time(compact_times["meditation"]),
            "sleep": minutes_to_time(sleep_minutes),
            "workout_label": workout_label,
            "workout_duration": workout_duration,
            "workout_timing": workout_pref or "flexible",
            "office": parse_office_time(office_time),
            "workout_sessions": compact_sessions,
        }

    breakfast_minutes = clamp_minutes(
        wake_minutes + 90 if workout_pref != "morning" else wake_minutes + 150,
        wake_minutes + 30,
        sleep_minutes - 330,
    )
    lunch_minutes = clamp_minutes(
        breakfast_minutes + 210,
        breakfast_minutes + 90,
        sleep_minutes - 270,
    )
    tea_minutes = clamp_minutes(
        lunch_minutes + 180,
        lunch_minutes + 90,
        sleep_minutes - 210,
    )
    workout_minutes = clamp_minutes(
        tea_minutes + 60 if workout_pref not in {"morning", "split"} else wake_minutes + 45,
        wake_minutes + 30,
        sleep_minutes - workout_duration_minutes - 30,
    )
    dinner_minutes = clamp_minutes(
        max(tea_minutes + 120, workout_minutes + workout_duration_minutes + 75),
        workout_minutes + workout_duration_minutes + 60,
        sleep_minutes - 120,
    )

    office = parse_office_time(office_time)
    workout_sessions = []

    if office:
        office_start = to_minutes(office["start"])
        office_end = to_minutes(office["end"])
        if workout_pref == "split":
            workout_sessions = _allocate_split_sessions(
                wake_minutes,
                sleep_minutes,
                office_start,
                office_end,
                workout_duration_minutes,
                workout_label,
                workout_pref,
            )
        elif workout_pref in {"morning", "evening", "flexible"}:
            workout_sessions = _allocate_split_sessions(
                wake_minutes,
                sleep_minutes,
                office_start,
                office_end,
                workout_duration_minutes,
                workout_label,
                workout_pref,
            )
        elif workout_pref == "after office":
            workout_sessions = []
        if workout_sessions:
            workout_minutes = to_minutes(workout_sessions[0]["time"])
            workout_duration_minutes = workout_sessions[0]["duration_minutes"]
            last_workout = workout_sessions[-1]
            last_workout_end = to_minutes(last_workout["time"]) + last_workout["duration_minutes"]
        else:
            last_workout_end = workout_minutes + workout_duration_minutes
        if workout_pref == "after office":
            workout_start = max(office_end + 30, tea_minutes + 30)
            workout_start = min(workout_start, sleep_minutes - workout_duration_minutes - 15)
            workout_sessions = [
                _make_workout_session(workout_start, workout_duration_minutes, workout_label),
            ]
            workout_minutes = to_minutes(workout_sessions[0]["time"])
            workout_duration_minutes = workout_sessions[0]["duration_minutes"]
            last_workout_end = workout_minutes + workout_duration_minutes
            dinner_minutes = max(last_workout_end + 75, tea_minutes + 60)
            if dinner_minutes > sleep_minutes - 120:
                dinner_minutes = sleep_minutes - 120
            reading_minutes = clamp_minutes(dinner_minutes + 60, dinner_minutes + 30, sleep_minutes - 45)
            meditation_minutes = clamp_minutes(reading_minutes + 30, reading_minutes + 15, sleep_minutes - 15)
        elif workout_sessions:
            adjusted_sessions = []
            for index, session in enumerate(workout_sessions):
                session_time = to_minutes(session["time"])
                session_duration = int(session.get("duration_minutes") or workout_duration_minutes)
                if index == 0 and workout_pref in {"morning", "split"}:
                    session_time = min(session_time, max(wake_minutes + 30, office_start - session_duration - 30))
                elif index == 0:
                    session_time = max(session_time, tea_minutes + 30, office_end + 90)
                else:
                    session_time = max(session_time, tea_minutes + 60, office_end + 120)
                session_time = min(session_time, sleep_minutes - session_duration - 15)
                adjusted_sessions.append(
                    _make_workout_session(session_time, session_duration, session.get("label") or workout_label)
                )
            workout_sessions = adjusted_sessions
            workout_minutes = to_minutes(workout_sessions[0]["time"])
            workout_duration_minutes = workout_sessions[0]["duration_minutes"]
            last_workout = workout_sessions[-1]
            last_workout_end = to_minutes(last_workout["time"]) + last_workout["duration_minutes"]
        else:
            last_workout_end = workout_minutes + workout_duration_minutes
    else:
        if workout_pref == "split":
            workout_sessions = _allocate_split_sessions(
                wake_minutes,
                sleep_minutes,
                None,
                None,
                workout_duration_minutes,
                workout_label,
                workout_pref,
            )
        elif workout_pref == "morning":
            workout_sessions = [_make_workout_session(workout_minutes, workout_duration_minutes, workout_label)]
        elif workout_pref in {"evening", "after office"}:
            workout_sessions = [_make_workout_session(workout_minutes, workout_duration_minutes, workout_label)]
        else:
            workout_sessions = [_make_workout_session(workout_minutes, workout_duration_minutes, workout_label)]
        workout_minutes = to_minutes(workout_sessions[0]["time"])
        workout_duration_minutes = workout_sessions[0]["duration_minutes"]
        last_workout_end = to_minutes(workout_sessions[-1]["time"]) + workout_sessions[-1]["duration_minutes"]

    if workout_pref == "split" and workout_sessions:
        morning_session = workout_sessions[0]
        morning_start = to_minutes(morning_session["time"])
        morning_end = morning_start + int(morning_session.get("duration_minutes") or workout_duration_minutes)
        breakfast_minutes = clamp_minutes(
            max(wake_minutes + 30, morning_end + 30),
            wake_minutes + 30,
            sleep_minutes - 420,
        )
        lunch_minutes = clamp_minutes(
            max(breakfast_minutes + 180, morning_end + 180),
            breakfast_minutes + 90,
            sleep_minutes - 270,
        )
        if len(workout_sessions) >= 2:
            evening_start = to_minutes(workout_sessions[-1]["time"])
            tea_upper = max(lunch_minutes + 180, evening_start - 60)
        else:
            tea_upper = sleep_minutes - 210
        tea_minutes = clamp_minutes(
            max(lunch_minutes + 150, lunch_minutes + 120),
            lunch_minutes + 90,
            tea_upper,
        )
        dinner_minutes = clamp_minutes(
            max(last_workout_end + 75, tea_minutes + 60),
            last_workout_end + 60,
            sleep_minutes - 120,
        )
        reading_minutes = clamp_minutes(dinner_minutes + 60, dinner_minutes + 30, sleep_minutes - 45)
        meditation_minutes = clamp_minutes(reading_minutes + 30, reading_minutes + 15, sleep_minutes - 15)
    else:
        dinner_minutes = clamp_minutes(
            max(tea_minutes + 60, last_workout_end + 75),
            last_workout_end + 60,
            sleep_minutes - 120,
        )
        reading_minutes = clamp_minutes(dinner_minutes + 60, dinner_minutes + 30, sleep_minutes - 45)
        meditation_minutes = clamp_minutes(reading_minutes + 30, reading_minutes + 15, sleep_minutes - 15)
    if not workout_sessions:
        workout_sessions = [_make_workout_session(workout_minutes, workout_duration_minutes, workout_label)]

    return {
        "wake": wake_time,
        "breakfast": minutes_to_time(breakfast_minutes),
        "lunch": minutes_to_time(lunch_minutes),
        "tea": minutes_to_time(tea_minutes),
        "workout": minutes_to_time(workout_minutes),
        "dinner": minutes_to_time(dinner_minutes),
        "reading": minutes_to_time(reading_minutes),
        "meditation": minutes_to_time(meditation_minutes),
        "sleep": minutes_to_time(sleep_minutes),
        "workout_label": workout_label,
        "workout_duration": workout_duration,
        "workout_timing": workout_pref or "flexible",
        "office": office,
        "workout_sessions": workout_sessions,
    }
