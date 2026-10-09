"""Career Compass onboarding backed by catalog and atomic user-service writes."""

import base64
import re

from sqlalchemy.exc import SQLAlchemyError
from database.db import SessionLocal, init_db, session_scope
from database.seed import seed_database
from services import user_service
from services.career_service import get_user_skill_states
from pathlib import Path

import streamlit as st

st.set_page_config(
    page_title="Career Compass | Onboarding",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="collapsed",
)

LEVELS = ("Not Known", "Beginner", "Intermediate", "Advanced")


def _valid_email(value):
    return bool(re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value.strip()))


def _set_target_career(career_id):
    st.session_state["onboarding_career_id"] = career_id


def _save_claim(skill_id):
    st.session_state["onboarding_claims"][skill_id] = st.session_state[f"onboarding_claim_{skill_id}"]


def _validate_submission(profile, career_id, skills, claims, careers):
    for field in ("name", "email", "degree", "branch"):
        if not isinstance(profile[field], str) or not profile[field].strip():
            raise ValueError(f"{field.capitalize()} is required.")
    if not _valid_email(profile["email"]):
        raise ValueError("Enter a valid email address.")
    if type(profile["year_of_study"]) is not int or not 1 <= profile["year_of_study"] <= 4:
        raise ValueError("Year of study must be from 1 to 4.")
    if career_id not in {career["career_id"] for career in careers}:
        raise ValueError("Select an available career.")
    if not skills:
        raise ValueError("This career has no required skills. Select another career.")
    for skill in skills:
        level = claims.get(skill["skill_id"])
        if type(level) is not int or not 0 <= level <= 3:
            raise ValueError(f"Choose a level from 0 to 3 for {skill['name']}.")


st.session_state.setdefault("onboarding_claims", {})
try:
    with SessionLocal() as session:
        careers = user_service.list_careers(session)
except SQLAlchemyError:
    careers = []
if not careers:
    st.info("The career catalog is not ready. Initialize the local database to continue.")
    if st.button("Initialize local database", key="initialize_onboarding_database"):
        try:
            init_db()
            with session_scope() as session:
                seed_database(session)
        except Exception:
            st.error("Database setup failed. Check local database access and try again.")
        else:
            st.rerun()
    st.stop()

ROOT = Path(__file__).resolve().parents[1]
css = (ROOT / "assets" / "onboarding.css").read_text(encoding="utf-8")
logo_path = ROOT / "assets" / "images" / "CareerCompassLogo.png"
logo = base64.b64encode(logo_path.read_bytes()).decode("ascii")

st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
st.markdown('<div class="cc-onboarding-marker" aria-hidden="true"></div>', unsafe_allow_html=True)
st.markdown(
    f"""
    <div class="cc-onboarding-topbar">
      <div class="cc-onboarding-brand">
        <img src="data:image/png;base64,{logo}" alt="">
        <span>CAREER COMPASS</span>
      </div>
      <span class="cc-onboarding-step">ONBOARDING</span>
    </div>
    """,
    unsafe_allow_html=True,
)

hero_copy, quick_card = st.columns([2.45, 1], vertical_alignment="center")
with hero_copy:
    st.markdown(
        """
        <p class="cc-onboarding-eyebrow">GET STARTED</p>
        <h1 class="cc-onboarding-title">Build your Career Compass.</h1>
        <p class="cc-onboarding-intro">Tell us where you are now, where you want to go, and how you rate your current skills.</p>
        """,
        unsafe_allow_html=True,
    )
with quick_card:
    st.markdown(
        """
        <div class="cc-quick-card">
          <strong><span>✦</span> 3 quick sections</strong>
          <p>About you · Target career · Claimed skills</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

with st.container(key="onboarding-about-card"):
    st.markdown(
        """
        <p class="cc-section-eyebrow">01 · ABOUT YOU</p>
        <h2 class="cc-section-title">Tell us where you're starting from.</h2>
        <p class="cc-section-description">These details help keep career requirements and opportunities relevant.</p>
        """,
        unsafe_allow_html=True,
    )
    # Email is rendered first so profile prefill occurs before profile widgets exist.
    if "onboarding_email" not in st.session_state and st.session_state.get("user_id"):
        try:
            with SessionLocal() as session:
                st.session_state["onboarding_email"] = user_service.get_user_profile(session, st.session_state["user_id"])["email"]
        except Exception:
            st.session_state["onboarding_email"] = ""
    st.text_input("Email", key="onboarding_email")
    email = st.session_state["onboarding_email"].strip()
    existing = None
    try:
        with SessionLocal() as session:
            if _valid_email(email):
                existing = user_service.get_user_by_email(session, email)
    except Exception:
        st.error("Could not load your profile. Check database access and try again.")
        st.stop()
    loaded_id = existing["user_id"] if existing else None
    if st.session_state.get("onboarding_loaded_user_id") != loaded_id:
        st.session_state["onboarding_claims"] = {}
        for key in list(st.session_state):
            if key.startswith("onboarding_claim_"):
                del st.session_state[key]
        st.session_state["onboarding_loaded_user_id"] = loaded_id
        for field in ("name", "degree", "branch"):
            st.session_state[f"onboarding_{field}"] = existing[field] if existing else ""
        st.session_state["onboarding_year"] = existing["year_of_study"] if existing else 1
        st.session_state["onboarding_career_id"] = existing["target_career_id"] if existing else careers[0]["career_id"]
    if st.session_state.get("onboarding_career_id") not in {c["career_id"] for c in careers}:
        st.session_state["onboarding_career_id"] = careers[0]["career_id"]
    for field in ("name", "degree", "branch"):
        st.session_state.setdefault(f"onboarding_{field}", existing[field] if existing else "")
    st.session_state.setdefault("onboarding_year", existing["year_of_study"] if existing else 1)
    if existing:
        st.info("Existing profile loaded. Profile details are read-only; only your career and skill claims will be updated.")
    left, right = st.columns(2, gap="large")
    with left:
        st.text_input("Full name", key="onboarding_name", disabled=existing is not None)
        st.text_input("Degree", key="onboarding_degree", disabled=existing is not None)
    with right:
        st.text_input("Branch", key="onboarding_branch", disabled=existing is not None)
        st.selectbox("Year of study", (1, 2, 3, 4), key="onboarding_year",
                     format_func=lambda year: f"Year {year}", disabled=existing is not None)

st.markdown('<div class="cc-onboarding-connector" aria-hidden="true"></div>', unsafe_allow_html=True)

with st.container(key="onboarding-career-card"):
    st.markdown(
        """
        <p class="cc-section-eyebrow">02 · TARGET CAREER</p>
        <h2 class="cc-section-title">What are you aiming for?</h2>
        <p class="cc-section-description">Choose one target for now. Switching careers later will not erase your progress.</p>
        """,
        unsafe_allow_html=True,
    )
    with st.container(key="onboarding-career-picker"):
        for index, career_record in enumerate(careers):
            career_id = career_record["career_id"]
            career = career_record["name"]
            description = career_record["description"] or ""
            selected = st.session_state["onboarding_career_id"] == career_id
            selected_key = "selected" if selected else "unselected"
            with st.container(key=f"target-career-card-{index}-{selected_key}"):
                selector, copy, marker = st.columns([0.055, 0.89, 0.055], vertical_alignment="center")
                with selector:
                    with st.container(key=f"target-career-control-{index}"):
                        st.button(
                            "●" if selected else "○",
                            key=f"target_career_select_{index}",
                            help=f"Select {career}",
                            on_click=_set_target_career,
                            args=(career_id,),
                        )
                with copy:
                    st.markdown(
                        f'<div class="cc-career-option-copy"><strong>{career}</strong>'
                        f'<span>{description}</span></div>',
                        unsafe_allow_html=True,
                    )
                with marker:
                    if selected:
                        st.markdown('<span class="cc-career-option-star">✦</span>', unsafe_allow_html=True)

st.markdown('<div class="cc-onboarding-connector" aria-hidden="true"></div>', unsafe_allow_html=True)

try:
    with SessionLocal() as session:
        skills = user_service.list_career_skills(session, st.session_state["onboarding_career_id"])
        saved = get_user_skill_states(session, existing["user_id"], [s["skill_id"] for s in skills]) if existing else {}
except Exception:
    st.error("Could not load career skills. Please try again.")
    st.stop()
for skill in skills:
    skill_id = skill["skill_id"]
    st.session_state["onboarding_claims"].setdefault(skill_id, saved.get(skill_id, {}).get("claimed_level", 0))
    st.session_state.setdefault(f"onboarding_claim_{skill_id}", st.session_state["onboarding_claims"][skill_id])
levels = LEVELS
with st.container(key="onboarding-skills-card"):
    st.markdown(
        """
        <p class="cc-section-eyebrow">03 · CLAIM YOUR SKILLS</p>
        <h2 class="cc-section-title">How strong do you think you are?</h2>
        <p class="cc-section-description">This is your self-rating. Assessments later create your demonstrated level.</p>
        """,
        unsafe_allow_html=True,
    )
    skill_heading, level_heading = st.columns([1.12, 1], gap="medium")
    with level_heading:
        heading_cols = st.columns(4, gap="small")
        for col, level in zip(heading_cols, levels):
            with col:
                st.markdown(f'<p class="cc-level-heading">{level}</p>', unsafe_allow_html=True)
    for skill_record in skills:
        skill = skill_record["name"]
        skill_id = skill_record["skill_id"]
        skill_col, choices_col = st.columns([1.12, 1], gap="medium", vertical_alignment="center")
        with skill_col:
            st.markdown(f'<p class="cc-skill-name">{skill}</p>', unsafe_allow_html=True)
        with choices_col:
            st.radio(
                f"Claimed level for {skill}",
                options=(0, 1, 2, 3),
                format_func=lambda level: LEVELS[level],
                horizontal=True,
                key=f"onboarding_claim_{skill_id}",
                on_change=_save_claim,
                args=(skill_id,),
                label_visibility="collapsed",
            )
    st.markdown(
        '<div class="cc-claim-note"><span>✦</span> These are claims, not scores. Your assessments will determine demonstrated levels.</div>',
        unsafe_allow_html=True,
    )

with st.container(key="onboarding-cta"):
    cta_text, cta_button = st.columns([1.5, 0.55], vertical_alignment="center")
    with cta_text:
        st.markdown('<p class="cc-cta-title">Ready to see your Career Compass?</p>', unsafe_allow_html=True)
    with cta_button:
        if st.button("Build My Career Compass  →", type="primary", key="build_career_compass", width="stretch"):
            profile = dict(name=st.session_state["onboarding_name"].strip(), email=email,
                           degree=st.session_state["onboarding_degree"].strip(),
                           branch=st.session_state["onboarding_branch"].strip(),
                           year_of_study=st.session_state["onboarding_year"])
            if existing:
                profile = {key: existing[key] for key in profile}
            career_id = st.session_state["onboarding_career_id"]
            claims = dict(st.session_state["onboarding_claims"])
            try:
                _validate_submission(profile, career_id, skills, claims, careers)
                with session_scope() as session:
                    user = user_service.get_user_by_email(session, email)
                    if user is None:
                        user = user_service.create_user(session, **profile)
                    user_id = user["user_id"]
                    current_skills = user_service.list_career_skills(session, career_id)
                    if current_skills != skills:
                        raise ValueError("Career requirements changed. Reload and review your claims.")
                    _validate_submission(profile, career_id, current_skills, claims, user_service.list_careers(session))
                    user_service.set_target_career(session, user_id, career_id)
                    for skill in current_skills:
                        user_service.set_skill_claim(session, user_id, skill["skill_id"], claims[skill["skill_id"]])
            except ValueError as exc:
                st.error(str(exc))
            except Exception:
                st.error("Could not save your Career Compass. No changes were saved. Please try again.")
            else:
                st.session_state["user_id"] = user_id
                st.switch_page("pages/Dashboard.py")
