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

    if office_end <= office_start:
        errors.append("Office end time must be after office start time.")

    if office_start < wake:
        errors.append("Office timing starts before the user wakes up.")

    if sleep <= wake:
        sleep = sleep + (24 * 60)
    if office_end > sleep:
        errors.append("Office timing continues after the user's sleep time.")

    return errors


def build_fixed_schedule(
    wake_time: str,
    sleep_time: str,
    fitness_type: str,
    workout_duration: str,
    workout_timing: str = "",
    office_time: str = "",
):
    wake_minutes, sleep_minutes = awake_window_bounds(wake_time, sleep_time)
    workout_pref = (workout_timing or "").strip().lower()

    if workout_pref == "morning":
        workout_minutes = clamp_minutes(wake_minutes + 60, wake_minutes + 30, sleep_minutes - 360)
        breakfast_minutes = clamp_minutes(workout_minutes + 60, workout_minutes + 30, sleep_minutes - 330)
        lunch_minutes = clamp_minutes(breakfast_minutes + 210, breakfast_minutes + 120, sleep_minutes - 270)
        tea_minutes = clamp_minutes(lunch_minutes + 210, lunch_minutes + 120, sleep_minutes - 210)
        dinner_minutes = clamp_minutes(max(tea_minutes + 180, workout_minutes + 300), tea_minutes + 75, sleep_minutes - 120)
    else:
        breakfast_minutes = clamp_minutes(
            wake_minutes + 90,
            wake_minutes + 45,
            sleep_minutes - 330,
        )
        lunch_minutes = clamp_minutes(
            breakfast_minutes + 210,
            breakfast_minutes + 120,
            sleep_minutes - 270,
        )
        tea_minutes = clamp_minutes(
            lunch_minutes + 210,
            lunch_minutes + 120,
            sleep_minutes - 210,
        )
        workout_minutes = clamp_minutes(
            tea_minutes + 60,
            tea_minutes + 30,
            sleep_minutes - 180,
        )
        dinner_minutes = clamp_minutes(
            max(tea_minutes + 180, workout_minutes + 90),
            workout_minutes + 75,
            sleep_minutes - 120,
        )

    office = parse_office_time(office_time)

    if office:
        office_start = to_minutes(office["start"])
        office_end = to_minutes(office["end"])

        if workout_pref in {"after office", "after-office", "after_office"}:
            workout_minutes = office_end + 15
            breakfast_minutes = clamp_minutes(breakfast_minutes, wake_minutes + 30, workout_minutes - 180)
            lunch_minutes = clamp_minutes(max(lunch_minutes, breakfast_minutes + 120), breakfast_minutes + 120, workout_minutes - 120)
            tea_minutes = clamp_minutes(max(tea_minutes, lunch_minutes + 120), lunch_minutes + 120, workout_minutes - 60)
            dinner_minutes = clamp_minutes(max(dinner_minutes, workout_minutes + 75), workout_minutes + 75, sleep_minutes - 120)
        elif workout_pref == "evening":
            workout_minutes = clamp_minutes(max(tea_minutes + 90, office_end + 90), office_end + 60, sleep_minutes - 180)
            dinner_minutes = clamp_minutes(max(dinner_minutes, workout_minutes + 75), workout_minutes + 75, sleep_minutes - 120)
        elif workout_pref not in {"morning"} and office_start <= workout_minutes <= office_end:
            # If workout falls inside office time, move it after office.
            workout_minutes = office_end + 15

        lunch_before_office = clamp_minutes(
            office_start - 45,
            breakfast_minutes + 120,
            sleep_minutes - 270,
        )
        lunch_after_office = clamp_minutes(
            office_end + 60,
            breakfast_minutes + 120,
            sleep_minutes - 270,
        )

        if office_start <= lunch_minutes <= office_end:
            lunch_minutes = _outside_office_candidate(
                lunch_before_office,
                lunch_after_office,
                office_start,
                office_end,
            )

        if office_start <= lunch_minutes <= office_end:
            lunch_minutes = office_end + 60

        if lunch_minutes < breakfast_minutes + 120:
            lunch_minutes = breakfast_minutes + 120

        if lunch_minutes > sleep_minutes - 270:
            lunch_minutes = sleep_minutes - 270

        if lunch_minutes > office_start and lunch_minutes < office_end:
            lunch_minutes = office_end + 60

        tea_minutes = clamp_minutes(max(tea_minutes, lunch_minutes + 120), lunch_minutes + 120, sleep_minutes - 210)

        # Dinner should not happen inside office time.
        # Keep dinner after office, usually after workout.
        if office_start <= dinner_minutes <= office_end:
            dinner_minutes = office_end + 90

        # If user wrote gym/workout after office, force workout after office.
        office_text = office_time.lower()
        if "gym after office" in office_text or "workout after office" in office_text:
            workout_minutes = office_end + 15
            dinner_minutes = office_end + 105

    reading_minutes = clamp_minutes(dinner_minutes + 60, dinner_minutes + 30, sleep_minutes - 45)
    meditation_minutes = clamp_minutes(reading_minutes + 30, reading_minutes + 15, sleep_minutes - 15)

    if workout_pref == "morning":
        ordered_keys = ["workout", "breakfast", "lunch", "tea", "dinner", "reading", "meditation"]
    else:
        ordered_keys = ["breakfast", "lunch", "tea", "workout", "dinner", "reading", "meditation"]
    candidate_times = {
        "breakfast": breakfast_minutes,
        "lunch": lunch_minutes,
        "tea": tea_minutes,
        "workout": workout_minutes,
        "dinner": dinner_minutes,
        "reading": reading_minutes,
        "meditation": meditation_minutes,
    }
    needs_compact = False
    last_time = wake_minutes
    for key in ordered_keys:
        value = candidate_times[key]
        if value < wake_minutes or value > sleep_minutes or value < last_time:
            needs_compact = True
            break
        last_time = value

    if needs_compact:
        compact_times = _compact_day_schedule(wake_minutes, sleep_minutes)
        breakfast_minutes = compact_times["breakfast"]
        lunch_minutes = compact_times["lunch"]
        tea_minutes = compact_times["tea"]
        workout_minutes = compact_times["workout"]
        dinner_minutes = compact_times["dinner"]
        reading_minutes = compact_times["reading"]
        meditation_minutes = compact_times["meditation"]

    if office is None:
        if workout_pref != "morning":
            breakfast_minutes = clamp_minutes(breakfast_minutes, wake_minutes + 30, sleep_minutes - 330)
            lunch_minutes = clamp_minutes(max(lunch_minutes, breakfast_minutes + 120), breakfast_minutes + 120, sleep_minutes - 270)
            tea_minutes = clamp_minutes(max(tea_minutes, lunch_minutes + 120), lunch_minutes + 120, sleep_minutes - 210)
            workout_minutes = clamp_minutes(max(workout_minutes, tea_minutes + 30), tea_minutes + 30, sleep_minutes - 180)
            dinner_minutes = clamp_minutes(max(dinner_minutes, workout_minutes + 75), workout_minutes + 75, sleep_minutes - 120)
        else:
            breakfast_minutes = clamp_minutes(breakfast_minutes, wake_minutes + 30, sleep_minutes - 330)
            lunch_minutes = clamp_minutes(max(lunch_minutes, breakfast_minutes + 120), breakfast_minutes + 120, sleep_minutes - 270)
            tea_minutes = clamp_minutes(max(tea_minutes, lunch_minutes + 120), lunch_minutes + 120, sleep_minutes - 210)
            dinner_minutes = clamp_minutes(max(dinner_minutes, tea_minutes + 60), tea_minutes + 75, sleep_minutes - 120)

    if needs_compact:
        compact_times = _compact_day_schedule(wake_minutes, sleep_minutes)
        breakfast_minutes = compact_times["breakfast"]
        lunch_minutes = compact_times["lunch"]
        tea_minutes = compact_times["tea"]
        workout_minutes = compact_times["workout"]
        dinner_minutes = compact_times["dinner"]
        reading_minutes = compact_times["reading"]
        meditation_minutes = compact_times["meditation"]
    else:
        reading_minutes = clamp_minutes(dinner_minutes + 60, dinner_minutes + 30, sleep_minutes - 45)
        meditation_minutes = clamp_minutes(reading_minutes + 30, reading_minutes + 15, sleep_minutes - 15)

    if office:
        if office_start <= lunch_minutes <= office_end:
            lunch_candidate_after = office_end + 60
            lunch_candidate_before = max(wake_minutes + 120, office_start - 45)
            if lunch_candidate_after <= sleep_minutes - 270:
                lunch_minutes = lunch_candidate_after
            else:
                lunch_minutes = min(lunch_candidate_before, sleep_minutes - 270)

        tea_minutes = max(tea_minutes, lunch_minutes + 120)
        if office_start <= tea_minutes <= office_end:
            tea_minutes = office_end + 120

        if office_start <= workout_minutes <= office_end and workout_pref not in {"morning"}:
            workout_minutes = office_end + 15

        dinner_minutes = max(dinner_minutes, tea_minutes + 60)
        if office_start <= dinner_minutes <= office_end:
            dinner_minutes = office_end + 90

        reading_minutes = max(reading_minutes, dinner_minutes + 30)
        meditation_minutes = max(meditation_minutes, reading_minutes + 15)
        meditation_minutes = min(meditation_minutes, sleep_minutes - 15)

    workout_label = (
        "Gym workout"
        if fitness_type == "Gym"
        else "Yoga session"
        if fitness_type == "Yoga"
        else "Gym + yoga"
    )

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
    }
