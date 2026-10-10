"""Supported profile fields persisted through the user service."""
from pathlib import Path
from html import escape
import base64
import streamlit as st
from database.db import SessionLocal, session_scope
from services import user_service
from ui.components.header import render_header
from ui.components.sidebar import render_sidebar

st.set_page_config(page_title="Settings · Career Compass", page_icon="🧭", layout="wide", initial_sidebar_state="expanded")
render_sidebar("Settings")
render_header()
st.markdown("<style>" + (Path(__file__).resolve().parents[1] / "assets/settings.css").read_text(encoding="utf-8") + "</style>", unsafe_allow_html=True)
@st.cache_data
def settings_art(path, modified):
    return base64.b64encode(Path(path).read_bytes()).decode("ascii")
art_path = Path(__file__).resolve().parents[1] / "assets/images/setting.png"
art = settings_art(str(art_path), art_path.stat().st_mtime_ns)
st.markdown(f'<style>.cc-set-hero{{background-image:url("data:image/png;base64,{art}")}}</style>', unsafe_allow_html=True)
st.markdown('<div class="cc-set-hero"><div class="cc-set-hero-copy"><p>YOUR ACCOUNT</p><h1>Settings</h1><div>Manage your Career Compass profile and preferences.</div></div></div>', unsafe_allow_html=True)
user_id = st.session_state.get("user_id")
if type(user_id) is not int:
    st.info("Complete onboarding to manage your profile.")
    st.page_link("pages/Onboarding.py", label="Go to Onboarding")
    st.stop()
try:
    with SessionLocal() as session:
        profile = user_service.get_user_profile(session, user_id)
except Exception:
    st.error("Could not load your profile. Check your profile and database, then try again.")
    st.page_link("pages/Onboarding.py", label="Go to Onboarding")
    st.stop()
notice = st.session_state.pop("settings_notice", None)
if notice:
    st.success(notice)
# Persisted values in form keys refresh normalized values and changed users.
version = f"{user_id}_{profile['name']}_{profile['degree']}_{profile['branch']}_{profile['year_of_study']}"
with st.container(key="cc-set-panels"):
    with st.container(key="cc-card-settings-profile"):
        st.markdown('<div class="cc-set-panel-heading"><span aria-hidden="true">&#9786;</span><div><h2>Your details</h2><p>Keep your profile information up to date. This helps us personalize your experience.</p></div></div>', unsafe_allow_html=True)
        with st.form(f"settings_profile_{version}"):
            first, second = st.columns(2, gap="medium")
            with first:
                name = st.text_input("Full name", value=profile["name"], key=f"settings_name_{version}")
            with second:
                st.markdown(f'<div class="cc-set-email"><label>Email address</label><div>{escape(profile["email"])} <small>(read-only)</small></div></div>', unsafe_allow_html=True)
            first, second = st.columns(2, gap="medium")
            with first:
                degree = st.text_input("Degree", value=profile["degree"], key=f"settings_degree_{version}")
            with second:
                branch = st.text_input("Branch", value=profile["branch"], key=f"settings_branch_{version}")
            first, second = st.columns(2, gap="medium")
            with first:
                year = st.selectbox("Year of study", (1, 2, 3, 4), index=profile["year_of_study"] - 1 if profile["year_of_study"] in (1, 2, 3, 4) else 0, key=f"settings_year_{version}")
            with st.container(key="cc-set-form-actions", horizontal=True, vertical_alignment="center", gap="small"):
                submitted = st.form_submit_button("Save profile")
                st.page_link("pages/Evidence.py", label="Manage evidence and credentials")
        if submitted:
            try:
                with session_scope() as session:
                    user_service.update_user_profile(session, user_id, name=name, degree=degree, branch=branch, year_of_study=year)
            except ValueError as error:
                st.error(f"Could not save profile: {error}")
            except Exception:
                st.error("Could not save profile. No changes were saved. Please try again.")
            else:
                st.session_state["settings_notice"] = "Profile saved."
                st.rerun()
    with st.container(key="cc-set-preferences"):
        st.markdown('<div class="cc-set-panel-heading"><span aria-hidden="true">&#9881;</span><div><h2>Preferences &amp; actions</h2><p>Manage your experience and account settings.</p></div></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="cc-set-option"><span aria-hidden="true">&#9678;</span><div><strong>Target career</strong><p>{escape(profile["target_career_name"] or "Choose your career direction")}</p></div></div>', unsafe_allow_html=True)
        st.page_link("pages/my_career.py", label="Manage target career")
        st.markdown('<div class="cc-set-option"><span aria-hidden="true">&#9826;</span><div><strong>Notifications</strong><p>Notification preferences are not available yet.</p></div></div><div class="cc-set-option"><span aria-hidden="true">&#9673;</span><div><strong>Profile visibility</strong><p>Recruiter profile sharing is not available yet.</p></div></div><div class="cc-set-option"><span aria-hidden="true">&#9881;</span><div><strong>Account information</strong><p>Your email is read-only. Profile changes are saved with the form on the left.</p></div></div>', unsafe_allow_html=True)
