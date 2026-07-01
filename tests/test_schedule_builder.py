from src.services.schedule_builder import build_fixed_schedule, awake_window_bounds
from src.routes.planner import validate_plan_constraints


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


def test_build_fixed_schedule_moves_lunch_outside_office_hours():
    schedule = build_fixed_schedule(
        wake_time="08:00",
        sleep_time="00:00",
        fitness_type="Yoga",
        workout_duration="1 hr",
        office_time="10:00 to 18:00",
    )

    lunch_minutes = _time_to_minutes(schedule["lunch"])
    assert lunch_minutes < _time_to_minutes("10:00") or lunch_minutes > _time_to_minutes("18:00")


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
