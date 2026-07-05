import json

try:
    from anthropic import Anthropic
except ImportError:  # pragma: no cover - optional dependency
    Anthropic = None

try:
    from cohere import Client
except ImportError:  # pragma: no cover - optional dependency
    Client = None

from src.config import (
    ENABLE_REMOTE_LLM,
    ANTHROPIC_API_KEY,
    ANTHROPIC_MODEL,
    COHERE_API_KEY,
    COHERE_MODEL,
    LLM_REQUEST_TIMEOUT_SECONDS,
)
from src.llm_utils import extract_json_payload, get_text_from_response


def _normalize_diseases(user_profile: dict):
    raw = user_profile.get("diseases") or []
    if isinstance(raw, str):
        items = [part.strip() for part in raw.split(",")]
    else:
        items = [str(part).strip() for part in raw]
    return {item.lower() for item in items if item and item.lower() != "none"}


def _local_feedback(user_profile: dict, preferences: dict):
    diseases = _normalize_diseases(user_profile)
    notes = []
    meal_rules = []
    health_tip = "Keep meals on time, stay hydrated, and protect your sleep routine."

    if {"sugar", "diabetes"} & diseases:
        meal_rules.extend([
            "Avoid sugary drinks, refined carbohydrates like white bread and maida, trans fats, and heavily processed snacks.",
            "Prefer fiber-rich meals with dal, vegetables, sprouts, curd, nuts, oats, and millets.",
        ])
        notes.append("Balance meals with fiber and protein to avoid blood sugar spikes.")
        health_tip = "For sugar control, choose high-fiber meals, avoid sweet drinks, and walk for 10 minutes after meals."

    if {"bp", "blood pressure"} & diseases:
        meal_rules.append("Keep salt moderate and prefer home-cooked, low-oil meals.")
        notes.append("Use less salt and avoid packaged salty snacks.")

    if "heart" in diseases:
        meal_rules.append("Avoid deep-fried and heavily processed foods; keep meals light and heart-friendly.")
        notes.append("Keep exercise gentle unless a doctor advises otherwise.")

    if user_profile.get("disability"):
        notes.append("Adjust activity intensity based on comfort and mobility.")

    if not notes:
        notes.append("Maintain hydration, regular meals, and consistent sleep routine.")

    return {
        "agent": "Agent 3 - Feedback / Safety",
        "provider": "local",
        "suggestions": notes,
        "meal_rules": meal_rules,
        "health_tip": health_tip,
        "diseases": sorted(diseases),
    }


def fallback_suggestions(user_profile: dict, preferences: dict):
    local_result = _local_feedback(user_profile, preferences)

    if ENABLE_REMOTE_LLM and ANTHROPIC_API_KEY and Anthropic is not None:
        try:
            client = Anthropic(api_key=ANTHROPIC_API_KEY, timeout=LLM_REQUEST_TIMEOUT_SECONDS)
            prompt = f"""
You are Agent 3 - Safety and Feedback Specialist.
Return only valid JSON.

User profile:
{json.dumps(user_profile, indent=2)}

Preferences:
{json.dumps(preferences, indent=2)}

Return a JSON object with:
- suggestions: list of practical safety suggestions
- meal_rules: list of exact meal safety rules
- health_tip: one concise healthy-life tip
- diseases: list of detected diseases
"""

            response = client.messages.create(
                model=ANTHROPIC_MODEL,
                max_tokens=500,
                system="Return only valid JSON.",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
            )
            text = get_text_from_response(response)
            payload = extract_json_payload(text)
            if isinstance(payload, dict):
                payload.setdefault("agent", "Agent 3 - Feedback / Safety")
                payload.setdefault("provider", "anthropic")
                return payload
        except Exception as exc:
            print("Agent 3 Anthropic fallback failed:", exc)

    if ENABLE_REMOTE_LLM and COHERE_API_KEY and Client is not None:
        try:
            client = Client(api_key=COHERE_API_KEY, timeout=LLM_REQUEST_TIMEOUT_SECONDS)
            prompt = f"""
You are Agent 3 - Safety and Feedback Specialist.
Return only valid JSON.

User profile:
{json.dumps(user_profile, indent=2)}

Preferences:
{json.dumps(preferences, indent=2)}

Return a JSON object with:
- suggestions: list of practical safety suggestions
- meal_rules: list of exact meal safety rules
- health_tip: one concise healthy-life tip
- diseases: list of detected diseases
"""

            response = client.chat(
                model=COHERE_MODEL,
                preamble="Return only valid JSON.",
                message=prompt,
                temperature=0.2,
            )
            text = get_text_from_response(response)
            payload = extract_json_payload(text)
            if isinstance(payload, dict):
                payload.setdefault("agent", "Agent 3 - Feedback / Safety")
                payload.setdefault("provider", "cohere")
                return payload
        except Exception as exc:
            print("Agent 3 Cohere fallback failed:", exc)

    return local_result
