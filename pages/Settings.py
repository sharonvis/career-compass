"""Supported profile fields persisted through the user service."""
import streamlit as st
from database.db import SessionLocal, session_scope
from services import user_service
from ui.components.header import render_header
from ui.components.sidebar import render_sidebar

st.set_page_config(page_title="Settings · Career Compass", page_icon="🧭", layout="wide", initial_sidebar_state="expanded")
render_sidebar("Settings")
render_header("Settings", "Manage your Career Compass profile.", "YOUR ACCOUNT")
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
with st.container(key="cc-card-settings-profile"):
    st.subheader("Your details")
    st.caption(f"Email: {profile['email']} (read-only)")
    with st.form(f"settings_profile_{version}"):
        name = st.text_input("Full name", value=profile["name"], key=f"settings_name_{version}")
        degree = st.text_input("Degree", value=profile["degree"], key=f"settings_degree_{version}")
        branch = st.text_input("Branch", value=profile["branch"], key=f"settings_branch_{version}")
        year = st.selectbox("Year of study", (1, 2, 3, 4), index=profile["year_of_study"] - 1 if profile["year_of_study"] in (1, 2, 3, 4) else 0, key=f"settings_year_{version}")
        submitted = st.form_submit_button("Save profile")
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
st.page_link("pages/Evidence.py", label="Manage evidence and credentials")
