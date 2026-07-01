from src.models import UpdatePlanRequest
from src.routes import planner as planner_route


def test_update_plan_can_be_called_multiple_times(monkeypatch):
    calls = {"save": 0}

    monkeypatch.setattr(
        planner_route,
        "get_user_by_id",
        lambda user_id: {
            "id": user_id,
            "name": "Test User",
            "email": "test@example.com",
            "phone": "9999999999",
            "height": 170,
            "weight": 70,
            "gender": "Male",
            "age": 30,
            "profession": "Engineer",
            "diseases": "",
            "disability": "",
        },
    )
    monkeypatch.setattr(planner_route, "validate_plan_constraints", lambda *args, **kwargs: [])
    monkeypatch.setattr(planner_route, "schedule_day_plan", lambda events: {"scheduled_count": len(events)})
    monkeypatch.setattr(planner_route, "schedule_optional_sms", lambda phone, events: {"enabled": False})
    monkeypatch.setattr(planner_route, "save_plan", lambda *args, **kwargs: _next_plan_id(calls))

    req = UpdatePlanRequest(
        user_id=1,
        plan_id=10,
        wake_time="08:00",
        sleep_time="22:00",
        diet_type="Veg",
        fitness_type="Yoga",
        workout_duration="1 hr",
        events=[
            {"time": "08:30", "activity": "Wake up and drink water", "category": "wake"},
            {"time": "09:30", "activity": "Breakfast", "category": "meal"},
            {"time": "13:00", "activity": "Lunch", "category": "meal"},
            {"time": "21:30", "activity": "Sleep", "category": "sleep"},
        ],
    )

    first = planner_route.update_plan(req)
    second = planner_route.update_plan(req)

    assert first["message"] == "Plan updated successfully"
    assert second["message"] == "Plan updated successfully"
    assert first["new_plan_id"] != second["new_plan_id"]


def _next_plan_id(calls):
    calls["save"] += 1
    return calls["save"]
