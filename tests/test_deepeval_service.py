from src.services.deepeval_service import evaluate_day_plan


def test_deepeval_evaluate_day_plan_flags_office_and_workout_overlap():
    profile = {"name": "Test User"}
    preferences = {
        "diet_type": "Non-Veg",
        "extra_preferences": {
            "office_time": "13:00 to 22:00",
            "workout_timing": "Both Morning and Evening",
            "notes": "Please suggest a comedy book for reading.",
        },
    }
    events = [
        {"time": "08:00", "activity": "Wake up and drink water", "category": "wake"},
        {"time": "14:00", "activity": "Yoga session for 1 hr", "category": "workout", "duration_minutes": 60},
        {"time": "22:30", "activity": "Book reading: Good Omens by Terry Pratchett and Neil Gaiman", "category": "reading"},
    ]

    result = evaluate_day_plan(profile, preferences, events, "Keep dinner light.")

    assert result.overall_score < 1.0
    assert result.metrics["office_alignment"] < 1.0
    assert result.metrics["workout_fit"] < 1.0
    assert "sleep_fit" in result.metrics
    assert result.tool.startswith("deepeval")
    assert result.warnings


def test_deepeval_sleep_metric_scores_short_sleep_low():
    profile = {"name": "Test User"}
    preferences = {
        "wake_time": "06:00",
        "sleep_time": "11:00",
        "diet_type": "Veg",
        "extra_preferences": {},
    }
    events = [{"time": "06:00", "activity": "Wake up and drink water", "category": "wake"}]

    result = evaluate_day_plan(profile, preferences, events, "")

    assert result.metrics["sleep_fit"] < 0.7
    assert any("sleep" in warning.lower() for warning in result.warnings)


def test_deepeval_sleep_metric_scores_normal_sleep_as_healthy():
    profile = {"name": "Test User"}
    preferences = {
        "wake_time": "07:00",
        "sleep_time": "14:30",
        "diet_type": "Veg",
        "extra_preferences": {},
    }
    events = [{"time": "07:00", "activity": "Wake up and drink water", "category": "wake"}]

    result = evaluate_day_plan(profile, preferences, events, "")

    assert result.metrics["sleep_fit"] == 1.0
    assert any("healthy" in warning.lower() for warning in result.warnings)


def test_deepeval_sleep_metric_flags_long_sleep_after_eight_hours():
    profile = {"name": "Test User"}
    preferences = {
        "wake_time": "06:00",
        "sleep_time": "14:30",
        "diet_type": "Veg",
        "extra_preferences": {},
    }
    events = [{"time": "06:00", "activity": "Wake up and drink water", "category": "wake"}]

    result = evaluate_day_plan(profile, preferences, events, "")

    assert result.metrics["sleep_fit"] < 1.0
    assert any("longer than average" in warning.lower() for warning in result.warnings)
