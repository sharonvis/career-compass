"""Static application tracking screen."""

import streamlit as st

from ui.components.header import render_header
from ui.components.sidebar import render_sidebar

st.set_page_config(page_title="Applications · Career Compass", page_icon="🧭", layout="wide", initial_sidebar_state="expanded")
render_sidebar("Applications")
render_header("Applications", "Keep your opportunities organized from first look to final decision.", "YOUR JOB SEARCH")

st.markdown('<div class="cc-applications-header-gap"></div>', unsafe_allow_html=True)
metrics = st.columns(3, gap="medium")
for col, label, value in zip(metrics, ("IN PROGRESS", "INTERVIEWS", "OFFERS"), ("4", "2", "1")):
    with col:
        with st.container(key=f"cc-card-applications-metric-{label.lower()}"):
            st.markdown(f'<p class="cc-stat-label">{label}</p><div class="cc-stat-value">{value}</div>', unsafe_allow_html=True)

st.markdown("<div style='height:22px'></div>", unsafe_allow_html=True)
filter_col, action_col = st.columns([1, .35], vertical_alignment="center")
with filter_col:
    with st.container(key="cc-applications-filter"):
        selected_filter = st.radio("Application status", ("All applications", "In progress", "Archived"), horizontal=True, label_visibility="collapsed", key="application_status_filter")
with action_col:
    st.button("Add application", type="primary", icon=":material/add:", width="stretch", key="add_application")

applications = (
    ("Northstar Labs", "Junior Data Analyst Intern", "Applied", "Oct 06, 2026", "cc-chip-coral"),
    ("Brightline Group", "Business Intelligence Intern", "Interview", "Oct 04, 2026", "cc-chip-green"),
    ("Fieldnote", "Product Analytics Intern", "Assessment", "Oct 01, 2026", "cc-chip-coral"),
    ("Juniper Health", "Data Operations Associate", "Saved", "Sep 28, 2026", ""),
)
if selected_filter == "In progress":
    applications = tuple(item for item in applications if item[2] not in ("Saved",))
elif selected_filter == "Archived":
    applications = ()

with st.container(key="cc-card-applications-list"):
    header_columns = st.columns([1.2, 2, .8, .9], gap="small")
    for column, label in zip(header_columns, ("Company", "Role", "Status", "Last updated")):
        with column:
            st.markdown(f'<p class="cc-applications-table-header">{label}</p>', unsafe_allow_html=True)
    st.markdown('<div class="cc-divider" style="margin:0 0 8px"></div>', unsafe_allow_html=True)
    if not applications:
        st.info("No archived applications yet.")
    for i, (company, role, status, date, chip) in enumerate(applications):
        cols = st.columns([1.2, 2, .8, .9], gap="small", vertical_alignment="center")
        with cols[0]: st.markdown(f'<p class="cc-row-title">{company}</p>', unsafe_allow_html=True)
        with cols[1]: st.markdown(f'<span class="cc-muted" style="font-size:12px">{role}</span>', unsafe_allow_html=True)
        with cols[2]: st.markdown(f'<span class="cc-chip {chip}">{status}</span>', unsafe_allow_html=True)
        with cols[3]: st.markdown(f'<span class="cc-muted" style="font-size:11px">{date}</span>', unsafe_allow_html=True)
        if i < len(applications) - 1:
            st.markdown('<div class="cc-divider" style="margin:8px 0"></div>', unsafe_allow_html=True)
