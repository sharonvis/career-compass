"""Reusable sidebar navigation for logged-in Career Compass pages."""

import base64
from pathlib import Path

import streamlit as st

from ui.components import load_shared_styles

NAV_ITEMS = (
    "Dashboard",
    "My Career",
    "Roadmap",
    "Opportunities",
    "Applications",
    "Settings",
)
NAV_ICONS = {
    "Dashboard": "▦",
    "My Career": "♙",
    "Roadmap": "⌘",
    "Opportunities": "◇",
    "Applications": "▧",
    "Settings": "⚙",
}


def render_sidebar(selected: str = "Dashboard") -> str:
    """Render the shared navigation and return the selected destination."""
    if selected not in NAV_ITEMS:
        raise ValueError(f"selected must be one of: {', '.join(NAV_ITEMS)}")

    load_shared_styles()
    st.markdown('<div class="cc-layout-marker" aria-hidden="true"></div>', unsafe_allow_html=True)
    logo_path = Path(__file__).resolve().parents[2] / "assets" / "images" / "Careercompasslogodark.png"
    logo = base64.b64encode(logo_path.read_bytes()).decode("ascii")

    with st.sidebar:
        st.markdown(
            f'<div class="cc-sidebar-brand">'
            f'<img src="data:image/png;base64,{logo}" alt="">'
            f'<span>CAREER<br>COMPASS</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
        destination = st.radio(
            "Primary navigation",
            options=NAV_ITEMS,
            format_func=lambda item: f"{NAV_ICONS[item]}  {item}",
            index=NAV_ITEMS.index(selected),
            label_visibility="collapsed",
            key="cc_primary_navigation",
        )
    return destination
