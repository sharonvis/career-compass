"""Service-backed roadmap; manual completion is not assessment evidence."""
from html import escape
from pathlib import Path
import base64

import streamlit as st

from database.db import SessionLocal, session_scope
from services import assessment_service, roadmap_service, user_service
from ui.components.sidebar import render_sidebar

st.set_page_config(page_title="Roadmap · Career Compass", page_icon="🧭",
                   layout="wide", initial_sidebar_state="expanded")
render_sidebar("Roadmap")
@st.cache_data(show_spinner=False)
def roadmap_header_art(path, modified_at):
    return base64.b64encode(Path(path).read_bytes()).decode("ascii")

assets = Path(__file__).resolve().parents[1] / "assets"
st.markdown('<style>' + (assets / "roadmap.css").read_text(encoding="utf-8") + '</style>', unsafe_allow_html=True)
with st.container(key="cc-roadmap-page"):
    art_path = assets / "images" / "my_career_hero.png"
    if art_path.is_file():
        encoded_art = roadmap_header_art(str(art_path), art_path.stat().st_mtime_ns)
        st.markdown('<style>.st-key-cc-roadmap-page .cc-rm-header::before{background-image:url("data:image/png;base64,' + encoded_art + '");}</style>', unsafe_allow_html=True)
    st.markdown('<div class="cc-rm-header"><div class="cc-rm-header-copy"><p class="cc-rm-eyebrow">LEARN WITH DIRECTION</p><h1>Your roadmap</h1><p class="cc-rm-intro">A focused path from your current skills to your target career.</p></div></div>', unsafe_allow_html=True)
    user_id = st.session_state.get("user_id")
    if type(user_id) is not int:
        st.info("Complete onboarding to load your roadmap.")
        st.page_link("pages/Onboarding.py", label="Go to Onboarding")
        st.stop()
    try:
        with SessionLocal() as session:
            profile = user_service.get_user_profile(session, user_id)
            career_id = profile["target_career_id"]
            items = roadmap_service.get_user_roadmap(session, user_id, career_id) if career_id is not None else []
        supported = {item["skill_name"] for item in assessment_service.list_supported_assessments()}
    except Exception:
        st.error("Could not load your roadmap. Check your profile and database, then try again.")
        st.page_link("pages/Onboarding.py", label="Go to Onboarding")
        st.stop()
    if career_id is None:
        st.info("Choose a target career in Onboarding to see your roadmap.")
        st.page_link("pages/Onboarding.py", label="Go to Onboarding")
        st.stop()
    with st.container(key="cc-card-roadmap-summary"):
        completed = sum(item["status"] == "completed" for item in items)
        ratio = completed / len(items) if items else 0
        st.markdown(f'<div class="cc-rm-summary"><div class="cc-rm-summary-main"><h2>{escape(profile["target_career_name"])}</h2><p>{completed} of {len(items)} roadmap items completed</p><div class="cc-rm-progress-row"><div class="cc-rm-track" role="img" aria-label="{completed} of {len(items)} roadmap items completed"><span style="width:{ratio:.6%}"></span></div><strong>{ratio:.0%}</strong></div></div><div class="cc-rm-summary-note">Small steps.<br>Bigger horizons.</div></div>', unsafe_allow_html=True)
        st.caption("Showing the service's current roadmap subset and relevant completion history.")
    if not items:
        st.info("No roadmap steps are currently returned for this career. Review your career profile for your latest progress.")
    elif completed == len(items):
        st.success("All displayed roadmap items are complete.")
    with st.container(key="roadmap-return-links"):
        left_link, right_link = st.columns(2)
        with left_link:
            st.page_link("pages/my_career.py", label="View My Career")
        with right_link:
            st.page_link("pages/Dashboard.py", label="Return to Dashboard")
    status_filters = {"All Steps": None, "To Do": "up_next", "In Progress": "current", "Completed": "completed", "Locked": "locked"}
    with st.container(key="roadmap-filters"):
        filter_column, sort_column = st.columns([4, 1.3], vertical_alignment="bottom")
        with filter_column:
            selected_filter = st.segmented_control("Roadmap steps", list(status_filters), default="All Steps", format_func=lambda name: f"{name} ({len(items) if status_filters[name] is None else sum(item['status'] == status_filters[name] for item in items)})", key="roadmap_status_filter", label_visibility="collapsed") or "All Steps"
        with sort_column:
            sort_order = st.selectbox("Sort by", ("Recommended order", "Skill name"), key="roadmap_display_sort")
    visible_items = [(index, item) for index, item in enumerate(items, 1) if status_filters[selected_filter] is None or item["status"] == status_filters[selected_filter]]
    if sort_order == "Skill name":
        visible_items = sorted(visible_items, key=lambda pair: pair[1]["skill_name"].casefold())
    if items and not visible_items:
        st.info("No roadmap steps in this status yet.")

    icons = {"Python": "code", "SQL": "database", "Statistics": "bar_chart", "Machine Learning Fundamentals": "hub", "Pandas/Data Handling": "table_chart", "Git": "account_tree"}
    for index, item in visible_items:
        key = item["item_key"]
        action = item["action_type"]
        with st.container(key=f"cc-card-roadmap-{key}"):
            number_column, content_column, status_column, action_column = st.columns([.45, 5.4, 1.1, 1.8], vertical_alignment="center")
            with number_column:
                st.markdown(f'<div class="cc-rm-step-number cc-rm-step-{escape(item["status"])}">{index:02}</div>', unsafe_allow_html=True)
            with content_column:
                icon = icons.get(item["skill_name"], "route")
                st.markdown(f'<div class="cc-rm-step-content"><div class="cc-rm-skill-icon" aria-hidden="true"><span class="material-symbols-rounded">{icon}</span></div><div class="cc-rm-copy"><h3>{escape(item["title"])}</h3><p>{escape(item["reason"])}</p><div class="cc-rm-meta">{escape(item["skill_name"])}</div></div></div>', unsafe_allow_html=True)
                if item.get("latest_attempt_id") is not None:
                    with st.expander("Step details"):
                        st.caption(f"Related assessment attempt: {item['latest_attempt_id']}")
            locked = item["status"] == "locked" or not item["prerequisites_met"]
            with status_column:
                status_label = {"up_next": "To do", "current": "In progress", "locked": "Locked", "completed": "Completed"}.get(item["status"], item["status"].replace("_", " "))
                st.markdown(f'<div class="cc-rm-status cc-rm-status-{escape(item["status"])}">{escape(status_label)}</div>', unsafe_allow_html=True)
            with action_column:
                if locked:
                    st.caption("Complete the prerequisites before starting this step.")
                if action in ("assess", "reassess"):
                    if item["skill_name"] in supported and item["status"] != "completed":
                        if st.button(item["title"], key=f"roadmap_assess_{key}", disabled=locked):
                            st.session_state["assessment_skill"] = item["skill_name"]
                            st.session_state.pop("assessment_attempt_id", None)
                            st.switch_page("pages/Assessment.py")
                    elif item["skill_name"] not in supported:
                        st.caption("An assessment is not available for this skill yet.")
                elif action in ("improve", "learn"):
                    reopen = item["status"] == "completed"
                    if st.button("Reopen" if reopen else "Mark complete", key=f"roadmap_toggle_{key}",
                                 disabled=locked and not reopen):
                        try:
                            with session_scope() as session:
                                current_profile = user_service.get_user_profile(session, user_id)
                                if current_profile["target_career_id"] != career_id:
                                    raise ValueError("Your target career changed. Reload your roadmap.")
                                current_items = roadmap_service.get_user_roadmap(session, user_id, career_id)
                                current = next((row for row in current_items if row["item_key"] == key), None)
                                if (current is None or current["action_type"] not in ("improve", "learn")
                                        or (current["status"] == "completed") != reopen
                                        or (not reopen and (current["status"] == "locked" or not current["prerequisites_met"]))):
                                    raise ValueError("This step changed. Reload your roadmap.")
                                mutation = (roadmap_service.mark_roadmap_item_incomplete if reopen
                                            else roadmap_service.mark_roadmap_item_completed)
                                mutation(session, user_id, key)
                        except Exception:
                            st.error("Could not save this roadmap change. No changes were saved. Reload the page and try again.")
                        else:
                            st.rerun()
