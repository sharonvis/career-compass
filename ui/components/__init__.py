"""Shared Streamlit components for the logged-in Career Compass UI."""

from pathlib import Path

import streamlit as st


def load_shared_styles() -> None:
    """Load the shared stylesheet once per Streamlit page run."""
    css_path = Path(__file__).resolve().parents[2] / "assets" / "styles.css"
    css = css_path.read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


__all__ = ["load_shared_styles"]
