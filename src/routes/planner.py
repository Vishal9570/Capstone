from fastapi import APIRouter, HTTPException
from datetime import date
from src.models import DayPlanRequest, FeedbackRequest, UpdatePlanRequest
from src.services.auth_service import get_user_by_id
from src.agents.agent2_analyser import analyse_user_history
from src.agents.agent3_feedback import fallback_suggestions
from src.agents.agent1_day_planner import generate_day_plan_with_gpt
from src.agents.agent4_notification import schedule_day_plan
from src.services.history_service import save_plan, get_history, save_feedback
from src.services.notification_service import schedule_optional_sms
from src.agents.agent2_preference_verifier import verify_plan_with_agent2
from src.models import FinalizePlanRequest
from src.agents.agent2_finalizer import finalize_plan_with_agent2
from src.agents.agent3_validator import validate_final_plan
from src.observability import record_plan_event, track_agent_latency
from src.services.schedule_builder import (
    parse_office_time,
    validate_awake_office_alignment,
    awake_window_bounds,
    to_minutes,
)
router = APIRouter(tags=["Planner"])


def _extract_remarks(events):
    remarks = []
    for idx, event in enumerate(events or [], start=1):
        remark = str(event.get("remark", "") or "").strip()
        if remark:
            remarks.append(
                f"Row {idx} ({event.get('category', 'unknown')} at {event.get('time', 'unknown')}): {remark}"
            )
    return remarks


def _build_correction_prompt(events, extra_preferences=None, user_change_reason=""):
    remarks = _extract_remarks(events)
    pieces = []
    if user_change_reason:
        pieces.append(f"User change reason: {user_change_reason}")
    if extra_preferences:
        pieces.append(f"Extra preferences: {extra_preferences}")
    if remarks:
        pieces.append("User remarks:")
        pieces.extend(f"- {item}" for item in remarks)

    if not pieces:
        return ""

    return (
        "Regenerate the day plan and apply these updates precisely.\n"
        "If a meal is skipped, replace it with a suitable light alternative or hydration break.\n"
        "If workout time should move, place it at the requested timing while keeping the rest of the plan consistent.\n"
        + "\n".join(pieces)
    )


def _detect_reading_genre(text: str):
    lowered = f" {text or ''} ".lower()
    genre_keywords = {
        "science fiction": ["science fiction", "sci-fi", "scifi", "sci fi"],
        "horror": ["horror", "scary", "ghost", "ghost story", "thriller", "spooky", "haunted", "dark"],
        "comedy": ["comedy", "funny", "humor", "humour", "comic", "laugh", "light-hearted", "satire"],
        "romance": ["romance", "romantic", "love story", "love"],
        "mystery": ["mystery", "mystery novel", "detective", "whodunit", "crime", "suspense"],
        "fiction": ["fiction", "fictional", "novel", "fantasy", "adventure", "literary"],
    }
    best_genre = ""
    best_index = None
    for genre, keywords in genre_keywords.items():
        for keyword in keywords:
            index = lowered.find(f" {keyword.lower()} ")
            if index == -1:
                continue
            if best_index is None or index < best_index:
                best_genre = genre
                best_index = index
    return best_genre


def _reading_preference_from_events(events, extra_preferences=None, user_change_reason=""):
    pieces = []
    for event in events or []:
        if str(event.get("category", "")).lower() == "reading":
            pieces.append(str(event.get("remark", "") or ""))
            pieces.append(str(event.get("activity", "") or ""))
    if extra_preferences:
        pieces.append(str(extra_preferences.get("notes", "") or ""))
        pieces.append(str(extra_preferences.get("reading_preference", "") or ""))
    if user_change_reason:
        pieces.append(user_change_reason)

    detected = _detect_reading_genre(" ".join(pieces))
    return detected


def _diet_bans(diet_type: str):
    diet = str(diet_type or "").strip().lower()
    if diet == "vegan":
        return [
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
    if diet == "veg":
        return ["chicken", "egg", "fish", "mutton", "meat"]
    return []


def _time_to_minutes(time_text: str):
    try:
        hour, minute = str(time_text or "").split(":")
        return int(hour) * 60 + int(minute)
    except Exception:
        return None


def _office_bounds_minutes(office_time: str):
    office = parse_office_time(office_time)
    if not office:
        return None, None
    office_start = to_minutes(office["start"])
    office_end = to_minutes(office["end"])
    if office_end <= office_start:
        office_end += 24 * 60
    return office_start, office_end


def _shift_event_outside_office(event, office_start: int, office_end: int, wake_minutes: int, sleep_minutes: int):
    duration = int(event.get("duration_minutes") or 30)
    event_minutes = _time_to_minutes(event.get("time", ""))
    if event_minutes is None:
        return event, False

    before_candidate = max(wake_minutes, office_start - duration - 15)
    after_candidate = min(max(office_end + 30, office_start + 30), sleep_minutes - duration)

    before_ok = before_candidate + duration <= office_start
    after_ok = after_candidate + duration <= sleep_minutes

    if before_ok:
        shifted = dict(event)
        shifted["time"] = f"{before_candidate // 60:02d}:{before_candidate % 60:02d}"
        return shifted, True
    if after_ok:
        shifted = dict(event)
        shifted["time"] = f"{after_candidate // 60:02d}:{after_candidate % 60:02d}"
        return shifted, True

    return event, False


def _skip_office_overlaps(events, office_time: str, wake_time: str, sleep_time: str, workout_timing: str = ""):
    office_start, office_end = _office_bounds_minutes(office_time)
    if office_start is None or office_end is None:
        return events, []

    wake_minutes, sleep_minutes = awake_window_bounds(wake_time, sleep_time)
    kept_events = []
    skipped_labels = []
    shifted_labels = []

    for event in events or []:
        category = str(event.get("category", "")).lower()
        event_minutes = _time_to_minutes(event.get("time", ""))
        if event_minutes is None:
            kept_events.append(event)
            continue

        comparison_minutes = event_minutes
        if office_end > 24 * 60 and comparison_minutes < office_start:
            comparison_minutes += 24 * 60

        if category == "workout" and office_start <= comparison_minutes <= office_end:
            skipped_labels.append(f"{event.get('activity')} at {event.get('time')}")
            continue

        kept_events.append(event)

    if not skipped_labels and not shifted_labels:
        return kept_events, []

    message = "Your workout was adjusted to fit your work hours."
    return kept_events, [message]


@router.post("/planner/generate")
def generate_plan(req: DayPlanRequest):
    user = get_user_by_id(req.user_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    profile = {
        "name": user["name"],
        "email": user["email"],
        "phone": user["phone"],
        "height": user["height"],
        "weight": user["weight"],
        "gender": user["gender"],
        "age": user["age"],
        "profession": user["profession"],
        "diseases": user["diseases"],
        "disability": user["disability"],
    }

    prefs = {
        "wake_time": req.wake_time,
        "sleep_time": req.sleep_time,
        "diet_type": req.diet_type,
        "fitness_type": req.fitness_type,
        "workout_duration": req.workout_duration,
        "extra_preferences": req.preferences or {},
    }
    prefs["extra_preferences"].setdefault("workout_timing", prefs["extra_preferences"].get("gym_preference", "Flexible"))
    reading_preference = _reading_preference_from_events([], prefs["extra_preferences"], "")
    if reading_preference:
        prefs["extra_preferences"]["reading_preference"] = reading_preference

    office_time = prefs["extra_preferences"].get("office_time", "")
    if not office_time:
        office_start = prefs["extra_preferences"].get("office_start")
        office_end = prefs["extra_preferences"].get("office_end")
        if office_start and office_end:
            office_time = f"{office_start} to {office_end}"

    office_errors = validate_awake_office_alignment(req.wake_time, req.sleep_time, office_time)
    if office_errors:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Office timing must fall within the user's awake window.",
                "errors": office_errors,
            },
        )

    # Agent 2: history analysis
    with track_agent_latency("agent2", "analysis"):
        analysis = analyse_user_history(req.user_id)

    # Agent 3: fallback / safety suggestions
    with track_agent_latency("agent3", "fallback"):
        fallback = fallback_suggestions(profile, prefs)

    # Pass Agent 2 and Agent 3 context forward to Agent 1.
    prefs["analysis_context"] = analysis
    prefs["safety_context"] = fallback

    # Agent 1: day plan generation
    # events = generate_day_plan_with_gpt(
    #     profile,
    #     prefs,
    #     analysis,
    #     fallback
    # )

    with track_agent_latency("agent1", "generation"):
        plan_payload = generate_day_plan_with_gpt(
            profile,
            prefs,
            analysis,
            fallback,
            return_metadata=True,
        )
    events = plan_payload["events"]
    health_tip = plan_payload.get("health_tip", "")
    events, overlap_warnings = _skip_office_overlaps(
        events,
        office_time,
        req.wake_time,
        req.sleep_time,
        prefs["extra_preferences"].get("workout_timing", ""),
    )

    verification = verify_plan_with_agent2(profile, prefs, events)

    if not verification.get("is_valid"):
        with track_agent_latency("agent1", "generation"):
            plan_payload = generate_day_plan_with_gpt(
                profile,
                prefs,
                analysis,
                fallback,
                correction_prompt=verification.get("correction_prompt", ""),
                return_metadata=True,
            )
        events = plan_payload["events"]
        health_tip = plan_payload.get("health_tip", health_tip)

        verification = verify_plan_with_agent2(profile, prefs, events)

    validation_errors = validate_plan_constraints(
        events,
        req.wake_time,
        req.sleep_time,
        req.diet_type,
        office_time=office_time,
    )
    if validation_errors:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Generated plan failed schedule validation.",
                "errors": validation_errors,
            },
        )

    record_plan_event(user.get("profession"), "generated", signal="generated")

    # Agent 4: desktop notification scheduler
    with track_agent_latency("agent4", "notification"):
        notification_result = schedule_day_plan(events)

    # Optional SMS placeholder
    sms_notification = schedule_optional_sms(req.phone, events)

    plan_id = save_plan(
        req.user_id,
        str(date.today()),
        req.wake_time,
        req.sleep_time,
        req.diet_type,
        req.fitness_type,
        req.workout_duration,
        events,
        {
            "agent2": analysis,
            "agent3": fallback,
            "desktop_notification": notification_result,
            "sms_notification": sms_notification,
            "health_tip": health_tip,
        },
    )

    return {
        "plan_id": plan_id,
        "date": str(date.today()),
        "user_id": req.user_id,
        "events": events,
        "message": overlap_warnings[0] if overlap_warnings else "Plan generated successfully.",
        "warnings": overlap_warnings,
        "agent_analysis": {
            "agent1": "OpenAI if configured, otherwise Gemini/local fallback",
            "agent2": analysis,
            "agent3": fallback,
            "agent4": notification_result,
            "health_tip": health_tip,
        },
        "notification": {
            "desktop": notification_result,
            "sms": sms_notification,
        },
        "health_tip": health_tip,
    }


@router.get("/history/{user_id}")
def history(user_id: int, limit: int = 10):
    return {
        "user_id": user_id,
        "entries": get_history(user_id, limit)
    }


@router.post("/feedback")
def feedback(req: FeedbackRequest):
    save_feedback(
        req.user_id,
        req.plan_id,
        req.rating,
        req.comments or ""
    )

    return {
        "message": "Feedback saved successfully"
    }

def validate_plan_constraints(events, wake_time, sleep_time, diet_type, office_time=""):
    errors = []

    wake_minutes, sleep_minutes = awake_window_bounds(wake_time, sleep_time)
    wraps_midnight = int(sleep_time.split(":")[0]) * 60 + int(sleep_time.split(":")[1]) <= int(wake_time.split(":")[0]) * 60 + int(wake_time.split(":")[1])
    errors.extend(validate_awake_office_alignment(wake_time, sleep_time, office_time))

    office = parse_office_time(office_time) if office_time else None
    office_start = office_end = None
    normalized_office_start = normalized_office_end = None
    if office:
        office_start = int(office["start"].split(":")[0]) * 60 + int(office["start"].split(":")[1])
        office_end = int(office["end"].split(":")[0]) * 60 + int(office["end"].split(":")[1])
        normalized_office_start = office_start
        normalized_office_end = office_end
        if sleep_minutes <= wake_minutes:
            if normalized_office_start < wake_minutes:
                normalized_office_start += 24 * 60
            if normalized_office_end < normalized_office_start:
                normalized_office_end += 24 * 60

    for event in events:
        event_time = event.get("time", "")

        try:
            event_minutes = int(event_time.split(":")[0]) * 60 + int(event_time.split(":")[1])
        except Exception:
            errors.append(f"Invalid time format for activity: {event.get('activity')}")
            continue

        if wraps_midnight and event_minutes < wake_minutes:
            event_minutes += 24 * 60

        if event_minutes < wake_minutes:
            errors.append(
                f"{event.get('activity')} at {event_time} is before wake-up time {wake_time}"
            )
            continue

        if event_minutes > sleep_minutes:
            errors.append(
                f"{event.get('activity')} at {event_time} is after sleep time {sleep_time}"
            )
            continue

        activity = str(event.get("activity", "")).lower()

        diet_label = str(diet_type or "").strip().lower()
        for word in _diet_bans(diet_label):
            if word in activity:
                label = "Vegan" if diet_label == "vegan" else "Veg"
                errors.append(
                    f"{label} item '{word}' found in {label} plan: {event.get('activity')}"
                )

        if office and event.get("category") == "workout":
            if (
                normalized_office_start is not None
                and normalized_office_end is not None
                and normalized_office_start <= event_minutes <= normalized_office_end
            ):
                errors.append(
                    f"{event.get('activity')} is scheduled during office hours ({office_time})."
                )

    return errors


@router.post("/planner/update")
def update_plan(req: UpdatePlanRequest):
    user = get_user_by_id(req.user_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    profile = {
        "name": user["name"],
        "email": user["email"],
        "phone": user["phone"],
        "height": user["height"],
        "weight": user["weight"],
        "gender": user["gender"],
        "age": user["age"],
        "profession": user["profession"],
        "diseases": user["diseases"],
        "disability": user["disability"],
    }

    prefs = {
        "wake_time": req.wake_time,
        "sleep_time": req.sleep_time,
        "diet_type": req.diet_type,
        "fitness_type": req.fitness_type,
        "workout_duration": req.workout_duration,
        "extra_preferences": getattr(req, "preferences", {}) or {},
    }
    prefs["extra_preferences"].setdefault("workout_timing", prefs["extra_preferences"].get("gym_preference", "Flexible"))
    reading_preference = _reading_preference_from_events(req.events, prefs["extra_preferences"], "")
    if reading_preference:
        prefs["extra_preferences"]["reading_preference"] = reading_preference

    office_time = prefs["extra_preferences"].get("office_time", "")
    if not office_time:
        office_start = prefs["extra_preferences"].get("office_start")
        office_end = prefs["extra_preferences"].get("office_end")
        if office_start and office_end:
            office_time = f"{office_start} to {office_end}"
    office_errors = validate_awake_office_alignment(req.wake_time, req.sleep_time, office_time)
    if office_errors:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Office timing must fall within the user's awake window.",
                "errors": office_errors,
            },
        )

    with track_agent_latency("agent2", "analysis"):
        analysis = analyse_user_history(req.user_id)
    with track_agent_latency("agent3", "fallback"):
        fallback = fallback_suggestions(profile, prefs)
    correction_prompt = _build_correction_prompt(req.events)
    events = req.events
    health_tip = fallback.get("health_tip", "")

    if correction_prompt:
        with track_agent_latency("agent1", "generation"):
            plan_payload = generate_day_plan_with_gpt(
                profile,
                prefs,
                analysis,
                fallback,
                correction_prompt=correction_prompt,
                return_metadata=True,
            )
        events = plan_payload["events"]
        health_tip = plan_payload.get("health_tip", health_tip)
    events, overlap_warnings = _skip_office_overlaps(
        events,
        office_time,
        req.wake_time,
        req.sleep_time,
        prefs["extra_preferences"].get("workout_timing", ""),
    )

    validation_errors = validate_plan_constraints(
        events,
        req.wake_time,
        req.sleep_time,
        req.diet_type,
        office_time=office_time,
    )
    if validation_errors:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Generated plan failed schedule validation.",
                "errors": validation_errors,
            },
        )

    plan_id = save_plan(
        req.user_id,
        str(date.today()),
        req.wake_time,
        req.sleep_time,
        req.diet_type,
        req.fitness_type,
        req.workout_duration,
        events,
        {
            "update_type": "user_edit_regenerated" if correction_prompt else "user_edit",
            "analysis": analysis,
            "fallback": fallback,
            "health_tip": health_tip,
            "correction_prompt": correction_prompt,
        }
    )

    record_plan_event(user.get("profession"), "updated", signal="remark_regenerated" if correction_prompt else "manual_edit")

    return {
        "message": "Plan updated successfully",
        "old_plan_id": req.plan_id,
        "new_plan_id": plan_id,
        "user_id": req.user_id,
        "events": events,
        "warnings": overlap_warnings,
        "validation_errors": validation_errors
    }

@router.post("/planner/finalize")
def finalize_plan(req: FinalizePlanRequest):
    user = get_user_by_id(req.user_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    profile = {
        "name": user["name"],
        "email": user["email"],
        "phone": user["phone"],
        "height": user["height"],
        "weight": user["weight"],
        "gender": user["gender"],
        "age": user["age"],
        "profession": user["profession"],
        "diseases": user["diseases"],
        "disability": user["disability"],
    }

    prefs = {
        "wake_time": req.wake_time,
        "sleep_time": req.sleep_time,
        "diet_type": req.diet_type,
        "fitness_type": req.fitness_type,
        "workout_duration": req.workout_duration,
        "extra_preferences": req.preferences or {},
    }
    prefs["extra_preferences"].setdefault("workout_timing", prefs["extra_preferences"].get("gym_preference", "Flexible"))
    reading_preference = _reading_preference_from_events(req.events, prefs["extra_preferences"], prefs["extra_preferences"].get("user_change_reason", ""))
    if reading_preference:
        prefs["extra_preferences"]["reading_preference"] = reading_preference

    office_time = prefs["extra_preferences"].get("office_time", "")
    if not office_time:
        office_start = prefs["extra_preferences"].get("office_start")
        office_end = prefs["extra_preferences"].get("office_end")
        if office_start and office_end:
            office_time = f"{office_start} to {office_end}"
    office_errors = validate_awake_office_alignment(req.wake_time, req.sleep_time, office_time)
    if office_errors:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Office timing must fall within the user's awake window.",
                "errors": office_errors,
            },
        )

    with track_agent_latency("agent2", "analysis"):
        analysis = analyse_user_history(req.user_id)
    with track_agent_latency("agent3", "fallback"):
        fallback = fallback_suggestions(profile, prefs)
    correction_prompt = _build_correction_prompt(req.events, prefs.get("extra_preferences", {}), prefs["extra_preferences"].get("user_change_reason", ""))

    if correction_prompt:
        with track_agent_latency("agent1", "generation"):
            plan_payload = generate_day_plan_with_gpt(
                profile,
                prefs,
                analysis,
                fallback,
                correction_prompt=correction_prompt,
                return_metadata=True,
            )
        final_events = plan_payload["events"]
        health_tip = plan_payload.get("health_tip", fallback.get("health_tip", ""))
        agent2_validation = {
            "message": "Plan regenerated from user remarks.",
            "updated_by": "user",
        }
    else:
        # Agent 2 finalises user-edited plan
        final_events = finalize_plan_with_agent2(
            profile,
            prefs,
            req.events
        )
        health_tip = fallback.get("health_tip", "")
        agent2_validation = {
            "message": "User manually edited the generated day plan.",
            "updated_by": "user",
        }

    final_events, overlap_warnings = _skip_office_overlaps(
        final_events,
        office_time,
        req.wake_time,
        req.sleep_time,
        prefs["extra_preferences"].get("workout_timing", ""),
    )

    # Agent 3 validates final plan
    validation = validate_final_plan(
        prefs,
        final_events
    )

    # If validation fails, return errors and still show final plan
    new_plan_id = save_plan(
        req.user_id,
        str(date.today()),
        req.wake_time,
        req.sleep_time,
        req.diet_type,
        req.fitness_type,
        req.workout_duration,
        final_events,
        {
            "update_type": "user_edit_finalised",
            "agent2": agent2_validation,
            "fallback": fallback,
            "health_tip": health_tip,
            "correction_prompt": correction_prompt,
            "agent3_validation": validation,
        },
    )

    record_plan_event(user.get("profession"), "finalized", signal="remark_regenerated" if correction_prompt else "manual_finalized")

    return {
        "message": "Plan finalised successfully",
        "old_plan_id": req.plan_id,
        "new_plan_id": new_plan_id,
        "user_id": req.user_id,
        "events": final_events,
        "warnings": overlap_warnings,
        "validation": validation,
        "health_tip": health_tip,
    }

# from fastapi import APIRouter, HTTPException
# from datetime import date
# from src.models import DayPlanRequest, FeedbackRequest
# from src.services.auth_service import get_user_by_id
# from src.agents.agent2_analyser import analyse_user_history
# from src.agents.agent3_feedback import fallback_suggestions
# from src.agents.agent1_day_planner import generate_day_plan_with_gpt
# from src.services.history_service import save_plan, get_history, save_feedback
# from src.services.notification_service import schedule_optional_sms
# from src.agents.agent4_notification import schedule_day_plan
# router = APIRouter(tags=["Planner"])


# @router.post("/planner/generate")
# def generate_plan(req: DayPlanRequest):
#     user = get_user_by_id(req.user_id)
#     if not user:
#         raise HTTPException(status_code=404, detail="User not found")

#     profile = {k: user[k] for k in ["name", "email", "phone", "height", "weight", "gender", "age", "profession", "diseases", "disability"]}
#     prefs = {
#         "wake_time": req.wake_time,
#         "sleep_time": req.sleep_time,
#         "diet_type": req.diet_type,
#         "fitness_type": req.fitness_type,
#         "workout_duration": req.workout_duration,
#         "extra_preferences": req.preferences or {}
#     }
#     analysis = analyse_user_history(req.user_id)
#     fallback = fallback_suggestions(profile, prefs)
#     events = generate_day_plan_with_gpt(profile, prefs, analysis, fallback)
#     notification = schedule_optional_sms(req.phone, events)
#     plan_id = save_plan(req.user_id, str(date.today()), req.wake_time, req.sleep_time, req.diet_type, req.fitness_type, req.workout_duration, events, {"agent2": analysis, "agent3": fallback, "notification": notification})

#     return {
#         "plan_id": plan_id,
#         "date": str(date.today()),
#         "user_id": req.user_id,
#         "events": events,
#         "agent_analysis": {
#             "agent1": "Azure OpenAI GPT-4o if configured, otherwise local fallback",
#             "agent2": analysis,
#             "agent3": fallback
#         },
#         "notification": notification
#     }


# @router.get("/history/{user_id}")
# def history(user_id: int, limit: int = 10):
#     return {"user_id": user_id, "entries": get_history(user_id, limit)}


# @router.post("/feedback")
# def feedback(req: FeedbackRequest):
#     save_feedback(req.user_id, req.plan_id, req.rating, req.comments or "")
#     return {"message": "Feedback saved successfully"}
