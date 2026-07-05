from datetime import datetime

try:
    from apscheduler.schedulers.background import BackgroundScheduler
except ImportError:
    BackgroundScheduler = None

try:
    from plyer import notification
except ImportError:
    notification = None

scheduler = BackgroundScheduler() if BackgroundScheduler is not None else None


def desktop_notification(title, message):
    if notification is None:
        print(f"Desktop notification unavailable: {title} - {message}")
        return
    notification.notify(
        title=title,
        message=message,
        timeout=10,
    )


def schedule_day_plan(events):
    """
    Schedule desktop notifications for upcoming plan items.
    """
    if scheduler is None:
        print("apscheduler is not installed; skipping scheduled desktop notifications.")
        return {"enabled": False, "scheduled_count": 0, "message": "Scheduler unavailable."}

    if not scheduler.running:
        scheduler.start()

    if notification is None:
        print("plyer is not installed; skipping desktop notifications.")
        return {"enabled": False, "scheduled_count": 0, "message": "Desktop notifications unavailable."}

    scheduled_count = 0
    for event in events or []:
        try:
            event_time = datetime.strptime(str(event.get("time", "")), "%H:%M")
            today = datetime.now()
            run_time = today.replace(
                hour=event_time.hour,
                minute=event_time.minute,
                second=0,
                microsecond=0,
            )

            if run_time < today:
                continue

            scheduler.add_job(
                desktop_notification,
                trigger="date",
                run_date=run_time,
                args=[
                    f"Notification: {event.get('activity', 'Day plan item')}",
                    event.get("notes") or event.get("activity", ""),
                ],
                id=f"{event.get('time', 'unknown')}_{event.get('activity', 'item')}",
                replace_existing=True,
            )
            scheduled_count += 1
            print(f"Notification scheduled for {run_time}")
        except Exception as exc:
            print(exc)

    return {
        "enabled": True,
        "scheduled_count": scheduled_count,
        "message": "Desktop notifications scheduled successfully." if scheduled_count else "No future notifications to schedule.",
    }
