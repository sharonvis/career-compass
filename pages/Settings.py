"""Static account preferences screen."""

import streamlit as st

from ui.components.header import render_header
from ui.components.sidebar import render_sidebar

st.set_page_config(page_title="Settings · Career Compass", page_icon="🧭", layout="wide", initial_sidebar_state="expanded")
render_sidebar("Settings")
render_header("Settings", "Manage your profile and how Career Compass keeps you informed.", "YOUR ACCOUNT")

st.markdown('<div class="cc-settings-header-gap"></div>', unsafe_allow_html=True)
profile_col, preferences_col = st.columns([1.15, 1], gap="large")
with profile_col:
    with st.container(key="cc-card-settings-profile"):
        st.markdown('<p class="cc-section-kicker">PROFILE</p><h2 class="cc-section-title">Your details</h2><p class="cc-section-copy">Keep your profile current so your recommendations stay relevant.</p>', unsafe_allow_html=True)
        st.text_input("Full name", value="Alex Morgan", key="settings_name")
        st.text_input("Email address", value="alex.morgan@example.com", key="settings_email")
        st.text_input("College or university", value="Northstar University", key="settings_school")
        st.selectbox("Year of study", ("1st Year", "2nd Year", "3rd Year", "4th Year"), index=2, key="settings_year")
        st.button("Save profile", type="primary", key="save_profile")
with preferences_col:
    with st.container(key="cc-card-settings-preferences"):
        st.markdown('<p class="cc-section-kicker">PREFERENCES</p><h2 class="cc-section-title">Stay in the loop.</h2><p class="cc-section-copy">Choose which updates you would like to see.</p>', unsafe_allow_html=True)
        st.toggle("Weekly progress summary", value=True, key="settings_weekly_summary")
        st.caption("A short recap of your assessments and roadmap activity.")
        st.markdown('<div class="cc-divider"></div>', unsafe_allow_html=True)
        st.toggle("Opportunity recommendations", value=True, key="settings_opportunity_updates")
        st.caption("Get a heads up when roles match your career interests.")
        st.markdown('<div class="cc-divider"></div>', unsafe_allow_html=True)
        st.selectbox("Email frequency", ("Weekly", "Monthly", "Only important updates"), key="settings_frequency")
        st.button("Save preferences", type="primary", key="save_preferences")
