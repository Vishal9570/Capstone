import json

try:
    from groq import Groq
except ImportError:  # pragma: no cover - optional dependency
    Groq = None

from src.config import ENABLE_REMOTE_LLM, GROQ_API_KEY, GROQ_MODEL, LLM_MAX_RETRIES, LLM_REQUEST_TIMEOUT_SECONDS
from src.llm_utils import extract_json_payload, get_text_from_response


def verify_plan_with_agent2(profile: dict, prefs: dict, events: list) -> dict:
    """
    Agent 2 verifies whether Agent 1 followed user preferences.
    """

    if not ENABLE_REMOTE_LLM or not GROQ_API_KEY or Groq is None:
        return basic_verify(prefs, events)

    try:
        client = Groq(
            api_key=GROQ_API_KEY,
            timeout=LLM_REQUEST_TIMEOUT_SECONDS,
            max_retries=LLM_MAX_RETRIES,
        )
        prompt = f"""
You are Agent 2 - Preference and Constraint Verifier.
Return only valid JSON.

User profile:
{json.dumps(profile, indent=2)}

User preferences:
{json.dumps(prefs, indent=2)}

Generated day plan:
{json.dumps(events, indent=2)}

Check these strictly:
1. No activity should be scheduled before wake_time.
2. Breakfast must be after wake_time.
3. Sleep activity should be close to sleep_time.
4. Diet preference must be respected.
5. Extra preferences must be respected.
6. Fitness preference and workout duration must be respected.
7. Do not judge medically. Only verify schedule and preference alignment.

Return valid JSON only in this format:
{{
  "is_valid": true,
  "errors": [],
  "correction_prompt": ""
}}

If invalid:
{{
  "is_valid": false,
  "errors": ["..."],
  "correction_prompt": "Regenerate the plan and fix these issues: ..."
}}
"""

        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": "You are a strict JSON-only verifier."},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
        text = get_text_from_response(response)
        payload = extract_json_payload(text)
        if isinstance(payload, dict):
            return payload
    except Exception as exc:
        print("Agent 2 verifier failed. Using basic fallback:", exc)

    return basic_verify(prefs, events)


def basic_verify(prefs: dict, events: list) -> dict:
    errors = []

    wake_time = prefs.get("wake_time", "06:00")
    diet_type = prefs.get("diet_type", "")
    notes = str(prefs.get("extra_preferences", {}).get("notes", "")).lower()

    def to_minutes(t):
        h, m = t.split(":")
        return int(h) * 60 + int(m)

    wake_mins = to_minutes(wake_time)
    diet_label = str(diet_type or "").strip().lower()
    banned_words = []
    if diet_label == "vegan":
        banned_words = [
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
    elif diet_label == "veg":
        banned_words = ["chicken", "egg", "fish", "mutton", "meat"]

    for event in events:
        event_time = event.get("time", "")
        activity = str(event.get("activity", "")).lower()
        category = str(event.get("category", "")).lower()

        try:
            event_mins = to_minutes(event_time)
        except Exception:
            errors.append(f"Invalid time format: {event_time}")
            continue

        if category != "sleep" and event_mins < wake_mins:
            errors.append(f"{event.get('activity')} is before wake time {wake_time}")

        for word in banned_words:
            if word in activity:
                label = "Vegan" if diet_label == "vegan" else "Veg"
                errors.append(f"{label} item found in {label} plan: {event.get('activity')}")

        if "avoid rice" in notes and "rice" in activity:
            errors.append(f"Rice found despite user preference: {event.get('activity')}")

    correction_prompt = ""
    if errors:
        correction_prompt = "Regenerate the plan and fix these issues: " + "; ".join(errors)

    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
        "correction_prompt": correction_prompt,
    }
