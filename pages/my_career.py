"""Career requirements and user evidence read from backend summaries."""
from html import escape

import streamlit as st

from database.db import SessionLocal, session_scope
from services import assessment_service, career_service, user_service
from ui.components.sidebar import render_sidebar

LEVELS = ("Not Known", "Beginner", "Intermediate", "Advanced")
st.set_page_config(page_title="My Career · Career Compass", page_icon="🧭",
                   layout="wide", initial_sidebar_state="expanded")
render_sidebar("My Career")
user_id = st.session_state.get("user_id")
if type(user_id) is not int:
    st.info("Complete onboarding to load your career profile.")
    st.page_link("pages/Onboarding.py", label="Go to Onboarding")
    st.stop()

try:
    with SessionLocal() as session:
        profile = user_service.get_user_profile(session, user_id)
        careers = user_service.list_careers(session)
        career_id = profile["target_career_id"]
        summary = career_service.get_user_career_summary(session, user_id, career_id) if career_id is not None else None
except Exception:
    st.error("Could not load your career profile. Check your profile and database, then try again.")
    st.page_link("pages/Onboarding.py", label="Go to Onboarding")
    st.stop()

st.markdown('<p class="cc-header-eyebrow">YOUR CAREER COMPASS</p>'
            '<h1 class="cc-header-title">My Career</h1>'
            f'<p class="cc-header-subtitle">{escape(profile["name"])}, explore your career requirements and progress.</p>',
            unsafe_allow_html=True)
catalog = {career["career_id"]: career for career in careers}
if not catalog:
    st.info("No careers are available. Return to Onboarding to set up the catalog.")
    st.page_link("pages/Onboarding.py", label="Go to Onboarding")
    st.stop()

top_left, top_right = st.columns([1, .35], vertical_alignment="center")
with top_left:
    st.markdown(f'<h2 class="cc-section-title" style="font-size:30px">{escape(profile["target_career_name"] or "Choose a target career")}</h2>', unsafe_allow_html=True)
    description = catalog.get(career_id, {}).get("description")
    if description:
        st.markdown(f'<p class="cc-section-copy">{escape(description)}</p>', unsafe_allow_html=True)
with top_right:
    with st.form("career_switch"):
        selected_id = st.selectbox("Target career", list(catalog),
                                   index=list(catalog).index(career_id) if career_id in catalog else 0,
                                   format_func=lambda value: catalog[value]["name"], key="career_switch_id")
        change = st.form_submit_button("Change career", icon=":material/swap_horiz:", width="stretch")
    if change:
        try:
            with session_scope() as session:
                available = {career["career_id"] for career in user_service.list_careers(session)}
                if selected_id not in available:
                    raise ValueError("Select an available career.")
                user_service.set_target_career(session, user_id, selected_id)
        except Exception:
            st.error("Could not change career. No changes were saved. Please try again.")
        else:
            st.rerun()

if summary is None:
    st.info("Choose a target career above to see your requirements.")
    st.stop()

st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
for column, label, value, key in zip(
    st.columns(3, gap="medium"),
    ("Claimed Readiness", "Effective Readiness", "Assessment Coverage"),
    (summary["claimed_readiness"], summary["effective_readiness"], summary["assessment_coverage"]),
    ("overview", "count", "progress"),
):
    with column:
        with st.container(key=f"cc-card-career-{key}"):
            st.metric(label, f"{value:.1%}")
st.caption("Assessment coverage is weighted by career skill importance. Effective readiness includes discounted unassessed claims.")
st.markdown('<p class="cc-section-kicker">CAREER REQUIREMENTS</p><h2 class="cc-section-title">Core skills</h2>', unsafe_allow_html=True)
st.caption(f"{len(summary['skills'])} required skills")
with st.container(key="cc-card-career-skills"):
    supported = {item["skill_name"] for item in assessment_service.list_supported_assessments()}
    for skill in summary["skills"]:
        columns = st.columns([1.5, 1, 1.15, .8, .65], gap="small", vertical_alignment="center")
        with columns[0]:
            st.markdown(f'<p class="cc-row-title">{escape(skill["name"])}</p>', unsafe_allow_html=True)
            if skill["latest_attempt_id"] is not None:
                st.caption(f"Latest completed attempt: #{skill['latest_attempt_id']}")
        with columns[1]:
            st.write(f"Required: {LEVELS[skill['required_level']]}")
        with columns[2]:
            st.write(f"Claimed: {LEVELS[skill['claimed_level']]}")
            demonstrated = skill["demonstrated_level"]
            label = "Not assessed" if demonstrated is None else "Not Demonstrated" if demonstrated == 0 else LEVELS[demonstrated]
            st.write(f"Demonstrated: {label}")
        with columns[3]:
            st.write("Unassessed" if demonstrated is None else "Assessed")
            st.caption("Confirmed gap: unknown" if skill["gap"] is None else f"Confirmed gap: {skill['gap']}")
            st.caption("Prerequisites met" if skill["prerequisites_met"] else "Blocked by prerequisites")
            for prerequisite in skill["prerequisites"]:
                st.caption(f"Requires {prerequisite['skill_name']}: {LEVELS[prerequisite['minimum_level']]}")
        with columns[4]:
            if skill["assessable"] and skill["name"] in supported:
                if st.button("Assess" if demonstrated is None else "Reassess",
                             key=f"career_skill_{skill['skill_id']}", width="stretch"):
                    st.session_state["assessment_skill"] = skill["name"]
                    st.session_state.pop("assessment_attempt_id", None)
                    st.switch_page("pages/Assessment.py")
            else:
                st.caption("Assessment not available for this skill.")
        st.markdown('<div class="cc-divider" style="margin:8px 0"></div>', unsafe_allow_html=True)
