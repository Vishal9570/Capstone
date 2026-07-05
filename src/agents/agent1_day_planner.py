import json
from typing import Any

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - optional dependency
    OpenAI = None

from src.config import (
    ENABLE_REMOTE_LLM,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    LLM_MAX_RETRIES,
    LLM_REQUEST_TIMEOUT_SECONDS,
)
from src.llm_utils import extract_json_payload, get_text_from_response
from src.services.schedule_builder import awake_window_bounds, build_fixed_schedule, parse_duration_minutes, to_minutes


BOOK_LIBRARY = [
    "Atomic Habits by James Clear",
    "The 7 Habits of Highly Effective People by Stephen Covey",
    "Ikigai by Hector Garcia and Francesc Miralles",
    "Eat That Frog! by Brian Tracy",
    "Why We Sleep by Matthew Walker",
    "Deep Work by Cal Newport",
]

GENRE_BOOK_LIBRARY = {
    "science fiction": [
        "Dune by Frank Herbert",
        "Ender's Game by Orson Scott Card",
        "The Left Hand of Darkness by Ursula K. Le Guin",
    ],
    "fiction": [
        "The Alchemist by Paulo Coelho",
        "The Kite Runner by Khaled Hosseini",
        "1984 by George Orwell",
    ],
    "horror": [
        "Dracula by Bram Stoker",
        "Frankenstein by Mary Shelley",
        "The Haunting of Hill House by Shirley Jackson",
    ],
    "comedy": [
        "Good Omens by Terry Pratchett and Neil Gaiman",
        "Bossypants by Tina Fey",
        "Yes Please by Amy Poehler",
    ],
    "romance": [
        "Pride and Prejudice by Jane Austen",
        "Me Before You by Jojo Moyes",
        "The Notebook by Nicholas Sparks",
    ],
    "mystery": [
        "Gone Girl by Gillian Flynn",
        "The Girl with the Dragon Tattoo by Stieg Larsson",
        "And Then There Were None by Agatha Christie",
    ],
}

GENRE_KEYWORDS = {
    "science fiction": ["science fiction", "sci-fi", "scifi", "sci fi"],
    "horror": ["horror", "scary", "ghost", "ghost story", "thriller", "spooky", "haunted", "dark"],
    "comedy": ["comedy", "funny", "humor", "humour", "comic", "laugh", "light-hearted", "satire"],
    "romance": ["romance", "romantic", "love story", "love"],
    "mystery": ["mystery", "mystery novel", "detective", "whodunit", "crime", "suspense"],
    "fiction": ["fiction", "fictional", "novel", "fantasy", "adventure", "literary"],
}

SUGAR_BAN_LIST = [
    "sugary drinks",
    "sweet drinks",
    "white bread",
    "maida",
    "trans fat",
    "trans fats",
    "processed snacks",
    "refined carbohydrates",
    "deep fried",
]

VEGAN_BAN_LIST = [
    "chicken",
    "egg",
    "fish",
    "mutton",
    "meat",
    "milk",
    "curd",
    "yogurt",
    "paneer",
    "ghee",
    "butter",
    "cheese",
    "cream",
    "buttermilk",
    "whey",
    "honey",
    "omelette",
    "omelet",
]


def _normalize_diseases(profile: dict[str, Any]):
    raw = profile.get("diseases") or []
    if isinstance(raw, str):
        items = [part.strip() for part in raw.split(",")]
    else:
        items = [str(part).strip() for part in raw]
    return {item.lower() for item in items if item and item.lower() != "none"}


def _parse_numeric(value: Any):
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def _parse_time_to_hours(value: str):
    try:
        hour, minute = str(value or "").split(":")
        return int(hour) + int(minute) / 60.0
    except Exception:
        return None


def _build_profile_health_tip(profile: dict[str, Any], prefs: dict[str, Any] | None = None):
    prefs = prefs or {}
    diseases = _normalize_diseases(profile)
    tips = []

    height = _parse_numeric(profile.get("height"))
    weight = _parse_numeric(profile.get("weight"))
    if height and weight:
        height_m = height / 100.0 if height > 3 else height
        if height_m > 0:
            bmi = weight / (height_m * height_m)
            if bmi >= 30:
                tips.append("Your BMI looks high, so focus on lighter portions, more daily walking, and low-oil meals.")
            elif bmi >= 25:
                tips.append("Your BMI suggests you should keep portions moderate and stay consistent with exercise.")
            elif bmi < 18.5:
                tips.append("Your BMI looks low, so add protein-rich, nutrient-dense meals and avoid skipping food.")

    age = _parse_numeric(profile.get("age"))
    if age is not None:
        if age >= 60:
            tips.append("At your age, keep workouts gentle, hydrate well, and keep health checkups regular.")
        elif age >= 40:
            tips.append("With increasing age, consistency in sleep, activity, and routine health checks matters more.")

    wake_hours = _parse_time_to_hours(prefs.get("wake_time"))
    sleep_hours = _parse_time_to_hours(prefs.get("sleep_time"))
    if wake_hours is not None and sleep_hours is not None:
        sleep_duration = sleep_hours - wake_hours
        if sleep_duration <= 0:
            sleep_duration += 24
        if sleep_duration < 7:
            tips.append("Your sleep window is short, so try to sleep earlier and protect at least 7 hours when possible.")
        elif sleep_duration > 8:
            tips.append("Your sleep window is longer than average, so keep it consistent and make sure you still feel rested.")
        else:
            tips.append("Your wake and sleep timings are well balanced, and 7 to 8 hours of sleep is a healthy normal routine.")

    if {"sugar", "diabetes"} & diseases:
        tips.append("For sugar management, keep meals high in fiber, avoid sweet drinks, and stay consistent with sugar checks.")
    elif {"bp", "blood pressure"} & diseases:
        tips.append("For blood pressure, keep salt moderate, avoid packaged snacks, and take relaxed walks after meals.")
    elif "heart" in diseases:
        tips.append("For heart health, prefer light home-cooked meals, healthy fats in moderation, and steady daily activity.")

    if not tips:
        return ""

    unique_tips = list(dict.fromkeys(tips))
    return " ".join(unique_tips[:4]) if len(unique_tips) > 1 else unique_tips[0]


def _contains_any(text: str, words: list[str]) -> bool:
    lowered = (text or "").lower()
    return any(word in lowered for word in words)


def _sort_events_chronologically(events: list[dict[str, Any]], wake_time: str, sleep_time: str):
    wake_minutes, sleep_minutes = awake_window_bounds(wake_time, sleep_time)
    sleep_events = [event for event in events or [] if str(event.get("category", "")).lower() == "sleep"]
    non_sleep_events = [event for event in events or [] if str(event.get("category", "")).lower() != "sleep"]

    def sort_key(item_with_index):
        index, event = item_with_index
        try:
            event_minutes = to_minutes(str(event.get("time", "00:00")))
        except Exception:
            event_minutes = wake_minutes
        if sleep_minutes <= wake_minutes and event_minutes < wake_minutes:
            event_minutes += 24 * 60
        return event_minutes, index

    ordered_events = [event for _, event in sorted(enumerate(non_sleep_events), key=sort_key)]
    ordered_events.extend(sleep_events)
    return ordered_events


def _select_book(profile: dict[str, Any], analysis: dict[str, Any]):
    history_count = int(analysis.get("history_count") or 0)
    disease_count = len(_normalize_diseases(profile))
    index = (history_count + disease_count + len(str(profile.get("name") or ""))) % len(BOOK_LIBRARY)
    return BOOK_LIBRARY[index]


def _detect_reading_genre(text: str):
    lowered = f" {text or ''} ".lower()
    best_genre = ""
    best_index = None
    for genre, keywords in GENRE_KEYWORDS.items():
        for keyword in keywords:
            needle = f" {keyword.lower()} "
            index = lowered.find(needle)
            if index == -1:
                continue
            if best_index is None or index < best_index:
                best_genre = genre
                best_index = index
    return best_genre


def _select_book_for_preferences(profile: dict[str, Any], analysis: dict[str, Any], prefs: dict[str, Any], correction_prompt: str = ""):
    extra_preferences = prefs.get("extra_preferences", {}) if isinstance(prefs, dict) else {}
    reading_text = " ".join(
        [
            str(extra_preferences.get("reading_preference", "") or ""),
            str(extra_preferences.get("notes", "") or ""),
            str(extra_preferences.get("user_change_reason", "") or ""),
            correction_prompt or "",
        ]
    )
    genre = _detect_reading_genre(reading_text)
    if genre and genre in GENRE_BOOK_LIBRARY:
        books = GENRE_BOOK_LIBRARY[genre]
        index = (int(analysis.get("history_count") or 0) + len(str(profile.get("name") or ""))) % len(books)
        return books[index]
    return _select_book(profile, analysis)


def _history_based_health_tip(profile: dict[str, Any], analysis: dict[str, Any]):
    diseases = _normalize_diseases(profile)
    recent_text = " ".join(
        [
            " ".join(analysis.get("recommendations") or []),
            " ".join(analysis.get("meal_patterns") or []),
            " ".join(analysis.get("activity_patterns") or []),
            " ".join(analysis.get("recent_patterns") or []),
        ]
    ).lower()

    if {"sugar", "diabetes"} & diseases:
        if "rice" in recent_text or "sweet" in recent_text:
            return "Your history shows meals that may spike sugar; keep portions smaller, swap refined carbs for millets or brown rice, and follow your doctor's glucose-monitoring advice."
        return "For sugar management, keep meals high in fiber, avoid sweet drinks, and stay consistent with sugar checks and light walks after meals."

    if {"bp", "blood pressure"} & diseases:
        if "salt" in recent_text or "snack" in recent_text:
            return "Your recent plan patterns suggest more salt or snacking; choose low-salt home-cooked meals, hydrate well, and keep your BP checks regular."
        return "For blood pressure, keep salt moderate, avoid packaged snacks, and take relaxed walks after meals."

    if "heart" in diseases:
        if "fried" in recent_text or "oil" in recent_text:
            return "Your history suggests heavy meals; for heart health, keep food light, avoid deep-fried items, and add gentle daily movement."
        return "For heart health, prefer light home-cooked meals, healthy fats in moderation, and steady daily activity."

    if "sleep" in recent_text or "late" in recent_text:
        return "Your history suggests sleep needs attention; finish dinner earlier, reduce screen time before bed, and keep a fixed sleep schedule."

    if "workout" in recent_text or "exercise" in recent_text:
        return "Your recent routine looks active; keep hydration steady and include a short stretch after workouts for recovery."

    if analysis.get("recommendations"):
        return str(analysis["recommendations"][0])

    return "A short evening walk after dinner can improve digestion and sleep quality."


def _health_tip(profile: dict[str, Any], analysis: dict[str, Any], fallback: dict[str, Any], prefs: dict[str, Any] | None = None):
    profile_tip = _build_profile_health_tip(profile, prefs)
    history_tip = _history_based_health_tip(profile, analysis)
    has_history_context = bool(
        analysis.get("history_count")
        or analysis.get("recommendations")
        or analysis.get("meal_patterns")
        or analysis.get("activity_patterns")
        or analysis.get("recent_patterns")
    )
    if profile_tip and history_tip and has_history_context:
        return f"{profile_tip} {history_tip}"
    if profile_tip:
        return profile_tip
    if history_tip:
        return history_tip
    if fallback.get("health_tip"):
        return fallback["health_tip"]
    return "Keep a consistent sleep routine and finish dinner at least 2-3 hours before bedtime."


def _diet_type(profile: dict[str, Any], prefs: dict[str, Any] | None = None):
    source = prefs or {}
    return (source.get("diet_type") or profile.get("diet_type") or "Veg").strip().lower()


def _stable_pick(options: list[str], key: str):
    if not options:
        return ""
    if len(options) == 1:
        return options[0]
    index = sum(ord(char) for char in key) % len(options)
    return options[index]


def _meal_candidates(
    meal_key: str,
    profile: dict[str, Any],
    prefs: dict[str, Any] | None = None,
    analysis: dict[str, Any] | None = None,
    fallback: dict[str, Any] | None = None,
):
    diseases = _normalize_diseases(profile)
    diet_type = _diet_type(profile, prefs)
    analysis = analysis or {}
    fallback = fallback or {}
    notes = json.dumps(prefs or {}).lower()
    context_bits = " ".join(
        [
            str(profile.get("name") or ""),
            diet_type,
            ",".join(sorted(diseases)),
            json.dumps(analysis, sort_keys=True),
            json.dumps(fallback, sort_keys=True),
            notes,
        ]
    ).lower()

    avoid_sweet = {"sugar", "diabetes"} & diseases or "sugar" in context_bits

    if meal_key == "breakfast":
        if {"sugar", "diabetes"} & diseases:
            return [
                "Moong dal chilla with curd and mint chutney",
                "Vegetable oats upma with nuts",
                "Besan chilla with paneer and salad",
            ]
        if diet_type == "vegan":
            return [
                "Vegetable oats upma with peanuts and lemon",
                "Poha with peanuts, curry leaves and lemon",
                "Besan chilla with mint chutney and salad",
            ]
        if diet_type == "veg":
            return [
                "Oats porridge with nuts, curd and fruit",
                "Besan chilla with mint chutney and curd",
                "Vegetable poha with peanuts and lemon",
            ]
        return [
            "Egg bhurji with whole wheat toast and fruit",
            "Vegetable omelette with oats and curd",
            "Boiled eggs with millet toast and salad",
        ]

    if meal_key == "lunch":
        if {"sugar", "diabetes"} & diseases:
            return [
                "Dal, mixed vegetables, salad and millet roti",
                "Rajma with brown rice and cucumber salad",
                "Paneer sabzi with brown rice and salad",
            ]
        if diet_type == "vegan":
            return [
                "Dal, brown rice, sabzi and salad",
                "Chole with roti and cucumber salad",
                "Rajma with millet roti and vegetables",
            ]
        if diet_type == "veg":
            return [
                "Dal, brown rice, sabzi and salad",
                "Chole with roti and cucumber salad",
                "Paneer curry with millet roti and vegetables",
            ]
        return [
            "Grilled chicken with brown rice and salad",
            "Egg curry with roti and vegetables",
            "Chicken curry with millet roti and cucumber salad",
        ]

    if meal_key == "tea":
        if {"sugar", "diabetes"} & diseases or avoid_sweet:
            return [
                "Unsweetened buttermilk with roasted chana",
                "Coconut water with nuts",
                "Sprouts chaat with lemon",
            ]
        if diet_type == "vegan":
            return [
                "Coconut water with roasted chana",
                "Fruit bowl with seeds and nuts",
                "Sprouts chaat with lemon",
            ]
        if diet_type == "veg":
            return [
                "Buttermilk with roasted chana",
                "Fruit bowl with seeds and nuts",
                "Sprouts chaat with lemon",
            ]
        return [
            "Boiled eggs with buttermilk",
            "Greek yogurt with nuts",
            "Fruit bowl with peanuts",
        ]

    if meal_key == "dinner":
        if {"sugar", "diabetes"} & diseases:
            return [
                "Vegetable soup with tofu salad",
                "Light moong dal khichdi with curd",
                "Paneer and vegetable bowl with millet roti",
            ]
        if diet_type == "vegan":
            return [
                "Vegetable soup with tofu salad",
                "Light moong dal khichdi with pickle",
                "Tofu and vegetable bowl with millet roti",
            ]
        if diet_type == "veg":
            return [
                "Paneer salad with quinoa",
                "Light khichdi with curd",
                "Tofu vegetable bowl with millet roti",
            ]
        return [
            "Steamed chicken with salad",
            "Chicken soup with vegetables",
            "Grilled chicken with quinoa salad",
        ]

    return ["Light, balanced meal"]


def _safe_pick(pool: list[str], fallback: str):
    return _stable_pick(pool, fallback)


def _sanitize_meal(text: str, profile: dict[str, Any], diet_type: str | None = None):
    text = (text or "").strip()
    if not text:
        return None

    diseases = _normalize_diseases(profile)
    diet_type = (diet_type or profile.get("diet_type") or "Veg").strip().lower()

    if diet_type in {"veg", "vegan"} and _contains_any(text, ["chicken", "egg", "fish", "mutton", "meat"]):
        return None
    if diet_type == "vegan" and _contains_any(text, VEGAN_BAN_LIST):
        return None

    if {"sugar", "diabetes"} & diseases:
        if _contains_any(text, SUGAR_BAN_LIST):
            return None

    return text


def _local_meals(profile: dict[str, Any], prefs: dict[str, Any], analysis: dict[str, Any], fallback: dict[str, Any]):
    diet_type = _diet_type(profile, prefs)
    context_key = json.dumps(
        {
            "name": profile.get("name"),
            "diet_type": diet_type,
            "diseases": sorted(_normalize_diseases(profile)),
            "analysis": analysis.get("history_count", 0),
            "fallback": fallback.get("health_tip", ""),
        },
        sort_keys=True,
    )

    sugar_safe_marker = "avoid sweet drinks, refined carbs, trans fats, and heavily processed snacks"
    if {"sugar", "diabetes"} & _normalize_diseases(profile):
        sugar_tip = sugar_safe_marker
    else:
        sugar_tip = "balanced with protein, fiber, and healthy fats"

    return {
        "breakfast": _stable_pick(
            _meal_candidates("breakfast", profile, prefs, analysis, fallback),
            context_key + ":breakfast",
        ),
        "lunch": _stable_pick(
            _meal_candidates("lunch", profile, prefs, analysis, fallback),
            context_key + ":lunch",
        ),
        "tea": _stable_pick(
            _meal_candidates("tea", profile, prefs, analysis, fallback),
            context_key + ":tea",
        ),
        "dinner": _stable_pick(
            _meal_candidates("dinner", profile, prefs, analysis, fallback),
            context_key + ":dinner",
        ),
        "meal_note": sugar_tip,
    }


def _compact_context_items(values: Any, limit: int = 4):
    if isinstance(values, dict):
        items = []
        for key, value in values.items():
            if isinstance(value, (list, tuple, set)):
                text = ", ".join(str(item) for item in list(value)[:limit] if item)
            else:
                text = str(value)
            if text:
                items.append(f"{key}: {text}")
        return items[:limit]

    if isinstance(values, (list, tuple, set)):
        return [str(item) for item in list(values)[:limit] if str(item)]

    if values:
        return [str(values)]
    return []


def _build_prompt(profile, prefs, schedule, analysis, fallback, correction_prompt=""):
    extra_preferences = prefs.get("extra_preferences", {}) if isinstance(prefs, dict) else {}
    analysis_summary = {
        "summary": analysis.get("summary", ""),
        "history_count": analysis.get("history_count", 0),
        "recent_patterns": _compact_context_items(analysis.get("recent_patterns")),
        "meal_patterns": _compact_context_items(analysis.get("meal_patterns")),
        "activity_patterns": _compact_context_items(analysis.get("activity_patterns")),
        "recommendations": _compact_context_items(analysis.get("recommendations")),
        "diseases": _compact_context_items(analysis.get("diseases")),
    }
    safety_summary = {
        "provider": fallback.get("provider", "local"),
        "diseases": _compact_context_items(fallback.get("diseases")),
        "suggestions": _compact_context_items(fallback.get("suggestions")),
        "meal_rules": _compact_context_items(fallback.get("meal_rules")),
        "health_tip": fallback.get("health_tip", ""),
    }
    preference_summary = {
        "diet_type": prefs.get("diet_type"),
        "fitness_type": prefs.get("fitness_type"),
        "workout_duration": prefs.get("workout_duration"),
        "workout_timing": extra_preferences.get("workout_timing") or extra_preferences.get("gym_preference"),
        "notes": extra_preferences.get("notes", ""),
        "extra_preferences": {k: v for k, v in extra_preferences.items() if v not in ("", None)},
    }

    return f"""
You are Agent 1 - Day Planner.
Return only valid JSON.

User profile:
{json.dumps(profile, indent=2)}

User preferences:
{json.dumps(preference_summary, indent=2)}

Agent 2 history context:
{json.dumps(analysis_summary, indent=2)}

Agent 3 safety context:
{json.dumps(safety_summary, indent=2)}

Today's fixed schedule:
{json.dumps(schedule, indent=2)}

Correction instructions:
{correction_prompt}

Planning priorities:
1. Use Agent 2's history signals to avoid repeating weak patterns and to align with what worked before.
2. Use Agent 3's safety rules to keep every meal disease-aware and medically safer.
3. Give extra preference fields strong weight, especially office timing, sleep timing, workout timing, and user notes.
4. If there is any conflict, disease safety overrides preferences.
5. Make meal choices practical, Indian, and easy to follow for the user's routine.

Rules:
1. Respect user preferences first.
2. If the user has any disease, disease-safe choices win over general preferences.
3. For sugar or diabetes, do not suggest sugary drinks, refined carbohydrates like white bread and maida, trans fats, or heavily processed snacks.
4. Use Indian meals.
5. Include one reading activity with a specific book title.
6. Include one concise healthy-life tip in the returned JSON.
7. Return JSON with exactly: breakfast, lunch, tea, dinner, reading_book, health_tip.
"""


def _parse_llm_meals(text: str, profile: dict[str, Any], diet_type: str | None = None):
    payload = extract_json_payload(text)
    if not isinstance(payload, dict):
        raise ValueError("Meal payload was not a JSON object")

    return {
        "breakfast": _sanitize_meal(payload.get("breakfast", ""), profile, diet_type)
        or _stable_pick(_meal_candidates("breakfast", profile, {"diet_type": diet_type}), "breakfast"),
        "lunch": _sanitize_meal(payload.get("lunch", ""), profile, diet_type)
        or _stable_pick(_meal_candidates("lunch", profile, {"diet_type": diet_type}), "lunch"),
        "tea": _sanitize_meal(payload.get("tea", ""), profile, diet_type)
        or _stable_pick(_meal_candidates("tea", profile, {"diet_type": diet_type}), "tea"),
        "dinner": _sanitize_meal(payload.get("dinner", ""), profile, diet_type)
        or _stable_pick(_meal_candidates("dinner", profile, {"diet_type": diet_type}), "dinner"),
        "reading_book": payload.get("reading_book") or "",
        "health_tip": payload.get("health_tip") or "",
    }


def _generate_with_openai(profile, prefs, schedule, analysis, fallback, correction_prompt=""):
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not configured")
    if OpenAI is None:
        raise RuntimeError("openai package is not installed")

    client = OpenAI(
        api_key=OPENAI_API_KEY,
        timeout=LLM_REQUEST_TIMEOUT_SECONDS,
        max_retries=LLM_MAX_RETRIES,
    )
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": "Return only valid JSON."},
            {"role": "user", "content": _build_prompt(profile, prefs, schedule, analysis, fallback, correction_prompt)},
        ],
        temperature=0.2,
    )
    text = get_text_from_response(response)
    return _parse_llm_meals(text, profile, prefs.get("diet_type"))


def _generate_with_gemini(profile, prefs, schedule, analysis, fallback, correction_prompt=""):
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not configured")

    import google.generativeai as genai

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(GEMINI_MODEL)
    response = model.generate_content(
        _build_prompt(profile, prefs, schedule, analysis, fallback, correction_prompt),
        request_options={"timeout": LLM_REQUEST_TIMEOUT_SECONDS},
    )
    text = getattr(response, "text", "") or get_text_from_response(response)
    return _parse_llm_meals(text, profile, prefs.get("diet_type"))


def generate_meals_with_agent1(profile, prefs, schedule, analysis=None, fallback=None, correction_prompt=""):
    analysis = analysis or {}
    fallback = fallback or {}
    if not ENABLE_REMOTE_LLM:
        return _local_meals(profile, prefs, analysis, fallback)
    try:
        if OPENAI_API_KEY:
            return _generate_with_openai(profile, prefs, schedule, analysis, fallback, correction_prompt)
    except Exception as exc:
        print("Agent 1 OpenAI path failed. Falling back to Gemini/local:", exc)

    try:
        if GEMINI_API_KEY:
            return _generate_with_gemini(profile, prefs, schedule, analysis, fallback, correction_prompt)
    except Exception as exc:
        print("Agent 1 Gemini path failed. Using local fallback:", exc)

    return _local_meals(profile, prefs, analysis, fallback)


def generate_day_plan_with_gpt(
    profile,
    prefs,
    analysis,
    fallback,
    correction_prompt: str = "",
    return_metadata: bool = False,
):
    wake_time = prefs["wake_time"]
    sleep_time = prefs["sleep_time"]
    fitness_type = prefs["fitness_type"]
    workout_duration = prefs["workout_duration"]
    office_start = prefs.get("extra_preferences", {}).get("office_start")
    office_end = prefs.get("extra_preferences", {}).get("office_end")
    office_time = prefs.get("extra_preferences", {}).get("office_time", "")
    if not office_time and office_start and office_end:
        office_time = f"{office_start} to {office_end}"

    schedule = build_fixed_schedule(
        wake_time=wake_time,
        sleep_time=sleep_time,
        fitness_type=fitness_type,
        workout_duration=workout_duration,
        office_time=office_time,
        workout_timing=prefs.get("extra_preferences", {}).get("workout_timing")
        or prefs.get("extra_preferences", {}).get("gym_preference", ""),
        planning_notes=" ".join(
            str(prefs.get("extra_preferences", {}).get(key, "") or "")
            for key in ("notes", "user_change_reason", "reading_preference")
        ),
    )

    meals = generate_meals_with_agent1(
        profile,
        prefs,
        schedule,
        analysis=analysis,
        fallback=fallback,
        correction_prompt=correction_prompt,
    )

    book_title = _select_book_for_preferences(profile, analysis, prefs, correction_prompt)
    health_tip = _health_tip(profile, analysis, fallback, prefs)

    if not meals.get("reading_book"):
        meals["reading_book"] = book_title
    elif _detect_reading_genre(
        " ".join(
            [
                str(prefs.get("extra_preferences", {}).get("reading_preference", "") or ""),
                str(prefs.get("extra_preferences", {}).get("notes", "") or ""),
                str(prefs.get("extra_preferences", {}).get("user_change_reason", "") or ""),
                correction_prompt or "",
            ]
        )
    ):
        meals["reading_book"] = book_title
    if not meals.get("health_tip"):
        meals["health_tip"] = health_tip

    diseases = _normalize_diseases(profile)
    tea_notes = "Sugar-safe afternoon snack." if {"sugar", "diabetes"} & diseases else "Light snack or hydration break."

    workout_sessions = schedule.get("workout_sessions") or [
        {
            "time": schedule["workout"],
            "duration_minutes": parse_duration_minutes(workout_duration, default=60),
            "label": schedule["workout_label"],
        }
    ]
    workout_events = []
    for session in workout_sessions:
        session_duration = int(session.get("duration_minutes") or parse_duration_minutes(workout_duration, default=60))
        session_time = session.get("time") or schedule["workout"]
        session_label = session.get("label") or schedule["workout_label"]
        workout_events.append(
            {
                "time": session_time,
                "activity": f"{session_label} for {workout_duration}",
                "category": "workout",
                "duration_minutes": session_duration,
                "notes": f"Workout is planned according to the user's timing preference ({schedule['workout_timing']}).",
                "remark": "",
            }
        )

    events = [
        {
            "time": schedule["wake"],
            "activity": "Wake up and drink water",
            "category": "wake",
            "duration_minutes": 15,
            "notes": "Start your day with hydration.",
            "remark": "",
        },
        {
            "time": schedule["breakfast"],
            "activity": meals["breakfast"],
            "category": "meal",
            "duration_minutes": 30,
            "notes": "Breakfast is planned to start the day with balanced energy.",
            "remark": "",
        },
        {
            "time": schedule["lunch"],
            "activity": meals["lunch"],
            "category": "meal",
            "duration_minutes": 45,
            "notes": "Lunch should stay balanced and aligned with the user's health context.",
            "remark": "",
        },
        {
            "time": schedule["tea"],
            "activity": meals["tea"],
            "category": "break",
            "duration_minutes": 20,
            "notes": tea_notes,
            "remark": "",
        },
        *workout_events,
        {
            "time": schedule["dinner"],
            "activity": meals["dinner"],
            "category": "meal",
            "duration_minutes": 40,
            "notes": "Keep dinner light and easy to digest.",
            "remark": "",
        },
        {
            "time": schedule["reading"],
            "activity": f"Book reading: {book_title}",
            "category": "reading",
            "duration_minutes": 30,
            "notes": f"Read 10-20 pages from {book_title} after dinner.",
            "remark": "",
        },
        {
            "time": schedule["meditation"],
            "activity": "Meditation",
            "category": "meditation",
            "duration_minutes": 15,
            "notes": "Short relaxation before sleep.",
            "remark": "",
        },
        {
            "time": schedule["sleep"],
            "activity": "Sleep",
            "category": "sleep",
            "duration_minutes": 480,
            "notes": "Maintain consistent sleep routine.",
            "remark": "",
        },
    ]

    events = _sort_events_chronologically(events, schedule["wake"], schedule["sleep"])

    if return_metadata:
        return {
            "events": events,
            "health_tip": health_tip,
        }

    return events
