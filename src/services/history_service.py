import json
from src.db.database import get_connection


def save_plan(user_id, plan_date, wake_time, sleep_time, diet_type, fitness_type, workout_duration, events, analysis):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO day_plans
    (user_id, plan_date, wake_time, sleep_time, diet_type, fitness_type, workout_duration, events_json, analysis_json)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id, plan_date, wake_time, sleep_time, diet_type, fitness_type,
        workout_duration, json.dumps(events, ensure_ascii=False), json.dumps(analysis, ensure_ascii=False)
    ))
    conn.commit()
    plan_id = cur.lastrowid
    conn.close()
    return plan_id


def get_history(user_id: int, limit: int = 10):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM day_plans WHERE user_id = ? ORDER BY created_at DESC LIMIT ?", (user_id, limit))
    rows = cur.fetchall()
    conn.close()
    output = []
    for row in rows:
        item = dict(row)
        item["events"] = json.loads(item["events_json"])
        item["analysis"] = json.loads(item["analysis_json"])
        item.pop("events_json", None)
        item.pop("analysis_json", None)
        output.append(item)
    return output


def save_feedback(user_id: int, plan_id: int, rating: int, comments: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO feedback (user_id, plan_id, rating, comments) VALUES (?, ?, ?, ?)", (user_id, plan_id, rating, comments))
    conn.commit()
    conn.close()
