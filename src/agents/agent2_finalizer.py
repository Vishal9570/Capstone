import json

try:
    from groq import Groq
except ImportError:  # pragma: no cover - optional dependency
    Groq = None

from src.config import ENABLE_REMOTE_LLM, GROQ_API_KEY, GROQ_MODEL, LLM_MAX_RETRIES, LLM_REQUEST_TIMEOUT_SECONDS
from src.llm_utils import extract_json_payload, get_text_from_response


def _local_finalize(edited_events):
    return edited_events


def finalize_plan_with_agent2(profile, prefs, edited_events):
    """
    Agent 2 finalises user-edited plan.
    It respects user edits and adjusts remaining schedule logically.
    """

    if not ENABLE_REMOTE_LLM or not GROQ_API_KEY or Groq is None:
        return _local_finalize(edited_events)

    try:
        client = Groq(
            api_key=GROQ_API_KEY,
            timeout=LLM_REQUEST_TIMEOUT_SECONDS,
            max_retries=LLM_MAX_RETRIES,
        )
        prompt = f"""
You are Agent 2 - Day Plan Finaliser.
Return only valid JSON.

User profile:
{json.dumps(profile, indent=2)}

User preferences:
{json.dumps(prefs, indent=2)}

User edited plan:
{json.dumps(edited_events, indent=2)}

Rules:
1. Respect the user's manual edits.
2. If user says lunch happened at 2 PM, keep lunch at 14:00.
3. If user says they had rice and dal instead of grilled chicken, update that meal.
4. If user office time is 9 AM to 7 PM, do not schedule gym during office time.
5. Workout should be before office or after office.
6. Do not schedule anything before wake-up time.
7. Sleep must remain near selected sleep time.
8. Keep the plan practical for an Indian working professional.
9. Return only valid JSON array.
10. Use exactly these fields: time, activity, category, duration_minutes, notes.
"""

        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": "Return only valid JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
        )
        text = get_text_from_response(response)
        payload = extract_json_payload(text)
        if isinstance(payload, list):
            return payload
    except Exception as exc:
        print("Agent 2 finalizer failed:", exc)

    return _local_finalize(edited_events)
