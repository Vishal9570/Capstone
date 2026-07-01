from datetime import datetime, timedelta

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
        timeout=10
    )


def schedule_day_plan(events):

    """
    events = [
        {
            "time":"07:30",
            "activity":"Poha with curd",
            "notes":"Healthy Indian breakfast",
            "category":"meal"
        }
    ]
    """

    if scheduler is None:
        print("apscheduler is not installed; skipping scheduled desktop notifications.")
        return

    if not scheduler.running:
        scheduler.start()

    if notification is None:
        print("plyer is not installed; skipping desktop notifications.")
        return

    for event in events:

        try:

            event_time = datetime.strptime(
                event["time"],
                "%H:%M"
            )

            today = datetime.now()

            run_time = today.replace(
                hour=event_time.hour,
                minute=event_time.minute,
                second=0,
                microsecond=0
            )

            # Skip past events
            if run_time < today:
                continue

            scheduler.add_job(
                desktop_notification,
                trigger="date",
                run_date=run_time,
                args=[
                    f"⏰ {event['activity']}",
                    event["notes"]
                ],
                id=f"{event['time']}_{event['activity']}",
                replace_existing=True
            )

            print(f"Notification scheduled for {run_time}")

        except Exception as e:

            print(e)
