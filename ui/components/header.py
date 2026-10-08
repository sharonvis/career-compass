"""Reusable page header and account controls for logged-in pages."""

import streamlit as st

from ui.components import load_shared_styles


def render_header(title: str = "", subtitle: str = "", eyebrow: str = "") -> None:
    """Render the page heading with search and profile controls."""
    load_shared_styles()
    st.markdown('<div class="cc-layout-marker cc-header-marker" aria-hidden="true"></div>', unsafe_allow_html=True)

    heading, search, profile = st.columns([1, 0.08, 0.13], vertical_alignment="top")
    with heading:
        if eyebrow:
            st.markdown(f'<p class="cc-header-eyebrow">{eyebrow}</p>', unsafe_allow_html=True)
        if title:
            st.markdown(f'<h1 class="cc-header-title">{title}</h1>', unsafe_allow_html=True)
        if subtitle:
            st.markdown(f'<p class="cc-header-subtitle">{subtitle}</p>', unsafe_allow_html=True)
    with search:
        st.markdown('<span class="cc-search-icon" role="img" aria-label="Search"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.8" cy="10.8" r="6.8"></circle><path d="m16 16 5 5"></path></svg></span>', unsafe_allow_html=True)
    with profile:
        with st.popover("S", use_container_width=False):
            st.markdown("**Profile**")
            st.caption("Signed in")
