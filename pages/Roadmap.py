"""Service-backed roadmap; manual completion is not assessment evidence."""
from html import escape

import streamlit as st

from database.db import SessionLocal, session_scope
from services import assessment_service, roadmap_service, user_service
from ui.components.sidebar import render_sidebar

st.set_page_config(page_title="Roadmap · Career Compass", page_icon="🧭",
                   layout="wide", initial_sidebar_state="expanded")
render_sidebar("Roadmap")
st.markdown('<p class="cc-header-eyebrow">LEARN WITH DIRECTION</p>'
            '<h1 class="cc-header-title">Your roadmap</h1>'
            '<p class="cc-header-subtitle">A focused path from your current skills to your target career.</p>',
            unsafe_allow_html=True)
user_id = st.session_state.get("user_id")
if type(user_id) is not int:
    st.info("Complete onboarding to load your roadmap.")
    st.page_link("pages/Onboarding.py", label="Go to Onboarding")
    st.stop()
try:
    with SessionLocal() as session:
        profile = user_service.get_user_profile(session, user_id)
        career_id = profile["target_career_id"]
        items = roadmap_service.get_user_roadmap(session, user_id, career_id) if career_id is not None else []
    supported = {item["skill_name"] for item in assessment_service.list_supported_assessments()}
except Exception:
    st.error("Could not load your roadmap. Check your profile and database, then try again.")
    st.page_link("pages/Onboarding.py", label="Go to Onboarding")
    st.stop()
if career_id is None:
    st.info("Choose a target career in Onboarding to see your roadmap.")
    st.page_link("pages/Onboarding.py", label="Go to Onboarding")
    st.stop()
with st.container(key="cc-card-roadmap-summary"):
    st.subheader(profile["target_career_name"])
    completed = sum(item["status"] == "completed" for item in items)
    st.caption(f"{completed} of {len(items)} displayed items completed")
    st.caption("Showing the service's current roadmap subset and relevant completion history.")
    if items:
        st.progress(completed / len(items))
if not items:
    st.info("No roadmap steps are currently returned for this career. Review your career profile for your latest progress.")
elif completed == len(items):
    st.success("All displayed roadmap items are complete.")
st.page_link("pages/my_career.py", label="View My Career")
st.page_link("pages/Dashboard.py", label="Return to Dashboard")

for item in items:
    key = item["item_key"]
    action = item["action_type"]
    with st.container(key=f"cc-card-roadmap-{key}"):
        st.markdown(f'<h3 class="cc-row-title">{escape(item["title"])}</h3>', unsafe_allow_html=True)
        st.write(item["reason"])
        st.caption(f"{item['skill_name']} · Action: {action} · Status: {item['status']}")
        st.caption(f"Item key: {key}")
        if item.get("latest_attempt_id") is not None:
            st.caption(f"Related assessment attempt: {item['latest_attempt_id']}")
        locked = item["status"] == "locked" or not item["prerequisites_met"]
        if locked:
            st.caption("Complete the prerequisites before starting this step.")
        if action in ("assess", "reassess"):
            if item["skill_name"] in supported and item["status"] != "completed":
                if st.button(item["title"], key=f"roadmap_assess_{key}", disabled=locked):
                    st.session_state["assessment_skill"] = item["skill_name"]
                    st.session_state.pop("assessment_attempt_id", None)
                    st.switch_page("pages/Assessment.py")
            elif item["skill_name"] not in supported:
                st.caption("An assessment is not available for this skill yet.")
        elif action in ("improve", "learn"):
            reopen = item["status"] == "completed"
            if st.button("Reopen" if reopen else "Mark complete", key=f"roadmap_toggle_{key}",
                         disabled=locked and not reopen):
                try:
                    with session_scope() as session:
                        current_profile = user_service.get_user_profile(session, user_id)
                        if current_profile["target_career_id"] != career_id:
                            raise ValueError("Your target career changed. Reload your roadmap.")
                        current_items = roadmap_service.get_user_roadmap(session, user_id, career_id)
                        current = next((row for row in current_items if row["item_key"] == key), None)
                        if (current is None or current["action_type"] not in ("improve", "learn")
                                or (current["status"] == "completed") != reopen
                                or (not reopen and (current["status"] == "locked" or not current["prerequisites_met"]))):
                            raise ValueError("This step changed. Reload your roadmap.")
                        mutation = (roadmap_service.mark_roadmap_item_incomplete if reopen
                                    else roadmap_service.mark_roadmap_item_completed)
                        mutation(session, user_id, key)
                except Exception:
                    st.error("Could not save this roadmap change. No changes were saved. Reload the page and try again.")
                else:
                    st.rerun()
