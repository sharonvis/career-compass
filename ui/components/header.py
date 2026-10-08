"""Shared page heading and account controls."""

import streamlit as st

from ui.components import load_shared_styles


def render_header(title: str = "", subtitle: str = "", eyebrow: str = "") -> None:
    """Render the signed-in page title, compact search, and profile menu."""
    load_shared_styles()
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
            with st.popover("S", help="Open account menu"):
                st.markdown("**Sharon**")
                st.caption("Student account")
            st.markdown('<span class="cc-header-dropdown-arrow" aria-hidden="true">⌄</span>', unsafe_allow_html=True)
