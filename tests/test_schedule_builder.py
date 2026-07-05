from src.services.schedule_builder import build_fixed_schedule, awake_window_bounds, validate_awake_office_alignment
from src.routes.planner import validate_plan_constraints, _skip_office_overlaps


def _time_to_minutes(value: str) -> int:
    hours, minutes = value.split(":")
    return int(hours) * 60 + int(minutes)


def _normalize_for_window(time_value: str, wake_time: str, wraps_midnight: bool) -> int:
    minutes = _time_to_minutes(time_value)
    wake_minutes = _time_to_minutes(wake_time)
    if wraps_midnight and minutes < wake_minutes:
        return minutes + 24 * 60
    return minutes


def test_build_fixed_schedule_keeps_overnight_plan_inside_awake_window():
    wake_time = "08:00"
    sleep_time = "00:00"
    schedule = build_fixed_schedule(
        wake_time=wake_time,
        sleep_time=sleep_time,
        fitness_type="Yoga",
        workout_duration="1 hr",
        office_time="09:00 to 18:00",
    )

    wake_minutes, sleep_minutes = awake_window_bounds(wake_time, sleep_time)
    wraps_midnight = _time_to_minutes(sleep_time) <= _time_to_minutes(wake_time)

    for key in ["wake", "breakfast", "lunch", "tea", "workout", "dinner", "reading", "meditation", "sleep"]:
        normalized = _normalize_for_window(schedule[key], wake_time, wraps_midnight)
        assert wake_minutes <= normalized <= sleep_minutes


def test_validate_plan_constraints_accepts_cross_midnight_sleep():
    wake_time = "08:00"
    sleep_time = "00:00"
    events = [
        {"time": "08:00", "activity": "Wake up and drink water", "category": "wake"},
        {"time": "09:30", "activity": "Poha with curd", "category": "meal"},
        {"time": "13:00", "activity": "Dal and rice", "category": "meal"},
        {"time": "16:30", "activity": "Sprouts chaat", "category": "break"},
        {"time": "18:30", "activity": "Yoga session for 1 hr", "category": "workout"},
        {"time": "21:00", "activity": "Paneer sabzi", "category": "meal"},
        {"time": "22:00", "activity": "Book reading: Deep Work by Cal Newport", "category": "reading"},
        {"time": "22:30", "activity": "Meditation", "category": "meditation"},
        {"time": "00:00", "activity": "Sleep", "category": "sleep"},
    ]

    errors = validate_plan_constraints(events, wake_time, sleep_time, "Veg", office_time="")
    assert errors == []


def test_validate_awake_office_alignment_allows_overnight_office_window():
    errors = validate_awake_office_alignment(
        wake_time="08:00",
        sleep_time="01:00",
        office_time="12:00 to 09:00",
    )

    assert errors == []


def test_build_fixed_schedule_honours_workout_timing():
    morning_schedule = build_fixed_schedule(
        wake_time="06:00",
        sleep_time="22:00",
        fitness_type="Gym",
        workout_duration="1 hr",
        workout_timing="Morning",
        office_time="",
    )
    after_office_schedule = build_fixed_schedule(
        wake_time="06:00",
        sleep_time="22:00",
        fitness_type="Gym",
        workout_duration="1 hr",
        workout_timing="After Office",
        office_time="09:00 to 18:00",
    )

    assert _time_to_minutes(morning_schedule["workout"]) < _time_to_minutes(morning_schedule["breakfast"])
    assert _time_to_minutes(after_office_schedule["workout"]) > _time_to_minutes("18:00")


def test_build_fixed_schedule_keeps_after_office_workout_and_human_order():
    schedule = build_fixed_schedule(
        wake_time="06:00",
        sleep_time="22:00",
        fitness_type="Gym",
        workout_duration="1 hr",
        workout_timing="After Office",
        office_time="09:00 to 18:00",
    )

    assert _time_to_minutes(schedule["workout"]) > _time_to_minutes("18:00")
    ordered_keys = ["breakfast", "lunch", "tea", "workout", "dinner", "reading", "meditation"]
    ordered_minutes = [_time_to_minutes(schedule[key]) for key in ordered_keys]
    assert ordered_minutes == sorted(ordered_minutes)
    assert ordered_minutes[-1] <= _time_to_minutes(schedule["sleep"])


def test_build_fixed_schedule_keeps_meals_in_normal_order_with_office_hours():
    schedule = build_fixed_schedule(
        wake_time="08:00",
        sleep_time="00:00",
        fitness_type="Yoga",
        workout_duration="1 hr",
        office_time="10:00 to 18:00",
    )

    wake_minutes, sleep_minutes = awake_window_bounds("08:00", "00:00")
    lunch_minutes = _time_to_minutes(schedule["lunch"])
    if lunch_minutes < _time_to_minutes("08:00"):
        lunch_minutes += 24 * 60

    assert _time_to_minutes(schedule["breakfast"]) < _time_to_minutes(schedule["lunch"]) < _time_to_minutes(schedule["tea"])
    assert wake_minutes <= lunch_minutes <= sleep_minutes


def test_build_fixed_schedule_compresses_short_awake_window_without_overflow():
    wake_time = "08:00"
    sleep_time = "10:00"
    schedule = build_fixed_schedule(
        wake_time=wake_time,
        sleep_time=sleep_time,
        fitness_type="Gym",
        workout_duration="1 hr",
        office_time="",
    )

    wake_minutes, sleep_minutes = awake_window_bounds(wake_time, sleep_time)
    for key in ["wake", "breakfast", "lunch", "tea", "workout", "dinner", "reading", "meditation", "sleep"]:
        assert wake_minutes <= _time_to_minutes(schedule[key]) <= sleep_minutes


def test_build_fixed_schedule_supports_split_workouts_outside_office_hours():
    schedule = build_fixed_schedule(
        wake_time="06:00",
        sleep_time="23:00",
        fitness_type="Gym",
        workout_duration="2 hr",
        workout_timing="Morning and Evening",
        office_time="09:00 to 18:00",
    )

    office_start = _time_to_minutes("09:00")
    office_end = _time_to_minutes("18:00")
    sessions = schedule.get("workout_sessions", [])

    assert len(sessions) >= 2
    for session in sessions:
        session_time = _time_to_minutes(session["time"])
        assert session_time < office_start or session_time > office_end


def test_build_fixed_schedule_split_workout_looks_human_without_office():
    schedule = build_fixed_schedule(
        wake_time="06:30",
        sleep_time="23:00",
        fitness_type="Gym",
        workout_duration="1.5 hr",
        workout_timing="Both Morning and Evening",
        office_time="",
    )

    wake_minutes, sleep_minutes = awake_window_bounds("06:30", "23:00")
    sessions = schedule.get("workout_sessions", [])

    assert len(sessions) >= 2
    breakfast = _time_to_minutes(schedule["breakfast"])
    lunch = _time_to_minutes(schedule["lunch"])
    tea = _time_to_minutes(schedule["tea"])
    dinner = _time_to_minutes(schedule["dinner"])
    reading = _time_to_minutes(schedule["reading"])
    meditation = _time_to_minutes(schedule["meditation"])
    morning_workout = _time_to_minutes(sessions[0]["time"])
    evening_workout = _time_to_minutes(sessions[-1]["time"])

    assert morning_workout < breakfast < lunch < tea < evening_workout < dinner < reading < meditation
    assert wake_minutes <= breakfast <= sleep_minutes
    assert wake_minutes <= meditation <= sleep_minutes


def test_generated_plan_keeps_sleep_row_last():
    from src.agents.agent1_day_planner import generate_day_plan_with_gpt

    profile = {"name": "Test User", "diseases": [], "diet_type": "Veg"}
    prefs = {
        "wake_time": "06:30",
        "sleep_time": "23:00",
        "diet_type": "Veg",
        "fitness_type": "Gym",
        "workout_duration": "1.5 hr",
        "extra_preferences": {"workout_timing": "Both Morning and Evening"},
    }

    result = generate_day_plan_with_gpt(profile, prefs, {}, {}, return_metadata=True)
    events = result["events"]

    assert events[-1]["category"] == "sleep"
    assert all(event["category"] != "sleep" for event in events[:-1])


def test_skip_office_overlaps_removes_conflicting_slots_and_reports_warning():
    events = [
        {"time": "08:00", "activity": "Wake up and drink water", "category": "wake"},
        {"time": "13:00", "activity": "Vegetable soup with tofu salad", "category": "meal"},
        {"time": "13:15", "activity": "Yoga session for 1 hr", "category": "workout"},
        {"time": "22:30", "activity": "Book reading: Deep Work by Cal Newport", "category": "reading"},
    ]

    kept_events, warnings = _skip_office_overlaps(
        events,
        "13:00 to 22:00",
        "08:00",
        "00:00",
        "Both Morning and Evening",
    )

    assert len(kept_events) == 3
    meal_event = next(event for event in kept_events if event["category"] == "meal")
    assert meal_event["time"] == "13:00"
    assert all(event["category"] != "workout" or event["time"] != "13:15" for event in kept_events)
    assert warnings
    assert "workout was adjusted to fit your work hours" in warnings[0].lower()
