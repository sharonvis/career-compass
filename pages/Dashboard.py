"""Read-only dashboard projections from existing backend services."""
from html import escape

import streamlit as st

from database.db import SessionLocal
from services import (application_service, assessment_service, career_service, opportunity_service,
                      progress_service, roadmap_service, user_service)
from ui.components.sidebar import render_sidebar

st.set_page_config(page_title="Dashboard · Career Compass", page_icon="🧭",
                   layout="wide", initial_sidebar_state="expanded")
render_sidebar("Dashboard")
user_id = st.session_state.get("user_id")
if type(user_id) is not int:
    st.info("Complete onboarding to load your Career Compass.")
    st.page_link("pages/Onboarding.py", label="Go to Onboarding")
    st.stop()

try:
    with SessionLocal() as session:
        profile = user_service.get_user_profile(session, user_id)
        career_id = profile["target_career_id"]
        if career_id is None:
            st.info("Choose a target career in Onboarding to load your dashboard.")
            st.page_link("pages/Onboarding.py", label="Go to Onboarding")
            st.stop()
        summary = career_service.get_user_career_summary(session, user_id, career_id)
        roadmap = roadmap_service.get_user_roadmap(session, user_id, career_id)
        opportunities = opportunity_service.get_ranked_opportunities(session, user_id, career_id, limit=3)
        counts = application_service.get_application_status_counts(session, user_id)
        activity = progress_service.list_recent_progress_events(session, user_id, limit=5)
except Exception:
    st.error("Could not load your dashboard. Check your profile and database, then try again.")
    st.page_link("pages/Onboarding.py", label="Go to Onboarding")
    st.stop()

# Preserve the heading styles without the shared header's demo account.
st.markdown('<p class="cc-header-eyebrow">YOUR CAREER COMPASS</p>'
            f'<h1 class="cc-header-title">{escape(profile["name"])}</h1>'
            '<p class="cc-header-subtitle">Here’s your next step toward the future you want.</p>',
            unsafe_allow_html=True)
st.markdown("<div class='cc-dashboard-gap'></div>", unsafe_allow_html=True)
hero_action, target_career = st.columns([1.98, 1], gap="small")
with hero_action:
    with st.container(key="dashboard-hero-next-action"):
        st.markdown('<span class="cc-section-kicker">NEXT ACTION</span>', unsafe_allow_html=True)
        action = summary["next_action"]
        if action is None:
            st.success("You’re up to date: no next action is currently recommended.")
        else:
            st.markdown(f'<h2 class="cc-dashboard-hero-title">{escape(action["action_type"].capitalize())} '
                        f'{escape(action["skill_name"])}</h2>', unsafe_allow_html=True)
            if action["action_type"] == "assess":
                supported = {item["skill_name"] for item in assessment_service.list_supported_assessments()}
                if action["skill_name"] in supported:
                    if st.button("Start Assessment", key="dashboard_start_assessment"):
                        st.session_state["assessment_skill"] = action["skill_name"]
                        st.session_state.pop("assessment_attempt_id", None)
                        st.switch_page("pages/Assessment.py")
                else:
                    st.caption("Assessment is not available for this skill.")
            elif action["action_type"] in {"improve", "learn"}:
                st.caption("See the current roadmap preview below for learning guidance.")
with target_career:
    with st.container(key="dashboard-hero-career"):
        st.markdown('<span class="cc-dashboard-label">YOUR TARGET CAREER</span>'
                    f'<h2 class="cc-dashboard-career-title">{escape(summary["career_name"])}</h2>',
                    unsafe_allow_html=True)
        st.page_link("pages/my_career.py", label="View My Career")

st.markdown("<div class='cc-dashboard-gap cc-gap-small'></div>", unsafe_allow_html=True)
metrics = (
    ("Claimed Readiness", summary["claimed_readiness"], "claimed"),
    ("Effective Readiness", summary["effective_readiness"], "demonstrated"),
    ("Assessment Coverage", summary["assessment_coverage"], "coverage"),
)
for col, (label, value, key) in zip(st.columns(3, gap="small"), metrics):
    with col:
        with st.container(key=f"dashboard-metric-{key}"):
            st.metric(label, f"{value:.1%}")
st.caption("Assessment coverage is weighted by career skill importance. Effective readiness includes discounted unassessed claims.")

st.markdown("<div class='cc-dashboard-gap cc-gap-small'></div>", unsafe_allow_html=True)
gaps_card, roadmap_card = st.columns([.94, 1.06], gap="small")
with gaps_card:
    with st.container(key="dashboard-important-gaps"):
        st.markdown('<div class="cc-dashboard-section-heading"><h2>Confirmed Gaps</h2></div>', unsafe_allow_html=True)
        if not summary["confirmed_gaps"]:
            st.info("No confirmed skill gaps. Unassessed skills are not confirmed gaps.")
        for number, gap in enumerate(summary["confirmed_gaps"], 1):
            st.markdown(f'<div class="cc-gap-row"><span class="cc-gap-number">{number}</span>'
                        f'<b>{escape(gap["skill_name"])}</b><span class="cc-gap-status coral">'
                        f'Gap: {gap["gap"]}</span></div>', unsafe_allow_html=True)
with roadmap_card:
    with st.container(key="dashboard-current-roadmap"):
        st.markdown('<div class="cc-dashboard-section-heading"><h2>Current Roadmap</h2></div>', unsafe_allow_html=True)
        if not roadmap:
            st.info("No roadmap items are currently recommended.")
        else:
            completed = sum(item["status"] == "completed" for item in roadmap)
            st.caption(f"{completed} of {len(roadmap)} displayed items completed")
        for item in roadmap:
            state = "done" if item["status"] == "completed" else "active" if item["status"] == "current" else ""
            st.markdown(f'<div class="cc-roadmap-step {state}"><span>{escape(item["title"])}</span>'
                        f' — {escape(item["status"].replace("_", " "))}</div>', unsafe_allow_html=True)
            st.caption(item["reason"])

st.markdown("<div class='cc-dashboard-gap cc-gap-small'></div>", unsafe_allow_html=True)
application_card, opportunity_card, activity_card = st.columns(3, gap="small")
with application_card:
    with st.container(key="dashboard-applications"):
        st.markdown('<div class="cc-bottom-card-heading"><b>Applications</b></div>', unsafe_allow_html=True)
        for status, count in counts.items():
            st.write(f"{status.capitalize()}: {count}")
with opportunity_card:
    with st.container(key="dashboard-recommended-opportunity"):
        st.markdown('<div class="cc-bottom-card-heading"><b>Recommended Opportunities</b></div>', unsafe_allow_html=True)
        if not opportunities:
            st.info("No matching opportunities available yet.")
        for opportunity in opportunities:
            st.markdown(f'<p class="cc-row-title">{escape(opportunity["title"])}</p>'
                        f'<p>{escape(opportunity["company"])}</p>', unsafe_allow_html=True)
            st.caption(f"{opportunity['match_band'].replace('_', ' ').title()} match")
            if opportunity["location"]:
                st.caption(opportunity["location"])
            if opportunity["deadline"]:
                st.caption(f"Deadline: {opportunity['deadline'].isoformat()}")
with activity_card:
    with st.container(key="dashboard-recent-activity"):
        st.markdown('<div class="cc-bottom-card-heading"><b>Recent Activity</b></div>', unsafe_allow_html=True)
        if not activity:
            st.info("No recent activity yet.")
        for event in activity:
            st.write(event["description"] or event["event_type"].replace("_", " "))
            st.caption(event["created_at"].strftime("%d %b %Y, %H:%M UTC"))
