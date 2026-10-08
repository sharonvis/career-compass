"""Static learning roadmap screen."""

import streamlit as st

from ui.components.header import render_header
from ui.components.sidebar import render_sidebar

st.set_page_config(page_title="Roadmap · Career Compass", page_icon="🧭", layout="wide", initial_sidebar_state="expanded")
render_sidebar("Roadmap")
render_header("Your roadmap", "A focused path from your current skills to your target career.", "LEARN WITH DIRECTION")

st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
summary, target = st.columns([1.4, 1], gap="large")
with summary:
    with st.container(key="cc-card-roadmap-summary"):
        st.markdown('<p class="cc-section-kicker">YOUR LEARNING PLAN</p><h2 class="cc-section-title">Data analyst foundations</h2><p class="cc-section-copy">A practical sequence built around your current skill profile.</p>', unsafe_allow_html=True)
        st.markdown(
            '<div class="cc-roadmap-progress-block">'
            '<p class="cc-roadmap-progress-label">2 of 6 steps complete</p>'
            '<div class="cc-roadmap-progress-track"><div class="cc-roadmap-progress-fill"></div></div>'
            '</div>',
            unsafe_allow_html=True,
        )
with target:
    with st.container(key="cc-card-roadmap-target"):
        st.markdown('<p class="cc-stat-label">ESTIMATED PACE</p><div class="cc-stat-value">4 weeks</div><p class="cc-stat-foot">About 3 hours per week</p>', unsafe_allow_html=True)

st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
st.markdown('<p class="cc-section-kicker">YOUR NEXT STEPS</p><h2 class="cc-section-title">Keep the momentum going.</h2>', unsafe_allow_html=True)
steps = (
    ("01", "Assess your SQL level", "Complete a short check of queries, joins, and filtering.", "Completed", "cc-chip-green", "check_circle"),
    ("02", "Practice SQL joins", "Work through a small dataset and combine related tables.", "In progress", "cc-chip-coral", "play_circle"),
    ("03", "Explore a dataset with Python", "Load, clean, and summarize a dataset with pandas.", "Up next", "", "radio_button_unchecked"),
    ("04", "Review statistics essentials", "Refresh distributions, averages, and variation.", "Planned", "", "radio_button_unchecked"),
)
for number, title, detail, status, chip, icon in steps:
    with st.container(key=f"cc-card-roadmap-step-{number}"):
        icon_col, text_col, status_col = st.columns([.12, 1, .35], vertical_alignment="center")
        with icon_col:
            st.markdown(f'<span class="material-symbols-rounded" style="font-size:25px;color:{"#51836e" if status == "Completed" else "#f25534" if status == "In progress" else "#aaa39c"}">{icon}</span>', unsafe_allow_html=True)
        with text_col:
            st.markdown(f'<p class="cc-row-title">{number} &nbsp; {title}</p><p class="cc-section-copy">{detail}</p>', unsafe_allow_html=True)
        with status_col:
            st.markdown(f'<span class="cc-chip {chip}">{status}</span>', unsafe_allow_html=True)
