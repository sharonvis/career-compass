"""Shared navigation for the signed-in Career Compass pages."""

import base64
from pathlib import Path

import streamlit as st

from ui.components import load_shared_styles

NAV_ITEMS = (
    ("Dashboard", "pages/Dashboard.py", "dashboard"),
    ("My Career", "pages/my_career.py", "work_outline"),
    ("Roadmap", "pages/Roadmap.py", "route"),
    ("Opportunities", "pages/Opportunities.py", "work"),
    ("Applications", "pages/Applications.py", "description"),
    ("Evidence", "pages/Evidence.py", "badge"),
    ("Settings", "pages/Settings.py", "settings"),
)


def render_sidebar(selected: str = "Dashboard") -> None:
    """Render shared branding and page links, highlighting the current page."""
    if selected not in {item[0] for item in NAV_ITEMS}:
        raise ValueError(f"selected must be one of: {', '.join(item[0] for item in NAV_ITEMS)}")

    load_shared_styles()
    st.markdown('<div class="cc-layout-marker" aria-hidden="true"></div>', unsafe_allow_html=True)
    logo_path = Path(__file__).resolve().parents[2] / "assets" / "images" / "Careercompasslogodark.png"
    logo = base64.b64encode(logo_path.read_bytes()).decode("ascii")

    with st.sidebar:
        st.markdown(
            f'<div class="cc-sidebar-brand"><img src="data:image/png;base64,{logo}" alt="">'
            '<span>CAREER<br>COMPASS</span></div>',
            unsafe_allow_html=True,
        )
        for label, page, icon in NAV_ITEMS:
            if label == selected:
                st.markdown(
                    f'<div class="cc-nav-active"><span class="cc-nav-icon">{_icon(icon)}</span>{label}</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.page_link(page, label=label, icon=f":material/{icon}:")
def _icon(name: str) -> str:
    """Material Symbols token for the active static navigation item."""
    return f'<span class="material-symbols-rounded">{name}</span>'
