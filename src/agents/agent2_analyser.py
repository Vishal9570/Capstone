import json

try:
    from groq import Groq
except ImportError:  # pragma: no cover - optional dependency
    Groq = None

from src.config import ENABLE_REMOTE_LLM, GROQ_API_KEY, GROQ_MODEL, LLM_MAX_RETRIES, LLM_REQUEST_TIMEOUT_SECONDS
from src.llm_utils import extract_json_payload, get_text_from_response
from src.services.history_service import get_history


def _normalize_diseases(value):
    if isinstance(value, str):
        items = [part.strip() for part in value.split(",")]
    else:
        items = [str(part).strip() for part in (value or [])]
    return [item for item in items if item and item.lower() != "none"]


def _build_local_analysis(history):
    latest = history[0]
    meal_patterns = []
    activity_patterns = []

    for item in history[:5]:
        events = item.get("events") or []
        meals = [str(event.get("activity", "")).strip() for event in events if str(event.get("category", "")).lower() == "meal"]
        readings = [str(event.get("activity", "")).strip() for event in events if str(event.get("category", "")).lower() == "reading"]

        if meals:
            meal_patterns.append(f"{item.get('plan_date')}: " + ", ".join(meals[:4]))
        if readings:
            activity_patterns.append(f"{item.get('plan_date')}: " + ", ".join(readings[:2]))

    return {
        "agent": "Agent 2 - Analyser",
        "provider": "local",
        "summary": f"Found {len(history)} previous plan(s).",
        "history_count": len(history),
        "recent_patterns": [
            f"{row.get('plan_date')}: diet={row.get('diet_type')}, fitness={row.get('fitness_type')}, workout={row.get('workout_duration')}"
            for row in history[:5]
        ],
        "meal_patterns": meal_patterns,
        "activity_patterns": activity_patterns,
        "recommendations": [
            f"Previous diet preference was {latest.get('diet_type')}.",
            f"Previous fitness preference was {latest.get('fitness_type')}.",
        ],
        "diseases": _normalize_diseases(latest.get("diseases")),
    }


def analyse_user_history(user_id: int):
    history = get_history(user_id, limit=5)
    if not history:
        return {
            "agent": "Agent 2 - Analyser",
            "provider": "local",
            "summary": "No previous history found. Plan will use signup profile and current preferences.",
            "history_count": 0,
            "recent_patterns": [],
            "meal_patterns": [],
            "activity_patterns": [],
            "recommendations": [],
            "diseases": [],
        }

    local_analysis = _build_local_analysis(history)

    if not ENABLE_REMOTE_LLM:
        return local_analysis

    if not GROQ_API_KEY or Groq is None:
        return local_analysis

    try:
        client = Groq(
            api_key=GROQ_API_KEY,
            timeout=LLM_REQUEST_TIMEOUT_SECONDS,
            max_retries=LLM_MAX_RETRIES,
        )
        prompt = f"""
You are Agent 2 - History Analyser for a day planner.
Return only valid JSON.

Use the user's recent history to produce a concise context object with:
- summary
- history_count
- recent_patterns (list)
- meal_patterns (list)
- activity_patterns (list)
- recommendations (list)
- diseases (list)

Recent plans:
{json.dumps(history, indent=2)}
"""

        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": "Return only valid JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        text = get_text_from_response(response)
        payload = extract_json_payload(text)
        if isinstance(payload, dict):
            payload.setdefault("agent", "Agent 2 - Analyser")
            payload.setdefault("provider", "groq")
            payload.setdefault("history_count", len(history))
            payload.setdefault("diseases", _normalize_diseases(history[0].get("diseases")))
            return payload
    except Exception as exc:
        print("Agent 2 analyser failed. Using local fallback:", exc)

    return local_analysis
