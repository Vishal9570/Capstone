from collections import defaultdict
import json

from src.db.database import get_connection


def get_profession_comparison():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            u.profession AS profession,
            dp.id AS plan_id,
            dp.plan_date,
            dp.analysis_json,
            COALESCE(f.rating, NULL) AS rating
        FROM day_plans dp
        JOIN users u ON u.id = dp.user_id
        LEFT JOIN feedback f ON f.plan_id = dp.id
        ORDER BY dp.created_at DESC
        """
    )
    rows = cur.fetchall()
    conn.close()

    summary = defaultdict(
        lambda: {
            "profession": "Unknown",
            "plans": 0,
            "updates": 0,
            "finalized": 0,
            "generated": 0,
            "feedback_count": 0,
            "rating_sum": 0,
            "avg_rating": 0,
        }
    )

    for row in rows:
        profession = (row["profession"] or "Unknown").strip() or "Unknown"
        item = summary[profession]
        item["profession"] = profession
        item["plans"] += 1

        analysis = {}
        try:
            analysis = json.loads(row["analysis_json"] or "{}")
        except Exception:
            analysis = {}

        update_type = str(analysis.get("update_type") or "").lower()
        if update_type:
            item["updates"] += 1
        else:
            item["generated"] += 1
        if "finalised" in update_type or "finalized" in update_type:
            item["finalized"] += 1

        rating = row["rating"]
        if rating is not None:
            item["feedback_count"] += 1
            item["rating_sum"] += int(rating)

    output = []
    for profession, item in sorted(summary.items(), key=lambda pair: pair[0]):
        feedback_count = item["feedback_count"]
        item["avg_rating"] = round(item["rating_sum"] / feedback_count, 2) if feedback_count else 0
        item.pop("rating_sum", None)
        output.append(item)

    return output
