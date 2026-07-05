from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from typing import Any

from src.services.schedule_builder import parse_office_time, to_minutes


DEEP_EVAL_AVAILABLE = importlib.util.find_spec("deepeval") is not None

VEGAN_BANS = {
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
}

VEG_BANS = {"chicken", "egg", "fish", "mutton", "meat"}


@dataclass
class DeepEvalResult:
    tool: str
    overall_score: float
    metrics: dict[str, float]
    warnings: list[str]
    summary: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "tool": self.tool,
            "overall_score": round(self.overall_score, 3),
            "metrics": {key: round(value, 3) for key, value in self.metrics.items()},
            "warnings": self.warnings,
            "summary": self.summary,
        }


def _detect_reading_genre(text: str) -> str:
    lowered = f" {text or ''} ".lower()
    genre_keywords = {
        "science fiction": ["science fiction", "sci-fi", "scifi", "sci fi"],
        "horror": ["horror", "scary", "ghost", "thriller", "spooky", "haunted"],
        "comedy": ["comedy", "funny", "humor", "humour", "comic", "laugh", "satire"],
        "romance": ["romance", "romantic", "love story", "love"],
        "mystery": ["mystery", "detective", "whodunit", "crime", "suspense"],
        "fiction": ["fiction", "fictional", "novel", "fantasy", "adventure", "literary"],
    }
    for genre, keywords in genre_keywords.items():
        if any(keyword in lowered for keyword in keywords):
            return genre
    return ""


def _diet_bans(diet_type: str) -> set[str]:
    diet = str(diet_type or "").strip().lower()
    if diet == "vegan":
        return set(VEGAN_BANS)
    if diet == "veg":
        return set(VEG_BANS)
    return set()


def _event_text(events: list[dict[str, Any]]) -> str:
    return " ".join(
        f"{event.get('time', '')} {event.get('activity', '')} {event.get('category', '')}"
        for event in events or []
    ).lower()


def _office_overlap_score(events: list[dict[str, Any]], office_time: str) -> tuple[float, list[str]]:
    office = parse_office_time(office_time)
    if not office:
        return 1.0, []

    office_start = to_minutes(office["start"])
    office_end = to_minutes(office["end"])
    if office_end <= office_start:
        office_end += 24 * 60

    blocked = 0
    warnings = []
    office_text = str(office_time or "")
    for event in events or []:
        category = str(event.get("category", "")).lower()
        if category not in {"meal", "workout", "reading", "meditation", "break"}:
            continue
        try:
            event_minutes = to_minutes(event.get("time", ""))
        except Exception:
            continue
        comparison_minutes = event_minutes
        if office_end > 24 * 60 and comparison_minutes < office_start:
            comparison_minutes += 24 * 60
        if office_start <= comparison_minutes <= office_end:
            blocked += 1
            warnings.append(f"{event.get('activity')} overlaps office time ({office_text}).")

    total_sensitive = sum(1 for event in events or [] if str(event.get("category", "")).lower() in {"meal", "workout", "reading", "meditation", "break"})
    if total_sensitive == 0:
        return 1.0, warnings
    score = max(0.0, 1.0 - (blocked / total_sensitive))
    return score, warnings


def _diet_score(events: list[dict[str, Any]], diet_type: str) -> tuple[float, list[str]]:
    bans = _diet_bans(diet_type)
    if not bans:
        return 1.0, []

    text = _event_text(events)
    hits = sorted(word for word in bans if word in text)
    if not hits:
        return 1.0, []
    score = max(0.0, 1.0 - min(1.0, len(hits) / max(1, len(bans))))
    return score, [f"Banned diet terms found: {', '.join(hits[:6])}."]


def _workout_fit_score(events: list[dict[str, Any]], workout_timing: str) -> tuple[float, list[str]]:
    timing = str(workout_timing or "").lower()
    workouts = [event for event in events or [] if str(event.get("category", "")).lower() == "workout"]
    if not workouts:
        return 1.0, []

    warnings = []
    first_workout_minutes = to_minutes(workouts[0].get("time", "00:00"))
    if "both morning and evening" in timing or "split" in timing:
        score = 1.0 if len(workouts) >= 2 else 0.5
        if len(workouts) < 2:
            warnings.append("Split workout timing was requested, but only one workout session was scheduled.")
        return score, warnings

    if "morning" in timing and first_workout_minutes >= to_minutes("12:00"):
        warnings.append("Morning workout was scheduled too late.")
        return 0.4, warnings
    if "evening" in timing and first_workout_minutes < to_minutes("12:00"):
        warnings.append("Evening workout was scheduled too early.")
        return 0.4, warnings

    return 1.0, []


def _reading_fit_score(events: list[dict[str, Any]], preferences: dict[str, Any]) -> tuple[float, list[str]]:
    text = " ".join(
        [
            str((preferences or {}).get("notes", "") or ""),
            str((preferences or {}).get("reading_preference", "") or ""),
            _event_text(events),
        ]
    )
    genre = _detect_reading_genre(text)
    if not genre:
        return 1.0, []
    activity = next((str(event.get("activity", "")) for event in events or [] if str(event.get("category", "")).lower() == "reading"), "")
    if genre in activity.lower():
        return 1.0, []
    return 0.75, [f"Reading request suggests {genre}, but the activity title does not clearly match it."]


def _parse_time_to_hours(value: str) -> float | None:
    try:
        hour, minute = str(value or "").split(":")
        return int(hour) + (int(minute) / 60.0)
    except Exception:
        return None


def _sleep_fit_score(preferences: dict[str, Any]) -> tuple[float, list[str]]:
    wake_time = str((preferences or {}).get("wake_time", "") or "")
    sleep_time = str((preferences or {}).get("sleep_time", "") or "")

    wake_hours = _parse_time_to_hours(wake_time)
    sleep_hours = _parse_time_to_hours(sleep_time)
    if wake_hours is None or sleep_hours is None:
        return 0.5, ["Sleep or wake time is missing, so sleep quality could not be fully evaluated."]

    sleep_duration = sleep_hours - wake_hours
    if sleep_duration <= 0:
        sleep_duration += 24

    if sleep_duration < 6:
        return 0.25, [f"Sleep duration looks too short at about {sleep_duration:.1f} hours."]
    if sleep_duration < 7:
        return 0.6, [f"Sleep duration is a bit short at about {sleep_duration:.1f} hours."]
    if sleep_duration <= 8:
        return 1.0, [f"Sleep duration looks healthy at about {sleep_duration:.1f} hours."]

    return 0.7, [f"Sleep duration is longer than average at about {sleep_duration:.1f} hours; keep it consistent."]


def evaluate_day_plan(profile: dict[str, Any], preferences: dict[str, Any], events: list[dict[str, Any]], health_tip: str = "") -> DeepEvalResult:
    office_time = str((preferences or {}).get("extra_preferences", {}).get("office_time", "") or "")
    workout_timing = str((preferences or {}).get("extra_preferences", {}).get("workout_timing", "") or "")
    diet_type = str((preferences or {}).get("diet_type", "") or "")

    office_score, office_warnings = _office_overlap_score(events, office_time)
    diet_score, diet_warnings = _diet_score(events, diet_type)
    workout_score, workout_warnings = _workout_fit_score(events, workout_timing)
    reading_score, reading_warnings = _reading_fit_score(events, (preferences or {}).get("extra_preferences", {}))
    sleep_score, sleep_warnings = _sleep_fit_score(preferences)

    metrics = {
        "office_alignment": office_score,
        "diet_alignment": diet_score,
        "workout_fit": workout_score,
        "reading_fit": reading_score,
        "sleep_fit": sleep_score,
    }
    overall = sum(metrics.values()) / len(metrics)
    warnings = office_warnings + diet_warnings + workout_warnings + reading_warnings + sleep_warnings

    summary = "Plan is well aligned with the selected preferences." if overall >= 0.85 else "Plan needs a few alignment adjustments."
    if health_tip:
        summary = f"{summary} Health tip: {health_tip}"

    tool = "deepeval" if DEEP_EVAL_AVAILABLE else "deepeval-heuristic"
    return DeepEvalResult(tool=tool, overall_score=overall, metrics=metrics, warnings=warnings, summary=summary)
