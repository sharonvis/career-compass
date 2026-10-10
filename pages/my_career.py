"""Career requirements and user evidence read from backend summaries."""
from html import escape
import base64
from pathlib import Path

import streamlit as st

from database.db import SessionLocal, session_scope
from services import assessment_service, career_service, user_service
from ui.components.sidebar import render_sidebar

LEVELS = ("Not Known", "Beginner", "Intermediate", "Advanced")
st.set_page_config(page_title="My Career · Career Compass", page_icon="🧭",
                   layout="wide", initial_sidebar_state="expanded")
render_sidebar("My Career")
user_id = st.session_state.get("user_id")
if type(user_id) is not int:
    st.info("Complete onboarding to load your career profile.")
    st.page_link("pages/Onboarding.py", label="Go to Onboarding")
    st.stop()

try:
    with SessionLocal() as session:
        profile = user_service.get_user_profile(session, user_id)
        careers = user_service.list_careers(session)
        career_id = profile["target_career_id"]
        summary = career_service.get_user_career_summary(session, user_id, career_id) if career_id is not None else None
except Exception:
    st.error("Could not load your career profile. Check your profile and database, then try again.")
    st.page_link("pages/Onboarding.py", label="Go to Onboarding")
    st.stop()

@st.cache_data(show_spinner=False)
def my_career_hero_art(path, modified_at):
    """Encode the existing decorative asset once per file version."""
    return base64.b64encode(Path(path).read_bytes()).decode("ascii")


st.markdown("""<style>
/* My Career top composition only; Core Skills keeps its existing styling. */
[data-testid="stMainBlockContainer"]:has(.st-key-my-career-hero) { max-width: 1240px; }
[data-testid="stLayoutWrapper"].st-key-my-career-hero,
.st-key-my-career-readiness [data-testid="stLayoutWrapper"]:is(.st-key-cc-card-career-overview,.st-key-cc-card-career-count,.st-key-cc-card-career-progress) { padding: 0; border: 0; background: transparent; box-shadow: none; }
[data-testid="stVerticalBlock"].st-key-my-career-hero { background: #FFF7F2; border: 1px solid rgba(23,19,16,.09); border-radius: 24px; padding: 28px; gap: 0; position: relative; overflow: hidden; isolation: isolate; }
.st-key-my-career-hero [data-testid="stHorizontalBlock"] { align-items: stretch; gap: 24px; position: relative; z-index: 1; }
.st-key-my-career-hero [data-testid="stColumn"] { min-width: 0; }
.st-key-my-career-hero [data-testid="stColumn"]:first-child [data-testid="stVerticalBlock"] { gap: 12px; }
.st-key-my-career-hero .cc-header-eyebrow { margin: 0 0 10px; color: #FF4A1C; font: 600 11px/1.5 'JetBrains Mono', monospace; letter-spacing: .16em; }
.st-key-my-career-hero .cc-header-title { margin: 0 0 10px; padding: 0; color: #171310; font: 800 clamp(36px,4vw,52px)/1.06 'Archivo', Arial, sans-serif; letter-spacing: -.035em; }
.st-key-my-career-hero .cc-header-subtitle { margin: 0; color: #78665B; font: 400 14px/1.6 'Inter', Arial, sans-serif; }
.st-key-my-career-hero .cc-mc-career-title { margin: 6px 0 0; padding: 0; color: #171310; font: 700 clamp(24px,2.6vw,32px)/1.2 'Archivo', Arial, sans-serif; letter-spacing: -.025em; }
.st-key-my-career-hero .cc-mc-description { margin: 0; max-width: 560px; color: #78665B; font: 400 14px/1.6 'Inter', Arial, sans-serif; }
.st-key-my-career-hero [data-testid="stColumn"]:last-child > [data-testid="stVerticalBlock"] { background: #171310; color: #FFF7EF; padding: 24px; border-radius: 18px; gap: 14px; height: 100%; box-sizing: border-box; }
.st-key-my-career-hero .cc-mc-control-label { margin: 0; display: flex; gap: 9px; align-items: center; color: #FBDDD0; font: 500 10px/1.5 'JetBrains Mono', monospace; letter-spacing: .14em; }
.st-key-my-career-hero .cc-mc-control-label::before { content: ''; width: 8px; height: 8px; background: #FF4A1C; transform: rotate(45deg); }
.st-key-my-career-hero [data-testid="stForm"] { padding: 0; border: 0; background: transparent; }
.st-key-my-career-hero [data-testid="stWidgetLabel"],.st-key-my-career-hero [data-testid="stWidgetLabel"] p { color: #FFF7EF; font: 500 13px/1.5 'Inter', Arial, sans-serif; }
.st-key-my-career-hero [data-baseweb="select"] > div { background: #FFF7F2; color: #171310; border-color: rgba(255,247,239,.2); border-radius: 10px; min-height: 44px; }
.st-key-my-career-hero [data-baseweb="select"] input { color: #171310; }
.st-key-my-career-hero [data-testid="stFormSubmitButton"] button { background: #FF4A1C; color: #171310; border: 1px solid #FF4A1C; min-height: 44px; border-radius: 10px; font: 700 14px/1.4 'Inter', Arial, sans-serif; }
.st-key-my-career-hero [data-testid="stFormSubmitButton"] button p { color: #171310; font: inherit; }
.st-key-my-career-hero [data-testid="stFormSubmitButton"] button:focus-visible { outline: 2px solid #FFF7EF; outline-offset: 3px; }
[data-testid="stVerticalBlock"].st-key-my-career-readiness { margin-top: 20px; margin-bottom: 24px; }
.st-key-my-career-readiness [data-testid="stHorizontalBlock"] { gap: 18px; align-items: stretch; }
.st-key-my-career-readiness [data-testid="stColumn"] { min-width: 0; }
.st-key-my-career-readiness [data-testid="stColumn"] > [data-testid="stVerticalBlock"] { height: 100%; }
.st-key-my-career-readiness [data-testid="stVerticalBlock"]:is(.st-key-cc-card-career-overview,.st-key-cc-card-career-count,.st-key-cc-card-career-progress) { height: 100%; min-height: 174px; border: 0; border-radius: 20px; padding: 22px; gap: 10px; box-shadow: none; color: #171310; }
.st-key-my-career-readiness [data-testid="stVerticalBlock"].st-key-cc-card-career-overview { background: #FBDDD0; }
.st-key-my-career-readiness [data-testid="stVerticalBlock"].st-key-cc-card-career-count { background: #171310; color: #FFF7EF; }
.st-key-my-career-readiness [data-testid="stVerticalBlock"].st-key-cc-card-career-progress { background: #FF4A1C; }
.st-key-my-career-readiness [data-testid="stMetric"] { border: 0; padding: 0; background: transparent; box-shadow: none; }
.st-key-my-career-readiness [data-testid="stMetricLabel"],.st-key-my-career-readiness [data-testid="stMetricLabel"] p { color: #171310; font: 500 10px/1.5 'JetBrains Mono', monospace; text-transform: uppercase; letter-spacing: .13em; }
.st-key-my-career-readiness [data-testid="stMetricValue"],.st-key-my-career-readiness [data-testid="stMetricValue"] * { color: #171310; font: 800 clamp(40px,4vw,56px)/1.05 'Archivo', Arial, sans-serif; letter-spacing: -.035em; font-variant-numeric: tabular-nums; }
.st-key-my-career-readiness .st-key-cc-card-career-count :is([data-testid="stMetricLabel"],[data-testid="stMetricLabel"] p,[data-testid="stMetricValue"],[data-testid="stMetricValue"] *) { color: #FFF7EF; }
.st-key-my-career-readiness .cc-mc-metric-helper { margin: 0 0 14px; color: #171310; font: 400 13px/1.5 'Inter', Arial, sans-serif; }
.st-key-my-career-readiness .st-key-cc-card-career-count .cc-mc-metric-helper { color: rgba(255,247,239,.76); }
.st-key-my-career-readiness .cc-mc-meter { height: 5px; border-radius: 4px; background: rgba(23,19,16,.17); overflow: hidden; }
.st-key-my-career-readiness .cc-mc-meter span { display: block; height: 100%; background: #171310; }
.st-key-my-career-readiness .st-key-cc-card-career-overview .cc-mc-meter { height: 7px; border: 1px solid #171310; box-sizing: border-box; background: transparent; }
.st-key-my-career-readiness .st-key-cc-card-career-count .cc-mc-meter { background: rgba(255,247,239,.2); }
.st-key-my-career-readiness .st-key-cc-card-career-count .cc-mc-meter span { background: #FF4A1C; }
@media (max-width: 899px) {
 .st-key-my-career-hero [data-testid="stHorizontalBlock"],.st-key-my-career-readiness [data-testid="stHorizontalBlock"] { flex-direction: column; }
 .st-key-my-career-hero [data-testid="stColumn"],.st-key-my-career-readiness [data-testid="stColumn"] { width: 100% !important; flex: 1 1 100%; }
 [data-testid="stVerticalBlock"].st-key-my-career-hero { padding: 22px; }
}
/* Put the artwork on the actual hero, avoiding a zero-height Markdown wrapper. */
[data-testid="stVerticalBlock"].st-key-my-career-hero::before { content: ''; position: absolute; top: 0; bottom: 0; right: 24%; width: 58%; z-index: 0; pointer-events: none; opacity: .48; background-repeat: no-repeat; background-size: cover; background-position: 72% 58%; }
@supports (mask-image: linear-gradient(to right,transparent,black)) or (-webkit-mask-image: linear-gradient(to right,transparent,black)) {
 [data-testid="stVerticalBlock"].st-key-my-career-hero::before { mask-image: linear-gradient(to right,transparent 0%,rgba(0,0,0,.12) 20%,black 52%); -webkit-mask-image: linear-gradient(to right,transparent 0%,rgba(0,0,0,.12) 20%,black 52%); }
}
@media (max-width: 899px) {
 [data-testid="stVerticalBlock"].st-key-my-career-hero::before { right: 0; width: 60%; height: 48%; bottom: auto; opacity: .35; background-position: 78% 48%; }
}
</style>""", unsafe_allow_html=True)

catalog = {career["career_id"]: career for career in careers}
if not catalog:
    st.info("No careers are available. Return to Onboarding to set up the catalog.")
    st.page_link("pages/Onboarding.py", label="Go to Onboarding")
    st.stop()

hero_art_path = Path(__file__).resolve().parents[1] / "assets" / "images" / "my_career_hero.png"
if hero_art_path.is_file():
    hero_art = my_career_hero_art(str(hero_art_path), hero_art_path.stat().st_mtime_ns)
    st.markdown('<style>[data-testid="stVerticalBlock"].st-key-my-career-hero::before{background-image:url("data:image/png;base64,' + hero_art + '");}</style>', unsafe_allow_html=True)
with st.container(key="my-career-hero"):
    top_left, top_right = st.columns([.65, .35], gap="large", vertical_alignment="center")
    with top_left:
        st.markdown('<p class="cc-header-eyebrow">YOUR CAREER COMPASS</p>'
                    '<h1 class="cc-header-title">My Career</h1>'
                    f'<p class="cc-header-subtitle">{escape(profile["name"])}, explore your career requirements and progress.</p>',
                    unsafe_allow_html=True)
        st.markdown(f'<h2 class="cc-mc-career-title">{escape(profile["target_career_name"] or "Choose a target career")}</h2>', unsafe_allow_html=True)
        description = catalog.get(career_id, {}).get("description")
        if description:
            st.markdown(f'<p class="cc-mc-description">{escape(description)}</p>', unsafe_allow_html=True)
    with top_right:
        st.markdown('<p class="cc-mc-control-label">YOUR DIRECTION</p>', unsafe_allow_html=True)
        with st.form("career_switch"):
            selected_id = st.selectbox("Target career", list(catalog),
                                       index=list(catalog).index(career_id) if career_id in catalog else 0,
                                       format_func=lambda value: catalog[value]["name"], key="career_switch_id")
            change = st.form_submit_button("Change career", icon=":material/swap_horiz:", width="stretch")
        if change:
            try:
                with session_scope() as session:
                    available = {career["career_id"] for career in user_service.list_careers(session)}
                    if selected_id not in available:
                        raise ValueError("Select an available career.")
                    user_service.set_target_career(session, user_id, selected_id)
            except Exception:
                st.error("Could not change career. No changes were saved. Please try again.")
            else:
                st.rerun()

if summary is None:
    st.info("Choose a target career above to see your requirements.")
    st.stop()

with st.container(key="my-career-readiness"):
    for column, label, value, key in zip(
        st.columns(3, gap="medium"),
        ("Claimed Readiness", "Effective Readiness", "Assessment Coverage"),
        (summary["claimed_readiness"], summary["effective_readiness"], summary["assessment_coverage"]),
        ("overview", "count", "progress"),
    ):
        with column:
            with st.container(key=f"cc-card-career-{key}"):
                st.metric(label, f"{value:.1%}")
                helper = {"overview": "From your self-ratings", "count": "Discounts unassessed claims", "progress": "Weighted by skill importance"}[key]
                st.markdown(f'<p class="cc-mc-metric-helper">{helper}</p><div class="cc-mc-meter" role="img" aria-label="{escape(label)} {value:.1%}"><span style="width:{value:.6%}"></span></div>', unsafe_allow_html=True)
st.markdown("""<style>
/* Core Skills only: explicit fields, compact chips, real assessment controls. */
.st-key-cc-mc-skills [data-testid="stLayoutWrapper"].st-key-cc-card-career-skills { padding: 0; border: 0; background: transparent; box-shadow: none; }
.st-key-cc-mc-skills [data-testid="stVerticalBlock"].st-key-cc-card-career-skills { background: #FFFDF9; border: 1px solid rgba(20,17,15,.08); border-radius: 20px; overflow: hidden; padding: 0; gap: 0; box-shadow: 0 8px 28px rgba(20,17,15,.04); }
.st-key-cc-mc-skills .cc-mc-skills-heading { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 16px; margin: 0 0 18px; }
.st-key-cc-mc-skills .cc-mc-skills-eyebrow { font: 500 11px/1.5 'JetBrains Mono', monospace; letter-spacing: .18em; color: #4A433D; }
.st-key-cc-mc-skills .cc-mc-skills-heading h2 { margin: 7px 0 0; padding: 0; font: 700 30px/1.15 'Archivo', Arial, sans-serif; color: #14110F; }
.st-key-cc-mc-skills .cc-mc-skills-count { padding: 0 14px; height: 32px; display: flex; align-items: center; border-radius: 999px; background: #14110F; color: #FFFFFF; font: 500 13px/1.4 'Inter', Arial, sans-serif; }
.st-key-cc-mc-skills [data-testid="stVerticalBlock"][class*="st-key-cc-mc-skill-row-"] { padding: 17px 24px; border-bottom: 1px solid rgba(20,17,15,.06); gap: 0; background: var(--cc-mc-row-surface,#FFFDF9); }
.st-key-cc-mc-skills .st-key-cc-card-career-skills > :last-child [data-testid="stVerticalBlock"][class*="st-key-cc-mc-skill-row-"] { border-bottom: 0; }
.st-key-cc-mc-skills [class*="st-key-cc-mc-skill-row-"] [data-testid="stHorizontalBlock"] { display: grid; grid-template-columns: minmax(0,1.65fr) minmax(0,.9fr) minmax(0,1.1fr) minmax(0,1.25fr) minmax(0,1.1fr); gap: 16px; align-items: center; }
.st-key-cc-mc-skills [data-testid="stColumn"] { width: 100% !important; min-width: 0; }
.st-key-cc-mc-skills .cc-mc-skill-name { margin: 0; font: 600 16px/1.45 'Inter', Arial, sans-serif; color: #14110F; overflow-wrap: anywhere; }
.st-key-cc-mc-skills .cc-mc-skill-attempt { margin-top: 7px; color: #4A433D; font: 400 12px/1.5 'Inter', Arial, sans-serif; }
.st-key-cc-mc-skills .cc-mc-skill-label { display: flex; align-items: center; gap: 7px; font: 500 10px/1.5 'JetBrains Mono', monospace; letter-spacing: .1em; color: #4A433D; }
.st-key-cc-mc-skills .cc-mc-skill-required .cc-mc-skill-label::before { content: ''; width: 6px; height: 6px; flex: 0 0 6px; background: #FF4A1C; }
.st-key-cc-mc-skills .cc-mc-skill-value { margin-top: 5px; color: #14110F; font: 600 14px/1.5 'Inter', Arial, sans-serif; overflow-wrap: anywhere; }
.st-key-cc-mc-skills .cc-mc-skill-field + .cc-mc-skill-field { margin-top: 8px; }
.st-key-cc-mc-skills .cc-mc-skill-field .cc-mc-skill-label { color: #78665B; font: 500 10px/1.5 'JetBrains Mono', monospace; text-transform: uppercase; }
.st-key-cc-mc-skills .cc-mc-skill-field .cc-mc-skill-value { margin-top: 7px; color: #14110F; font: 600 14px/1.5 'Inter', Arial, sans-serif; }
.st-key-cc-mc-skills .cc-mc-skill-chip { display: inline-flex; align-items: center; gap: 7px; min-height: 28px; padding: 5px 10px; box-sizing: border-box; border-radius: 999px; border: 1px solid rgba(20,17,15,.35); color: #14110F; font: 500 10px/1.4 'JetBrains Mono', monospace; letter-spacing: .08em; text-transform: uppercase; max-width: 100%; }
.st-key-cc-mc-skills .cc-mc-skill-chip-gap { background: #FBDDD0; border-color: rgba(255,74,28,.16); }
.st-key-cc-mc-skills .cc-mc-skill-chip-gap::before { content: ''; width: 5px; height: 5px; flex: 0 0 5px; border-radius: 50%; background: #FF4A1C; }
.st-key-cc-mc-skills .cc-mc-skill-chip-met { background: #14110F; color: #FFF7EF; }
.st-key-cc-mc-skills .cc-mc-skill-chip-blocked { background: #F4E7DE; border: 1px solid rgba(20,17,15,.16); color: #4A433D; }
.st-key-cc-mc-skills .cc-mc-skill-detail { margin-top: 6px; font: 400 12px/1.5 'Inter', Arial, sans-serif; color: #4A433D; overflow-wrap: anywhere; }
.st-key-cc-mc-skills .cc-mc-skill-prerequisites { margin-top: 8px; color: #78665B; font: 400 12px/1.75 'Inter', Arial, sans-serif; overflow-wrap: anywhere; }
.st-key-cc-mc-skills .cc-mc-skill-prerequisites .cc-mc-skill-label { margin-bottom: 5px; text-transform: uppercase; color: #78665B; }
.st-key-cc-mc-skills .cc-mc-skill-prerequisite + .cc-mc-skill-prerequisite { margin-top: 4px; }
.st-key-cc-mc-skills .cc-mc-skill-unavailable { display: flex; align-items: center; min-height: 40px; color: #78665B; font: 400 12px/1.5 'Inter', Arial, sans-serif; }
.st-key-cc-mc-skills [data-testid="stButton"] button { background: #FF4A1C; border: 1px solid #FF4A1C; color: #14110F; min-height: 40px; border-radius: 12px; padding: 0 14px; font: 700 14px/1.4 'Inter', Arial, sans-serif; }
.st-key-cc-mc-skills [data-testid="stButton"] button p { color: #14110F !important; font: inherit; }
.st-key-cc-mc-skills [data-testid="stButton"] button:hover { background: #14110F; border-color: #14110F; color: #FFFFFF; }
.st-key-cc-mc-skills [data-testid="stButton"] button:hover p { color: #FFFFFF !important; }
.st-key-cc-mc-skills [data-testid="stButton"] button:focus-visible { outline: 2px solid #14110F; outline-offset: 3px; }
.st-key-cc-mc-skills .cc-mc-skills-eyebrow { display: flex; align-items: center; gap: 10px; }
.st-key-cc-mc-skills .cc-mc-skills-eyebrow::before { content: ''; width: 20px; height: 2px; background: #FF4A1C; }
.st-key-cc-mc-skills .cc-mc-skill-name { position: relative; padding-left: 14px; font-weight: 700; }
.st-key-cc-mc-skills .cc-mc-skill-name::before { content: ''; position: absolute; left: 0; top: .55em; width: 5px; height: 5px; border-radius: 1px; background: #FF4A1C; }
.st-key-cc-mc-skills .cc-mc-skill-required { background: #FBDDD0; padding: 10px; border-radius: 10px; }
.st-key-cc-mc-skills .cc-mc-skill-field + .cc-mc-skill-field .cc-mc-skill-label { color: #6F5E54; }
.st-key-cc-mc-skills [class*="st-key-cc-mc-skill-row-"] [data-testid="stColumn"]:nth-child(4) { align-self: start; }
.st-key-cc-mc-skills [class*="st-key-cc-mc-skill-row-"] [data-testid="stColumn"]:last-child { align-self: center; }
.st-key-cc-mc-skills { container-type: inline-size; }
@container (max-width: 850px) {
 .st-key-cc-mc-skills [class*="st-key-cc-mc-skill-row-"] [data-testid="stHorizontalBlock"] { grid-template-columns: minmax(0,1fr); gap: 16px; }
}
@media (max-width: 899px) {
 .st-key-cc-mc-skills [class*="st-key-cc-mc-skill-row-"] [data-testid="stHorizontalBlock"] { grid-template-columns: minmax(0,1fr); gap: 16px; }
}
@media (max-width: 599px) {
 .st-key-cc-mc-skills [data-testid="stButton"] button { width: 100%; min-height: 44px; }
}
@media (prefers-reduced-motion: no-preference) {
 @keyframes cc-mc-skills-enter { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }
 .st-key-cc-mc-skills [data-testid="stVerticalBlock"][class*="st-key-cc-mc-skill-row-"] { animation: cc-mc-skills-enter 200ms ease both; animation-delay: var(--cc-mc-skill-delay,0ms); transition: background-color 200ms ease; }
 .st-key-cc-mc-skills [data-testid="stVerticalBlock"][class*="st-key-cc-mc-skill-row-"]:hover { background: rgba(20,17,15,.03); }
}
</style>""", unsafe_allow_html=True)
with st.container(key="cc-mc-skills"):
    st.markdown(f'<div class="cc-mc-skills-heading"><div><div class="cc-mc-skills-eyebrow">CAREER REQUIREMENTS</div><h2>Core skills</h2></div><div class="cc-mc-skills-count">{len(summary["skills"])} required skills</div></div>', unsafe_allow_html=True)
    with st.container(key="cc-card-career-skills"):
        supported = {item["skill_name"] for item in assessment_service.list_supported_assessments()}
        st.markdown('<style>' + ''.join(f'.st-key-cc-mc-skills .st-key-cc-mc-skill-row-{skill["skill_id"]}' + '{--cc-mc-skill-delay:' + str(index * 50) + 'ms;--cc-mc-row-surface:' + ('#FFF8F3' if index % 2 else '#FFFDF9') + ';}' for index, skill in enumerate(summary["skills"])) + '</style>', unsafe_allow_html=True)
        for skill in summary["skills"]:
            demonstrated = skill["demonstrated_level"]
            label = "Not assessed" if demonstrated is None else "Not Demonstrated" if demonstrated == 0 else LEVELS[demonstrated]
            # Display-only mapping of the existing backend fields; no scoring.
            state, chip = ("BLOCKED", "blocked") if not skill["prerequisites_met"] else ("UNASSESSED", "unassessed") if demonstrated is None else ("CONFIRMED GAP", "gap") if skill["gap"] is not None and skill["gap"] > 0 else ("MEETS REQUIREMENT", "met")
            with st.container(key=f"cc-mc-skill-row-{skill['skill_id']}"):
                columns = st.columns([1.5, 1, 1.2, 1.4, .9], gap="medium", vertical_alignment="center")
                with columns[0]:
                    attempt = f'<div class="cc-mc-skill-attempt">Latest completed attempt: #{escape(str(skill["latest_attempt_id"]))}</div>' if skill.get("latest_attempt_id") is not None else ""
                    st.markdown(f'<div class="cc-mc-skill-name">{escape(skill["name"])}</div>{attempt}', unsafe_allow_html=True)
                with columns[1]:
                    st.markdown(f'<div class="cc-mc-skill-required"><div class="cc-mc-skill-label">REQUIRED</div><div class="cc-mc-skill-value">{escape(LEVELS[skill["required_level"]])}</div></div>', unsafe_allow_html=True)
                with columns[2]:
                    st.markdown(f'<div class="cc-mc-skill-field"><div class="cc-mc-skill-label">CLAIMED</div><div class="cc-mc-skill-value">{escape(LEVELS[skill["claimed_level"]])}</div></div><div class="cc-mc-skill-field"><div class="cc-mc-skill-label">DEMONSTRATED</div><div class="cc-mc-skill-value">{escape(label)}</div></div>', unsafe_allow_html=True)
                with columns[3]:
                    details = ""
                    if demonstrated is not None and skill["gap"] is not None and skill["gap"] > 0:
                        unit = "level" if skill["gap"] == 1 else "levels"
                        details += f'<div class="cc-mc-skill-detail">Gap: {escape(str(skill["gap"]))} {unit}</div>'
                    if not skill["prerequisites_met"] and skill.get("prerequisites"):
                        details += '<div class="cc-mc-skill-prerequisites"><div class="cc-mc-skill-label">REQUIRES</div>' + ''.join(f'<div class="cc-mc-skill-prerequisite">{escape(prerequisite["skill_name"])} &middot; {escape(LEVELS[prerequisite["minimum_level"]])}</div>' for prerequisite in skill["prerequisites"]) + '</div>'
                    st.markdown(f'<div class="cc-mc-skill-chip cc-mc-skill-chip-{chip}">{state}</div>{details}', unsafe_allow_html=True)
                with columns[4]:
                    if skill["assessable"] and skill["name"] in supported:
                        if st.button("Assess" if demonstrated is None else "Reassess",
                                     key=f"career_skill_{skill['skill_id']}", width="stretch"):
                            st.session_state["assessment_skill"] = skill["name"]
                            st.session_state.pop("assessment_attempt_id", None)
                            st.switch_page("pages/Assessment.py")
                    else:
                        st.markdown('<div class="cc-mc-skill-unavailable">Not available yet</div>', unsafe_allow_html=True)
