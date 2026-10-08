"""Career Compass onboarding page; selections are kept in Streamlit session state."""

import base64
from pathlib import Path

import streamlit as st

st.set_page_config(
    page_title="Career Compass | Onboarding",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="collapsed",
)

YEAR_OPTIONS = ("1st Year", "2nd Year", "3rd Year", "4th Year")


def _set_year_of_study(year: str) -> None:
    st.session_state["year_of_study"] = year


st.session_state.setdefault("year_of_study", "2nd Year")
ROOT = Path(__file__).resolve().parents[1]
css = (ROOT / "assets" / "onboarding.css").read_text(encoding="utf-8")
logo_path = ROOT / "assets" / "images" / "CareerCompassLogo.png"
logo = base64.b64encode(logo_path.read_bytes()).decode("ascii")

st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
st.markdown('<div class="cc-onboarding-marker" aria-hidden="true"></div>', unsafe_allow_html=True)
st.markdown(
    f"""
    <div class="cc-onboarding-topbar">
      <div class="cc-onboarding-brand">
        <img src="data:image/png;base64,{logo}" alt="">
        <span>CAREER COMPASS</span>
      </div>
      <span class="cc-onboarding-step">ONBOARDING</span>
    </div>
    """,
    unsafe_allow_html=True,
)

hero_copy, quick_card = st.columns([2.45, 1], vertical_alignment="center")
with hero_copy:
    st.markdown(
        """
        <p class="cc-onboarding-eyebrow">GET STARTED</p>
        <h1 class="cc-onboarding-title">Build your Career Compass.</h1>
        <p class="cc-onboarding-intro">Tell us where you are now, where you want to go, and how you rate your current skills.</p>
        """,
        unsafe_allow_html=True,
    )
with quick_card:
    st.markdown(
        """
        <div class="cc-quick-card">
          <strong><span>✦</span> 3 quick sections</strong>
          <p>About you · Target career · Claimed skills</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

with st.container(key="onboarding-about-card"):
    st.markdown(
        """
        <p class="cc-section-eyebrow">01 · ABOUT YOU</p>
        <h2 class="cc-section-title">Tell us where you're starting from.</h2>
        <p class="cc-section-description">These details help keep career requirements and opportunities relevant.</p>
        """,
        unsafe_allow_html=True,
    )
    college_col, degree_col = st.columns(2, gap="large")
    with college_col:
        st.markdown('<p class="cc-field-label">College / University</p>', unsafe_allow_html=True)
        st.text_input(
            "College / University",
            key="college_university",
            label_visibility="collapsed",
            placeholder="",
        )
    with degree_col:
        st.markdown('<p class="cc-field-label">Degree / Branch</p>', unsafe_allow_html=True)
        st.text_input(
            "Degree / Branch",
            key="degree_branch",
            label_visibility="collapsed",
            placeholder="B.Tech Computer Science",
        )
    st.markdown('<p class="cc-field-label cc-year-label">Year of study</p>', unsafe_allow_html=True)
    with st.container(key="onboarding-years"):
        year_columns = st.columns(4, gap="small")
        selected_year = st.session_state["year_of_study"]

        with year_columns[0]:
            with st.container(key="year-option-1-selected" if selected_year == "1st Year" else "year-option-1"):
                st.button(
                    "1st Year",
                    type="secondary",
                    key="year_of_study_button_1",
                    on_click=_set_year_of_study,
                    args=("1st Year",),
                    use_container_width=True,
                )
        with year_columns[1]:
            with st.container(key="year-option-2-selected" if selected_year == "2nd Year" else "year-option-2"):
                st.button(
                    "2nd Year",
                    type="secondary",
                    key="year_of_study_button_2",
                    on_click=_set_year_of_study,
                    args=("2nd Year",),
                    use_container_width=True,
                )
        with year_columns[2]:
            with st.container(key="year-option-3-selected" if selected_year == "3rd Year" else "year-option-3"):
                st.button(
                    "3rd Year",
                    type="secondary",
                    key="year_of_study_button_3",
                    on_click=_set_year_of_study,
                    args=("3rd Year",),
                    use_container_width=True,
                )
        with year_columns[3]:
            with st.container(key="year-option-4-selected" if selected_year == "4th Year" else "year-option-4"):
                st.button(
                    "4th Year",
                    type="secondary",
                    key="year_of_study_button_4",
                    on_click=_set_year_of_study,
                    args=("4th Year",),
                    use_container_width=True,
                )

st.markdown('<div class="cc-onboarding-connector" aria-hidden="true"></div>', unsafe_allow_html=True)

careers = {
    "AI / ML Engineer": "Python · ML Fundamentals · SQL · Statistics · Pandas · Git",
    "Software Engineer": "Programming · problem solving · systems · development fundamentals",
    "Data Analyst": "SQL · Statistics · data analysis · reporting · data tools",
}
with st.container(key="onboarding-career-card"):
    st.markdown(
        """
        <p class="cc-section-eyebrow">02 · TARGET CAREER</p>
        <h2 class="cc-section-title">What are you aiming for?</h2>
        <p class="cc-section-description">Choose one target for now. Switching careers later will not erase your progress.</p>
        """,
        unsafe_allow_html=True,
    )
    with st.container(key="onboarding-career-picker"):
        st.radio(
            "Target career",
            options=tuple(careers),
            index=0,
            format_func=lambda career: f"{career}\n\n{careers[career]}",
            key="target_career",
            label_visibility="collapsed",
        )

st.markdown('<div class="cc-onboarding-connector" aria-hidden="true"></div>', unsafe_allow_html=True)

skills = ("Python", "ML Fundamentals", "SQL", "Statistics")
levels = ("Not Known", "Beginner", "Intermediate", "Advanced")
default_levels = {
    "Python": "Intermediate",
    "ML Fundamentals": "Beginner",
    "SQL": "Advanced",
    "Statistics": "Beginner",
}
with st.container(key="onboarding-skills-card"):
    st.markdown(
        """
        <p class="cc-section-eyebrow">03 · CLAIM YOUR SKILLS</p>
        <h2 class="cc-section-title">How strong do you think you are?</h2>
        <p class="cc-section-description">This is your self-rating. Assessments later create your demonstrated level.</p>
        """,
        unsafe_allow_html=True,
    )
    skill_heading, level_heading = st.columns([1.12, 1], gap="medium")
    with level_heading:
        heading_cols = st.columns(4, gap="small")
        for col, level in zip(heading_cols, levels):
            with col:
                st.markdown(f'<p class="cc-level-heading">{level}</p>', unsafe_allow_html=True)
    for skill in skills:
        skill_col, choices_col = st.columns([1.12, 1], gap="medium", vertical_alignment="center")
        with skill_col:
            st.markdown(f'<p class="cc-skill-name">{skill}</p>', unsafe_allow_html=True)
        with choices_col:
            st.radio(
                f"Claimed level for {skill}",
                options=levels,
                index=levels.index(default_levels[skill]),
                horizontal=True,
                key=f"claimed_{skill.lower().replace(' ', '_')}",
                label_visibility="collapsed",
            )
    st.markdown(
        '<div class="cc-claim-note"><span>✦</span> These are claims, not scores. Your assessments will determine demonstrated levels.</div>',
        unsafe_allow_html=True,
    )

with st.container(key="onboarding-cta"):
    cta_text, cta_button = st.columns([1.5, 0.55], vertical_alignment="center")
    with cta_text:
        st.markdown('<p class="cc-cta-title">Ready to see your Career Compass?</p>', unsafe_allow_html=True)
    with cta_button:
        st.button("Build My Career Compass  →", type="primary", key="build_career_compass", width="stretch")
