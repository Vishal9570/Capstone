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


def test_generate_day_plan_vegan_uses_vegan_meals():
    planner.OPENAI_API_KEY = ""
    planner.GEMINI_API_KEY = ""

    profile = {
        "name": "Test User",
        "diseases": [],
        "diet_type": "Vegan",
    }
    prefs = {
        "wake_time": "07:00",
        "sleep_time": "22:00",
        "diet_type": "Vegan",
        "fitness_type": "Yoga",
        "workout_duration": "1 hr",
        "extra_preferences": {},
    }

    result = planner.generate_day_plan_with_gpt(profile, prefs, {}, {}, return_metadata=True)
    meal_text = " ".join(event["activity"].lower() for event in result["events"] if event["category"] == "meal")

    assert not any(word in meal_text for word in ["egg", "chicken", "fish", "mutton", "meat"])
    assert not any(word in meal_text for word in ["curd", "yogurt", "paneer", "milk", "butter", "ghee", "cheese", "buttermilk", "honey"])
    assert any(word in meal_text for word in ["poha", "dal", "rajma", "chole", "tofu", "oats"])


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


def test_health_tip_uses_profile_and_sleep_context():
    planner.OPENAI_API_KEY = ""
    planner.GEMINI_API_KEY = ""

    profile = {
        "name": "Test User",
        "height": 170,
        "weight": 90,
        "age": 62,
        "diseases": ["Sugar"],
        "diet_type": "Veg",
    }
    prefs = {
        "wake_time": "07:00",
        "sleep_time": "12:30",
        "diet_type": "Veg",
        "fitness_type": "Yoga",
        "workout_duration": "1 hr",
        "extra_preferences": {},
    }

    result = planner.generate_day_plan_with_gpt(profile, prefs, {}, {}, return_metadata=True)
    tip = result["health_tip"].lower()

    assert "bmi" in tip or "weight" in tip or "portion" in tip
    assert "sleep" in tip or "7 hours" in tip
    assert "sugar" in tip


def test_reading_remark_prefers_requested_genre():
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
        "extra_preferences": {
            "notes": "Please suggest horror books for reading.",
        },
    }

    result = planner.generate_day_plan_with_gpt(profile, prefs, {}, {}, return_metadata=True)
    reading_activity = next(event["activity"] for event in result["events"] if event["category"] == "reading")

    assert any(book in reading_activity for book in [
        "Dracula by Bram Stoker",
        "Frankenstein by Mary Shelley",
        "The Haunting of Hill House by Shirley Jackson",
    ])


def test_reading_remark_prefers_comedy_genre():
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
        "extra_preferences": {
            "notes": "Please suggest a comedy book for reading.",
        },
    }

    result = planner.generate_day_plan_with_gpt(profile, prefs, {}, {}, return_metadata=True)
    reading_activity = next(event["activity"] for event in result["events"] if event["category"] == "reading")

    assert any(book in reading_activity for book in [
        "Good Omens by Terry Pratchett and Neil Gaiman",
        "Bossypants by Tina Fey",
        "Yes Please by Amy Poehler",
    ])
