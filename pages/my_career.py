"""Career detail and skill progress, using static sample data."""

import streamlit as st

from ui.components.header import render_header
from ui.components.sidebar import render_sidebar

st.set_page_config(page_title="My Career · Career Compass", page_icon="🧭", layout="wide", initial_sidebar_state="expanded")
render_sidebar("My Career")
render_header("My Career", "Explore the skills for your target career and track your progress.", "YOUR CAREER COMPASS")

top_left, top_right = st.columns([1, 0.35], vertical_alignment="center")
with top_left:
    st.markdown('<h2 class="cc-section-title" style="font-size:30px">Data Analyst</h2>', unsafe_allow_html=True)
    st.markdown('<p class="cc-section-copy">Turn data into useful insights that help solve real world problems.</p>', unsafe_allow_html=True)
with top_right:
    st.button("Change career", icon=":material/swap_horiz:", key="change_career", width="stretch")

st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
overview, skills_count, progress = st.columns(3, gap="medium")
with overview:
    with st.container(key="cc-card-career-overview"):
        st.markdown('<p class="cc-stat-label">CAREER OVERVIEW</p><p class="cc-section-copy">Data analysts collect, clean, and interpret information to support better decisions.</p>', unsafe_allow_html=True)
with skills_count:
    with st.container(key="cc-card-career-count"):
        st.markdown('<p class="cc-stat-label">KEY SKILLS</p><div class="cc-stat-value">6</div><p class="cc-stat-foot">to focus on</p>', unsafe_allow_html=True)
with progress:
    with st.container(key="cc-card-career-progress"):
        st.markdown('<p class="cc-stat-label">ASSESSMENT COVERAGE</p><div class="cc-stat-value">2 of 6</div><p class="cc-stat-foot">skills assessed</p>', unsafe_allow_html=True)

st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
st.markdown('<p class="cc-section-kicker">CAREER REQUIREMENTS</p><h2 class="cc-section-title">Core skills</h2><p class="cc-section-copy">See where you are today and which skills could use more practice.</p>', unsafe_allow_html=True)
st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
with st.container(key="cc-card-career-skills"):
    header_columns = st.columns([1.5, 1, 1.15, .8, .65], gap="small")
    for column, label in zip(header_columns, ("Skill", "Required", "Your level", "Status", "")):
        with column:
            st.markdown(f'<p class="cc-career-table-header">{label}</p>', unsafe_allow_html=True)
    st.markdown('<div class="cc-divider" style="margin:0 0 8px"></div>', unsafe_allow_html=True)
    skills = (("SQL", "Intermediate", "Beginner", "Gap", "Assess"), ("Python", "Intermediate", "Intermediate", "On track", "Review"), ("Statistics", "Intermediate", "Not assessed", "To assess", "Assess"), ("Data visualisation", "Beginner", "Not assessed", "To assess", "Assess"), ("Communication", "Intermediate", "Not assessed", "To assess", "Assess"))
    for index, (name, required, level, status, action) in enumerate(skills):
        cols = st.columns([1.5, 1, 1.15, .8, .65], gap="small", vertical_alignment="center")
        with cols[0]:
            st.markdown(f'<p class="cc-row-title">{index + 1:02d} &nbsp; {name}</p>', unsafe_allow_html=True)
        with cols[1]: st.markdown(f'<span class="cc-chip">{required}</span>', unsafe_allow_html=True)
        with cols[2]: st.markdown(f'<span class="cc-muted" style="font-size:12px">{level}</span>', unsafe_allow_html=True)
        with cols[3]:
            chip = "cc-chip-coral" if status == "Gap" else "cc-chip-green" if status == "On track" else ""
            st.markdown(f'<div class="cc-career-status-cell"><span class="cc-chip {chip}">{status}</span></div>', unsafe_allow_html=True)
        with cols[4]: st.button(action, key=f"career_skill_{index}", type="primary" if status == "Gap" else "secondary", width="stretch")
        if index < len(skills) - 1:
            st.markdown('<div class="cc-divider" style="margin:8px 0"></div>', unsafe_allow_html=True)
