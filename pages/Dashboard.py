"""Career Compass dashboard with static reference data."""

import streamlit as st

from ui.components.header import render_header
from ui.components.sidebar import render_sidebar

st.set_page_config(
    page_title="Dashboard · Career Compass",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded",
)
render_sidebar("Dashboard")
render_header(
    title="Sharon",
    subtitle="Here’s your next step toward the future you want.",
    eyebrow="Good evening,",
)

st.markdown("<div class='cc-dashboard-gap'></div>", unsafe_allow_html=True)
hero_action, target_career = st.columns([1.98, 1], gap="small")
with hero_action:
    with st.container(key="dashboard-hero-next-action"):
        st.markdown(
            '<div class="cc-dashboard-card-heading"><span class="cc-section-kicker">NEXT ACTION</span>'
            '<span class="cc-more">•••</span></div>'
            '<h2 class="cc-dashboard-hero-title">Assess SQL</h2>'
            '<p class="cc-dashboard-copy">SQL is an important skill for your target career and is currently<br class="cc-wide-break"> '
            'unassessed. Complete the assessment to understand your level.</p>',
            unsafe_allow_html=True,
        )
        st.button("Start Assessment  →", type="primary", key="dashboard_start_assessment")
with target_career:
    with st.container(key="dashboard-hero-career"):
        st.markdown(
            '<div class="cc-dashboard-card-heading"><span class="cc-dashboard-label">YOUR TARGET CAREER</span>'
            '<span class="cc-chevron">›</span></div>'
            '<h2 class="cc-dashboard-career-title">Data Analyst</h2>'
            '<div class="cc-career-summary"><p class="cc-dashboard-copy">Focus on building your data analysis, SQL, and statistics skills.</p>'
            '<div class="cc-career-bars"><i></i><i></i><i></i></div></div>',
            unsafe_allow_html=True,
        )

st.markdown("<div class='cc-dashboard-gap cc-gap-small'></div>", unsafe_allow_html=True)
metric_columns = st.columns(3, gap="small")
metrics = (
    ("◯", "Claimed Readiness", "81%", 81, "claimed"),
    ("▥", "Demonstrated Readiness", "51%", 51, "demonstrated"),
    ("⊙", "Assessment Coverage", "2 of 6 skills", 2, "coverage"),
)
for col, (icon, label, value, progress, key) in zip(metric_columns, metrics):
    with col:
        with st.container(key=f"dashboard-metric-{key}"):
            if key == "coverage":
                meter = "".join(f'<i class="{"filled" if index < progress else ""}"></i>' for index in range(6))
            else:
                meter = f'<div class="cc-meter"><i style="width:{progress}%"></i></div>'
            st.markdown(
                f'<div class="cc-dashboard-metric"><span class="cc-metric-icon">{icon}</span>'
                f'<div class="cc-metric-content"><span class="cc-metric-label">{label}</span>'
                f'<strong>{value}</strong>{meter}</div></div>',
                unsafe_allow_html=True,
            )

st.markdown("<div class='cc-dashboard-gap cc-gap-small'></div>", unsafe_allow_html=True)
gaps_card, roadmap_card = st.columns([.94, 1.06], gap="small")
with gaps_card:
    with st.container(key="dashboard-important-gaps"):
        st.markdown('<div class="cc-dashboard-section-heading"><h2>Important Gaps</h2><span class="cc-chevron">›</span></div>', unsafe_allow_html=True)
        gaps = (("1", "Statistics", "Not Assessed", "coral"), ("2", "ML Fundamentals", "Beginner", "neutral"), ("3", "Data Visualisation", "Not Assessed", "coral"))
        for number, name, status, kind in gaps:
            st.markdown(
                f'<div class="cc-gap-row"><span class="cc-gap-number">{number}</span>'
                f'<b>{name}</b><span class="cc-gap-status {kind}">{status}</span></div>',
                unsafe_allow_html=True,
            )
with roadmap_card:
    with st.container(key="dashboard-current-roadmap"):
        st.markdown('<div class="cc-dashboard-section-heading"><h2>Current Roadmap</h2><span class="cc-roadmap-summary">2 of 5 completed</span><span class="cc-mini-meter"><i></i></span><span class="cc-chevron">›</span></div>', unsafe_allow_html=True)
        roadmap = (("done", "Learn SQL Basics"), ("active", "Practice JOINs"), ("", "Learn Data Analysis with Python"), ("", "Work on a mini project"))
        for state, label in roadmap:
            st.markdown(f'<div class="cc-roadmap-step {state}"><span class="cc-roadmap-dot">{"✓" if state == "done" else ""}</span><span>{label}</span></div>', unsafe_allow_html=True)

st.markdown("<div class='cc-dashboard-gap cc-gap-small'></div>", unsafe_allow_html=True)
deadline_card, opportunity_card, activity_card = st.columns(3, gap="small")
with deadline_card:
    with st.container(key="dashboard-next-deadline"):
        st.markdown('<div class="cc-bottom-card-heading"><span>▣</span><b>Next Deadline</b><span class="cc-chevron">›</span></div><div class="cc-bottom-card-content"><div><strong>AI/ML Intern</strong><small>TechCorp</small></div><span class="cc-date-badge">12 Oct 2026<small>in 3 days</small></span></div>', unsafe_allow_html=True)
with opportunity_card:
    with st.container(key="dashboard-recommended-opportunity"):
        st.markdown('<div class="cc-bottom-card-heading"><span>▣</span><b>Recommended Opportunity</b><span class="cc-chevron">›</span></div><div class="cc-bottom-card-content"><div><strong>Data Analyst Intern</strong><small>TechCorp</small></div><span class="cc-match-badge">Strong Match</span></div>', unsafe_allow_html=True)
with activity_card:
    with st.container(key="dashboard-recent-activity"):
        st.markdown('<div class="cc-bottom-card-heading"><span>◷</span><b>Recent Activity</b><span class="cc-chevron">›</span></div><p class="cc-activity-line">Completed Python Basics assessment<small>2 days ago</small></p><p class="cc-activity-line">Added SQL to your learning roadmap</p>', unsafe_allow_html=True)
