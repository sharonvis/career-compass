"""Static internships and early-career opportunity discovery screen."""

import streamlit as st

from ui.components.header import render_header
from ui.components.sidebar import render_sidebar

st.set_page_config(page_title="Opportunities · Career Compass", page_icon="🧭", layout="wide", initial_sidebar_state="expanded")
render_sidebar("Opportunities")
render_header("Opportunities", "Explore roles that fit your career direction and growing skills.", "YOUR NEXT POSSIBILITY")

st.markdown('<div class="cc-opportunities-header-gap"></div>', unsafe_allow_html=True)
query, location, sort = st.columns([1.4, 1, .7], gap="medium")
with query:
    st.text_input("Search roles", placeholder="Role, company, or skill", label_visibility="collapsed", key="opportunity_search")
with location:
    st.selectbox("Location", ("Any location", "Remote", "United States", "India"), label_visibility="collapsed", key="opportunity_location")
with sort:
    st.selectbox("Sort by", ("Best match", "Newest", "Closing soon"), label_visibility="collapsed", key="opportunity_sort")

st.markdown('<p class="cc-section-copy">Showing <b>12 opportunities</b> matched to your Data Analyst path</p>', unsafe_allow_html=True)
st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
left, right = st.columns(2, gap="large")
opportunities = (
    ("Junior Data Analyst Intern", "Northstar Labs", "Remote · Internship", "Posted 2 days ago", ("SQL", "Python", "Data visualisation"), "Strong match", "cc-chip-green"),
    ("Business Intelligence Intern", "Brightline Group", "New York, NY · Internship", "Posted 4 days ago", ("SQL", "Excel", "Communication"), "Good match", "cc-chip-coral"),
    ("Product Analytics Intern", "Fieldnote", "Remote · Internship", "Posted 1 week ago", ("Statistics", "SQL", "Experimentation"), "Good match", "cc-chip-coral"),
    ("Data Operations Associate", "Juniper Health", "Boston, MA · Full time", "Posted 1 week ago", ("Python", "Data quality", "SQL"), "Build a skill", ""),
)
for i, (title, company, meta, posted, skills, fit, fit_style) in enumerate(opportunities):
    col = left if i % 2 == 0 else right
    with col:
        with st.container(key=f"cc-card-opportunity-{i}"):
            st.markdown(f'<p class="cc-stat-label">{company.upper()} <span style="float:right;color:#aaa39c">{posted}</span></p><h3>{title}</h3><p class="cc-section-copy">{meta}</p>', unsafe_allow_html=True)
            st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
            st.markdown(" ".join(f'<span class="cc-chip">{skill}</span>' for skill in skills), unsafe_allow_html=True)
            st.markdown(f'<div class="cc-opportunity-match-row"><span class="cc-chip {fit_style}">{fit}</span></div>', unsafe_allow_html=True)
            st.button("View opportunity", key=f"view_opportunity_{i}", icon=":material/arrow_outward:", width="stretch")
