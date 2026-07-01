from datetime import datetime


def to_minutes(time_str):
    try:
        h, m = time_str.split(":")
        return int(h) * 60 + int(m)
    except Exception:
        return None


def validate_final_plan(prefs, events):
    errors = []

    wake_time = prefs.get("wake_time")
    sleep_time = prefs.get("sleep_time")
    diet_type = prefs.get("diet_type")
    office_time = str(prefs.get("extra_preferences", {}).get("office_time", "")).lower()

    wake_mins = to_minutes(wake_time)
    sleep_mins = to_minutes(sleep_time)

    if wake_mins is None:
        errors.append("Invalid wake-up time.")

    for event in events:
        event_time = event.get("time")
        activity = str(event.get("activity", "")).lower()
        category = str(event.get("category", "")).lower()

        event_mins = to_minutes(event_time)

        if event_mins is None:
            errors.append(f"Invalid time format for {event.get('activity')}")
            continue

        if category != "sleep" and wake_mins is not None and event_mins < wake_mins:
            errors.append(
                f"{event.get('activity')} at {event_time} is before wake-up time {wake_time}"
            )

        if diet_type == "Veg":
            non_veg_words = ["chicken", "egg", "fish", "mutton", "meat"]
            for word in non_veg_words:
                if word in activity:
                    errors.append(
                        f"Non-veg item found in Veg plan: {event.get('activity')}"
                    )

        # if "9" in office_time and "7" in office_time:
        #     if category == "workout" and 9 * 60 <= event_mins <= 19 * 60:
        #         errors.append(
        #             f"Workout scheduled during office time: {event_time}"
        #         )


        # Validate activities against office hours
        if office_time:
            office_lower = office_time.lower()
        
            try:
                # Expected format:
                # "9 AM to 7 PM"
                # "09:00 to 19:00"
        
                if "am" in office_lower or "pm" in office_lower:
                    import re
        
                    matches = re.findall(r'(\d{1,2})\s*(am|pm)', office_lower)
        
                    if len(matches) >= 2:
                        start_hour = int(matches[0][0])
                        end_hour = int(matches[1][0])
        
                        if matches[0][1] == "pm" and start_hour != 12:
                            start_hour += 12
        
                        if matches[1][1] == "pm" and end_hour != 12:
                            end_hour += 12
        
                        office_start = start_hour * 60
                        office_end = end_hour * 60
        
                        # Activities that should NOT happen during office hours
                        blocked_categories = [
                            "workout",
                            "meal",
                            "reading",
                            "meditation",
                            "gym",
                            "yoga"
                        ]
        
                        if category in blocked_categories:
                            if office_start <= event_mins <= office_end:
                                errors.append(
                                    f"{event.get('activity')} is scheduled during office hours ({office_time})."
                                )
        
            except Exception:
                pass

    return {
        "is_valid": len(errors) == 0,
        "errors": errors
    }