def schedule_optional_sms(phone: str | None, events: list):
    if not phone:
        return {"enabled": False, "scheduled_count": 0, "message": "Phone number not provided. SMS reminders skipped."}
    return {"enabled": True, "scheduled_count": len(events), "message": "SMS scheduling placeholder completed. Twilio worker can be added later."}
