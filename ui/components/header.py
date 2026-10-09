"""Shared page heading and account controls."""

import streamlit as st
from html import escape

from database import db
from services.user_service import get_user_profile

from ui.components import load_shared_styles


def render_header(title: str = "", subtitle: str = "", eyebrow: str = "") -> None:
    """Render the signed-in page title, compact search, and profile menu."""
    load_shared_styles()
    name = "Guest"
    has_profile = False
    user_id = st.session_state.get("user_id")
    if type(user_id) is int:
        try:
            with db.SessionLocal() as session:
                name = get_user_profile(session, user_id)["name"]
                has_profile = True
        except Exception:
            name = "Guest"
    st.markdown('<div class="cc-layout-marker cc-header-marker" aria-hidden="true"></div>', unsafe_allow_html=True)
    heading, controls = st.columns([1, 0.16], vertical_alignment="top")
    with heading:
        if eyebrow:
            st.markdown(f'<p class="cc-header-eyebrow">{eyebrow}</p>', unsafe_allow_html=True)
        if title:
            st.markdown(f'<h1 class="cc-header-title">{title}</h1>', unsafe_allow_html=True)
        if subtitle:
            st.markdown(f'<p class="cc-header-subtitle">{subtitle}</p>', unsafe_allow_html=True)
    with controls:
        with st.container(
            key="cc-header-controls",
            horizontal=True,
            wrap=False,
            horizontal_alignment="right",
            vertical_alignment="center",
            gap="small",
        ):
            with st.container(key="cc-header-search"):
                with st.popover("\u200b", icon=":material/search:", help="Search Career Compass"):
                    st.text_input(
                        "Search Career Compass",
                        placeholder="Search anything...",
                        label_visibility="collapsed",
                        key="cc_global_search",
                    )
            with st.popover(name[:1].upper() or "?", help="Open account menu"):
                st.markdown(f'<strong>{escape(name)}</strong>', unsafe_allow_html=True)
                st.caption("Student account" if has_profile else "Complete onboarding to set up your profile")
            st.markdown('<span class="cc-header-dropdown-arrow" aria-hidden="true">⌄</span>', unsafe_allow_html=True)
