from src.agents import agent1_day_planner as planner


def test_generate_day_plan_without_llm_uses_disease_safe_meals():
    planner.OPENAI_API_KEY = ""
    planner.GEMINI_API_KEY = ""

    profile = {
        "name": "Test User",
        "diseases": ["Sugar"],
        "diet_type": "Veg",
    }
    prefs = {
        "wake_time": "08:00",
        "sleep_time": "00:00",
        "diet_type": "Veg",
        "fitness_type": "Yoga",
        "workout_duration": "1 hr",
        "extra_preferences": {"office_start": "09:00", "office_end": "18:00"},
    }
    analysis = {"history_count": 2, "recommendations": ["keep meals light"]}
    fallback = {"health_tip": "Keep dinner light."}

    result = planner.generate_day_plan_with_gpt(
        profile,
        prefs,
        analysis,
        fallback,
        return_metadata=True,
    )

    activities = [event["activity"].lower() for event in result["events"]]

    assert result["health_tip"]
    assert any(event["category"] == "reading" and event["activity"].startswith("Book reading:") for event in result["events"])
    assert any(event["category"] == "sleep" and event["time"] == "00:00" for event in result["events"])
    assert not any("sugary drinks" in activity for activity in activities)
    assert not any("white bread" in activity for activity in activities)
    assert not any("maida" in activity for activity in activities)
    assert not any("trans fat" in activity for activity in activities)


def test_generate_day_plan_non_veg_includes_non_veg_options():
    planner.OPENAI_API_KEY = ""
    planner.GEMINI_API_KEY = ""

    profile = {
        "name": "Test User",
        "diseases": [],
        "diet_type": "Non-Veg",
    }
    prefs = {
        "wake_time": "07:00",
        "sleep_time": "22:00",
        "diet_type": "Non-Veg",
        "fitness_type": "Gym",
        "workout_duration": "1 hr",
        "extra_preferences": {},
    }

    result = planner.generate_day_plan_with_gpt(profile, prefs, {}, {}, return_metadata=True)
    meal_text = " ".join(event["activity"].lower() for event in result["events"] if event["category"] == "meal")

    assert any(word in meal_text for word in ["egg", "chicken"])


def test_generated_events_include_remark_column():
    planner.OPENAI_API_KEY = ""
    planner.GEMINI_API_KEY = ""

    profile = {
        "name": "Test User",
        "diseases": [],
        "diet_type": "Veg",
    }
    prefs = {
        "wake_time": "07:00",
        "sleep_time": "22:00",
        "diet_type": "Veg",
        "fitness_type": "Yoga",
        "workout_duration": "1 hr",
        "extra_preferences": {"gym_preference": "Morning"},
    }

    result = planner.generate_day_plan_with_gpt(profile, prefs, {}, {}, return_metadata=True)
    assert all("remark" in event for event in result["events"])


def test_health_tip_changes_with_history_context():
    planner.OPENAI_API_KEY = ""
    planner.GEMINI_API_KEY = ""

    profile = {
        "name": "Test User",
        "diseases": ["Sugar"],
        "diet_type": "Veg",
    }
    prefs = {
        "wake_time": "08:00",
        "sleep_time": "22:00",
        "diet_type": "Veg",
        "fitness_type": "Yoga",
        "workout_duration": "1 hr",
        "extra_preferences": {},
    }

    result_a = planner.generate_day_plan_with_gpt(
        profile,
        prefs,
        {"history_count": 0, "recommendations": [], "meal_patterns": [], "activity_patterns": [], "recent_patterns": []},
        {},
        return_metadata=True,
    )
    result_b = planner.generate_day_plan_with_gpt(
        profile,
        prefs,
        {
            "history_count": 3,
            "recommendations": ["Keep sugar lower", "Earlier dinner"],
            "meal_patterns": ["2026-07-01: rice, sweet tea"],
            "activity_patterns": ["2026-07-01: evening walk"],
            "recent_patterns": ["late snacks, rice-heavy dinner"],
        },
        {},
        return_metadata=True,
    )

    assert result_a["health_tip"] != result_b["health_tip"]
    assert "sugar" in result_b["health_tip"].lower() or "rice" in result_b["health_tip"].lower()
