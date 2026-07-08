"""Streamlit UI for the Multi-Agent Day Planner. Run: streamlit run ui/app.py"""
import streamlit as st
import httpx
import pandas as pd
import os
API_BASE = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
st.set_page_config(page_title="AI Day Planner", page_icon="DP", layout="wide")
st.markdown("""
<style>
:root {
    --bg: #eef4f4;
    --surface: #ffffff;
    --surface-alt: #f7fbfb;
    --ink: #262530;
    --muted: #6b7280;
    --accent: #f4765d;
    --accent-2: #71d49a;
    --accent-3: #c7f0e7;
    --sidebar: #282637;
    --sidebar-soft: #332f44;
    --border: rgba(40, 38, 55, 0.08);
    --shadow: 0 14px 40px rgba(31, 41, 55, 0.08);
}

html, body, [class*="css"] {
    font-family: "Segoe UI", "Trebuchet MS", sans-serif;
}

body {
    background:
        radial-gradient(circle at top left, rgba(244,118,93,0.12), transparent 28%),
        radial-gradient(circle at top right, rgba(113,212,154,0.14), transparent 24%),
        linear-gradient(180deg, #f4f8f8 0%, #eef4f4 100%);
    color: var(--ink);
}

.stApp {
    background: transparent;
}

section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, var(--sidebar) 0%, #201f2c 100%);
    border-right: 0;
}

section[data-testid="stSidebar"] * {
    color: #f6f7fb !important;
}

section[data-testid="stSidebar"] .stRadio label {
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 14px;
    margin-bottom: 0.35rem;
    padding: 0.2rem 0.4rem;
}

section[data-testid="stSidebar"] .stButton button {
    width: 100%;
    border-radius: 14px;
    background: rgba(255,255,255,0.08);
    border: 1px solid rgba(255,255,255,0.1);
    color: #fff;
}

.brand-shell {
    display: flex;
    align-items: center;
    gap: 0.8rem;
    padding: 1rem 0 0.4rem 0;
}

.brand-mark {
    width: 3rem;
    height: 3rem;
    border-radius: 999px;
    background: linear-gradient(135deg, var(--accent) 0%, #ff9b7b 100%);
    color: #1f2230;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 800;
    font-size: 1.15rem;
    box-shadow: 0 10px 30px rgba(244,118,93,0.32);
}

.muted {
    color: var(--muted);
}

.hero-card,
.panel-card,
.mini-card,
.metric-card,
.note-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 22px;
    box-shadow: var(--shadow);
}

.hero-card {
    padding: 1.25rem 1.35rem;
}

.hero-pill {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    padding: 0.4rem 0.75rem;
    border-radius: 999px;
    background: var(--accent-3);
    color: #23423d;
    font-size: 0.85rem;
    font-weight: 700;
}

.metric-card {
    padding: 1rem 1.1rem;
    position: relative;
    overflow: hidden;
}

.metric-label {
    font-size: 0.8rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--muted);
}

.metric-value {
    font-size: 2rem;
    font-weight: 800;
    margin-top: 0.2rem;
}

.metric-sub {
    color: var(--muted);
    font-size: 0.92rem;
}

.metric-accent {
    width: 2.75rem;
    height: 2.75rem;
    border-radius: 999px;
    background: linear-gradient(135deg, var(--sidebar) 0%, #423d5c 100%);
    color: #fff;
    display: flex;
    align-items: center;
    justify-content: center;
    position: absolute;
    right: 1rem;
    top: 1rem;
    font-size: 1.05rem;
}

.panel-card {
    padding: 1.2rem;
}

.mini-card {
    padding: 1rem;
    background: linear-gradient(180deg, #ffffff 0%, #fbfcfd 100%);
}

.section-title {
    font-size: 1.55rem;
    font-weight: 800;
    margin-bottom: 0.2rem;
}

.section-subtitle {
    color: var(--muted);
    margin-bottom: 1rem;
}

div.stButton > button:first-child {
    background: linear-gradient(135deg, var(--accent) 0%, #f5947f 100%);
    color: white;
    border-radius: 14px;
    border: none;
    padding: 0.7rem 1.35rem;
    font-size: 16px;
    font-weight: 700;
    transition: 0.2s ease;
    box-shadow: 0 10px 24px rgba(244,118,93,0.28);
}

div.stButton > button:first-child:hover {
    transform: translateY(-1px);
    box-shadow: 0 14px 28px rgba(244,118,93,0.34);
}

div[data-testid="stForm"] {
    background: rgba(255,255,255,0.8);
    border: 1px solid var(--border);
    border-radius: 20px;
    box-shadow: var(--shadow);
    padding: 1rem 1rem 0.5rem 1rem;
}

.stDataFrame, [data-testid="stDataFrame"] {
    border-radius: 18px;
    overflow: hidden;
    border: 1px solid var(--border);
    box-shadow: var(--shadow);
}
</style>
""", unsafe_allow_html=True)

def api_post(path, payload):
    try:
        r = httpx.post(f"{API_BASE}{path}", json=payload, timeout=90)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        st.error(f"API error {e.response.status_code}: {e.response.text}")
    except Exception as e:
        st.error(f"Connection error: {e}")
    return {}


def api_get(path, params=None):
    try:
        r = httpx.get(f"{API_BASE}{path}", params=params or {}, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"Error: {e}")
    return {}


def _time_to_minutes(value):
    if value is None:
        return None
    return value.hour * 60 + value.minute


def _office_alignment_errors(wake_time, sleep_time, office_start, office_end):
    errors = []
    if office_start is None or office_end is None:
        return errors

    wake_mins = _time_to_minutes(wake_time)
    sleep_mins = _time_to_minutes(sleep_time)
    office_start_mins = _time_to_minutes(office_start)
    office_end_mins = _time_to_minutes(office_end)

    if office_end_mins <= office_start_mins:
        errors.append("Office end time must be after office start time.")
    if office_start_mins < wake_mins:
        errors.append("Office time starts before the user wakes up.")
    if office_end_mins > sleep_mins:
        errors.append("Office time continues after the user's sleep time.")
    return errors


def fmt_time(value):
    return value.strftime("%I:%M %p") if value else "Not set"


def metric_card(label, value, sublabel="", accent="*"):
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
            <div class="metric-sub">{sublabel}</div>
            <div class="metric-accent">{accent}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def hero_banner(title, subtitle, pill="Dashboard"):
    st.markdown(
        f"""
        <div class="hero-card">
            <div class="hero-pill">{pill}</div>
            <div style="margin-top: 0.75rem;">
                <div class="section-title">{title}</div>
                <div class="section-subtitle">{subtitle}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def panel_title(title, subtitle=""):
    st.markdown(
        f"""
        <div style="margin-bottom: 0.8rem;">
            <div class="section-title">{title}</div>
            <div class="section-subtitle">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _ensure_remark_column(events):
    normalized = []
    for event in events or []:
        item = dict(event)
        item.setdefault("remark", "")
        normalized.append(item)
    return normalized





# Initialize session state
defaults = {
    "logged_in": False,
    "user": None,
    "auth_page": "signup",
    "latest_plan_id": None,
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

# Reset application
if st.sidebar.button("Reset App / Logout"):
    for key, value in defaults.items():
        st.session_state[key] = value

    st.cache_data.clear()
    st.cache_resource.clear()

    st.rerun()


def signup_page():
    st.title("New User Signup")
    st.caption("Create your health and lifestyle profile.")
    with st.form("signup_form"):
        c1, c2 = st.columns(2)
        name = c1.text_input("Name")
        email = c2.text_input("Email ID")
        phone = c1.text_input("Phone Number", placeholder="+91XXXXXXXXXX")
        profession = c2.text_input("Profession")
        password = c1.text_input("Password", type="password")
        confirm_password = c2.text_input("Confirm Password", type="password")
        c3, c4, c5 = st.columns(3)
        height = c3.number_input("Height (cm)", 50.0, 250.0, 170.0)
        weight = c4.number_input("Weight (kg)", 20.0, 200.0, 70.0)
        age = c5.number_input("Age", 10, 100, 25)
        gender = st.selectbox("Gender", ["Male", "Female", "Other"])
        diseases = st.multiselect("Diseases", ["None", "BP", "Sugar", "Heart", "Asthma", "Thyroid"])
        disability = st.text_input("Disability, if any", placeholder="Write None if not applicable")
        submitted = st.form_submit_button("Signup", type="primary", use_container_width=True)
    if submitted:
        if password != confirm_password:
            st.error("Password and confirm password do not match.")
            return
        if not name or not email or not password:
            st.error("Please fill Name, Email and Password.")
            return
        result = api_post("/auth/signup", {"name": name, "email": email, "phone": phone, "password": password, "height": height, "weight": weight, "gender": gender, "age": int(age), "profession": profession, "diseases": diseases, "disability": disability})
        if result.get("user"):
            st.success("Signup successful. Please login.")
            st.session_state.auth_page = "login"
            st.rerun()
    st.divider()
    if st.button("Already have an account? Login"):
        st.session_state.auth_page = "login"
        st.rerun()


def login_page():
    st.title("Login")
    st.caption("For demo, email login is enabled. In production, password should always be required.")
    email = st.text_input("Email ID")
    password = st.text_input("Password Optional", type="password")
    if st.button("Login", type="primary", use_container_width=True):
        result = api_post("/auth/login", {"email": email, "password": password if password else None})
        if result.get("user"):
            st.session_state.logged_in = True
            st.session_state.user = result["user"]
            st.success("Login successful.")
            st.rerun()
    st.divider()
    if st.button("New user? Signup"):
        st.session_state.auth_page = "signup"
        st.rerun()


if not st.session_state.logged_in:
    signup_page() if st.session_state.auth_page == "signup" else login_page()
    st.stop()

user = st.session_state.user
with st.sidebar:
    st.title("Day Planner Agent")
    st.caption("Multi-Agent | Indian Meals | Notify")
    st.divider()
    st.write(f"Logged in as: **{user['name']}**")
    st.caption(user["email"])
    page = st.radio(
        "Navigate",
        ["Profile", "Dashboard", "History", "Feedback", "Analytics"],
        index=1,
        label_visibility="collapsed",
    )
    st.divider()
    phone = st.text_input("Phone", value=user.get("phone") or "")
    if st.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.user = None
        st.session_state.auth_page = "login"
        st.session_state.latest_plan_id = None
        st.rerun()



if page in ("Dashboard", "Day Planner"):
    hero_banner(
        "Plan your day with less effort and better balance",
        "The planner blends your routine, history, health context, and office timing into one practical schedule.",
        pill="Day Planner",
    )

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        metric_card("User", user["name"], user["email"], accent="U")
    with m2:
        metric_card("Wake", fmt_time(st.session_state.get("wake_time_value")), "Last selected wake time", accent="W")
    with m3:
        metric_card("Sleep", fmt_time(st.session_state.get("sleep_time_value")), "Last selected sleep time", accent="S")
    with m4:
        metric_card("Plan", "Ready", "Generate or update anytime", accent="P")

    st.markdown("<div style='height: 0.7rem;'></div>", unsafe_allow_html=True)
    st.title("Generate My Day Plan")
    st.caption("Agent 1 creates, Agent 2 finalises, Agent 3 validates.")

    c1, c2 = st.columns(2)
    wake_time = c1.time_input("Wake-up time")
    sleep_time = c2.time_input("Sleep time")
    st.session_state.wake_time_value = wake_time
    st.session_state.sleep_time_value = sleep_time

    

    st.subheader("Work Schedule")

    c1, c2 = st.columns(2)

    office_start = c1.time_input(
        "Office Start Time",
        value=None,
        key="office_start"
    )

    office_end = c2.time_input(
        "Office End Time",
        value=None,
        key="office_end"
    )

    office_time = (
        f"{office_start.strftime('%H:%M')} to {office_end.strftime('%H:%M')}"
        if office_start and office_end
        else ""
    )

    work_mode = st.selectbox(
        "Work Mode",
        [
            "Office",
            "Work From Home",
            "Hybrid",
            "Student",
            "Not Working"
        ]
    )

    gym_preference = st.selectbox(
        "Workout Timing",
        [
            "Morning",
            "After Office",
            "Evening",
            "Flexible"
        ]
    )

    diet_type = st.selectbox("Diet Preference", ["Veg", "Non-Veg"])
    fitness_type = st.selectbox("Fitness Preference", ["Gym", "Yoga", "Both"])
    workout_duration = st.selectbox("Workout Duration", ["1 hr", "1.5 hr", "2 hr"])

    preferences_text = st.text_area(
        "Extra Preferences",
        placeholder="Example: avoid rice at night, gym after office, light dinner"
    )

    wake_str = wake_time.strftime("%H:%M")
    sleep_str = sleep_time.strftime("%H:%M")

    if "current_events" not in st.session_state:
        st.session_state.current_events = []

    if "edit_mode" not in st.session_state:
        st.session_state.edit_mode = False

    if st.button("Generate My Day Plan", type="primary", use_container_width=True):
        office_errors = _office_alignment_errors(wake_time, sleep_time, office_start, office_end)
        if office_errors:
            st.error("Office timing must fall within your awake window.")
            for msg in office_errors:
                st.write(f"- {msg}")
            st.stop()

      
        
        result = api_post(
            "/planner/generate",
            {
                "user_id": user["id"],
                "wake_time": wake_str,
                "sleep_time": sleep_str,
                "diet_type": diet_type,
                "fitness_type": fitness_type,
                "workout_duration": workout_duration,
                "phone": phone or None,
                "preferences": {
                    "notes": preferences_text,
                    "work_mode": work_mode,
                    "office_start": office_start.strftime("%H:%M") if office_start else None,
                    "office_end": office_end.strftime("%H:%M") if office_end else None,
                    "gym_preference": gym_preference
                }
            }
        )

        if result.get("events"):
            st.session_state.latest_plan_id = result.get("plan_id")
            st.session_state.current_events = _ensure_remark_column(result["events"])
            st.session_state.edit_mode = False
            # st.success("Day plan generated successfully.")

            if result.get("validation"):
                st.json(result["validation"])
            
            if result.get("health_tip"):
                st.success(f"Healthy tip: {result['health_tip']}")

    if st.session_state.current_events:
        st.subheader("Your Day Plan")
        st.caption("Use the remark column to request changes, then regenerate the plan.")
        st.info("Only the Remark column is editable. Use it to request meal, workout, or timing changes.")
        current_df = pd.DataFrame(_ensure_remark_column(st.session_state.current_events))
        editable_columns = [column for column in current_df.columns if column != "remark"]
        edited_df = st.data_editor(
            current_df,
            use_container_width=True,
            num_rows="fixed",
            hide_index=True,
            disabled=editable_columns,
            column_config={
                "remark": st.column_config.TextColumn(
                    "Remark",
                    help="Add a change request for this row, such as skip meal or move workout time.",
                    default="",
                ),
            },
            key="editable_day_plan",
        )
        user_change_reason = st.text_area(
            "What changed?",
            placeholder="Example: I did not have grilled chicken. I had rice and dal. Also lunch happened at 2 PM because of office work."
        )
        c1, c2 = st.columns(2)
        if c1.button("Regenerate Plan", use_container_width=True):
            result = api_post(
                "/planner/finalize",
                {
                    "user_id": user["id"],
                    "plan_id": st.session_state.latest_plan_id,
                    "wake_time": wake_str,
                    "sleep_time": sleep_str,
                    "diet_type": diet_type,
                    "fitness_type": fitness_type,
                    "workout_duration": workout_duration,
                    "events": edited_df.to_dict("records"),
                    "preferences": {
                        "notes": preferences_text,
                        "office_time": office_time,
                        "user_change_reason": user_change_reason,
                    }
                }
            )
            if result.get("events"):
                st.session_state.current_events = _ensure_remark_column(result["events"])
                st.session_state.latest_plan_id = result.get("new_plan_id")
                st.success("Updated day plan regenerated successfully.")
                if result.get("validation"):
                    st.json(result["validation"])
                st.rerun()
        if c1.button("Finalise Updated Plan", use_container_width=True):
            result = api_post(
                "/planner/finalize",
                {
                    "user_id": user["id"],
                    "plan_id": st.session_state.latest_plan_id,
                    "wake_time": wake_str,
                    "sleep_time": sleep_str,
                    "diet_type": diet_type,
                    "fitness_type": fitness_type,
                    "workout_duration": workout_duration,
                    "events": edited_df.to_dict("records"),
                    "preferences": {
                        "notes": preferences_text,
                        "office_time": office_time,
                        "user_change_reason": user_change_reason,
                    }
                }
            )
            if result.get("events"):
                st.session_state.current_events = _ensure_remark_column(result["events"])
                st.session_state.latest_plan_id = result.get("new_plan_id")
                st.success("Updated day plan finalised successfully.")
                if result.get("validation"):
                    st.json(result["validation"])
                st.rerun()
        if c2.button("Cancel Edit", use_container_width=True):
            st.session_state.current_events = _ensure_remark_column(st.session_state.current_events)
            st.rerun()

elif page == "Profile":
    st.title("👤 Edit Profile")
    st.caption("Update your health and lifestyle profile. Future day plans will use this updated data.")

    current_diseases = user.get("diseases") or ""
    current_diseases_list = [
        d.strip() for d in current_diseases.split(",") if d.strip()
    ]

    with st.form("profile_update_form"):
        c1, c2 = st.columns(2)

        phone_new = c1.text_input("Phone Number", value=user.get("phone") or "")
        profession_new = c2.text_input("Profession", value=user.get("profession") or "")

        height_new = c1.number_input(
            "Height (cm)",
            50.0,
            250.0,
            float(user.get("height") or 170.0),
        )

        weight_new = c2.number_input(
            "Weight (kg)",
            20.0,
            200.0,
            float(user.get("weight") or 70.0),
        )

        age_new = c1.number_input(
            "Age",
            10,
            100,
            int(user.get("age") or 25),
        )

        diseases_new = st.multiselect(
            "Diseases",
            ["None", "BP", "Sugar", "Heart", "Asthma", "Thyroid"],
            default=current_diseases_list if current_diseases_list else ["None"],
        )

        disability_new = st.text_input(
            "Disability, if any",
            value=user.get("disability") or "",
        )

        submitted = st.form_submit_button(
            "💾 Update Profile",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        result = api_post(
            "/profile/update",
            {
                "user_id": user["id"],
                "phone": phone_new,
                "height": height_new,
                "weight": weight_new,
                "age": int(age_new),
                "profession": profession_new,
                "diseases": diseases_new,
                "disability": disability_new,
            },
        )

        if result.get("user"):
            st.session_state.user = result["user"]
            st.success("Profile updated successfully.")
            st.rerun()

elif page == "History":
    st.title("History")
    st.caption("Review your previous day plans and saved context.")

    try:
        history_result = api_get(f"/history/{user['id']}", params={"limit": 10})
        history_entries = history_result.get("entries", [])
    except Exception as exc:
        st.error(f"Unable to load history: {exc}")
        history_entries = []

    if history_entries:
        history_df = pd.DataFrame(history_entries)
        display_cols = [col for col in history_df.columns if col not in {"events_json", "analysis_json"}]
        st.dataframe(history_df[display_cols], use_container_width=True)

        selected_plan = st.selectbox(
            "Inspect plan",
            options=[entry["id"] for entry in history_entries],
            format_func=lambda plan_id: f"Plan #{plan_id}",
        )
        selected_entry = next((entry for entry in history_entries if entry["id"] == selected_plan), None)
        if selected_entry:
            st.subheader("Plan details")
            st.json(selected_entry)
    else:
        st.info("No history found yet. Generate your first plan to see it here.")

elif page == "Feedback":
    st.title("Feedback")
    st.caption("Share how the latest plan worked for you.")

    plan_options = []
    try:
        history_result = api_get(f"/history/{user['id']}", params={"limit": 10})
        plan_options = history_result.get("entries", [])
    except Exception as exc:
        st.error(f"Unable to load plans for feedback: {exc}")

    if not plan_options:
        st.info("Generate a plan first, then come back here to rate it.")
    else:
        with st.form("feedback_form"):
            selected_plan = st.selectbox(
                "Select plan",
                options=[entry["id"] for entry in plan_options],
                format_func=lambda plan_id: f"Plan #{plan_id}",
            )
            rating = st.slider("Rating", min_value=1, max_value=5, value=4)
            comments = st.text_area("Comments", placeholder="What worked well? What should change next time?")
            submit_feedback = st.form_submit_button("Submit Feedback")

        if submit_feedback:
            result = api_post(
                "/feedback",
                {
                    "user_id": user["id"],
                    "plan_id": selected_plan,
                    "rating": rating,
                    "comments": comments,
                },
            )
            if result.get("message"):
                st.success(result["message"])

elif page == "Analytics":
    st.title("Analytics")
    st.caption("Compare how different professions follow their plans.")

    profession_metrics = []
    try:
        analytics_result = api_get("/analytics/professions")
        profession_metrics = analytics_result.get("items", [])
    except Exception as exc:
        st.error(f"Unable to load profession analytics: {exc}")

    if profession_metrics:
        metrics_df = pd.DataFrame(profession_metrics)
        st.dataframe(metrics_df, use_container_width=True)

        chart_df = metrics_df.set_index("profession")[["plans", "updates", "finalized", "feedback_count"]]
        st.bar_chart(chart_df)
    else:
        st.info("No profession analytics available yet. Generate a few plans first.")

    st.markdown("""
| Service | URL |
|---|---|
| FastAPI Docs | [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) |
| API Health | [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health) |
| Profession Analytics | [http://127.0.0.1:8000/analytics/professions](http://127.0.0.1:8000/analytics/professions) |
""")


