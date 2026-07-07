import random
from locust import HttpUser, task, between


class DayPlannerUser(HttpUser):
    wait_time = between(1, 3)  # seconds between tasks, simulates real user pacing

    def on_start(self):
        """Runs once per simulated user at the start — signup + login."""
        self.email = f"loadtest_{random.randint(1, 999999)}@example.com"
        self.user_id = None

        signup_payload = {
            "name": "Load Test User",
            "email": self.email,
            "phone": "+919999999999",
            "password": "testpass123",
            "height": 170.0,
            "weight": 70.0,
            "gender": "Male",
            "age": 28,
            "profession": "Software Engineer",
            "diseases": [],
            "disability": "None",
        }
        with self.client.post("/auth/signup", json=signup_payload, catch_response=True) as resp:
            if resp.status_code == 200 and resp.json().get("user"):
                self.user_id = resp.json()["user"]["id"]
                resp.success()
            else:
                resp.failure(f"Signup failed: {resp.status_code} {resp.text}")

    @task(5)
    def generate_plan(self):
        if not self.user_id:
            return
        payload = {
            "user_id": self.user_id,
            "wake_time": "06:00",
            "sleep_time": "22:00",
            "diet_type": "Veg",
            "fitness_type": "Gym",
            "workout_duration": "1 hr",
            "phone": None,
            "preferences": {
                "notes": "office 9 to 6, avoid rice at night",
                "work_mode": "Office",
                "office_start": "09:00",
                "office_end": "18:00",
                "gym_preference": "Morning",
            },
        }
        with self.client.post("/planner/generate", json=payload, catch_response=True, name="/planner/generate") as resp:
            if resp.status_code == 200 and resp.json().get("events"):
                resp.success()
            else:
                resp.failure(f"Generate failed: {resp.status_code} — {resp.text[:300]}")

    @task(3)
    def view_history(self):
        if not self.user_id:
            return
        self.client.get(f"/history/{self.user_id}", params={"limit": 10}, name="/history/[user_id]")

    @task(2)
    def view_analytics(self):
        self.client.get("/analytics/professions")

    @task(1)
    def submit_feedback(self):
        if not self.user_id:
            return
        self.client.post("/feedback", json={
            "user_id": self.user_id,
            "plan_id": 1,
            "rating": random.randint(3, 5),
            "comments": "Load test feedback",
        })
