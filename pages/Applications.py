"""Persisted application tracking through the application service."""
from datetime import datetime
from html import escape
from pathlib import Path
import base64
import streamlit as st
from database.db import SessionLocal, session_scope
from services import application_service, user_service
from ui.components.sidebar import render_sidebar

st.set_page_config(page_title="Applications · Career Compass", page_icon="🧭", layout="wide", initial_sidebar_state="expanded")
render_sidebar("Applications")
assets = Path(__file__).resolve().parents[1] / "assets"
st.markdown('<style>' + (assets / "applications.css").read_text(encoding="utf-8") + '</style>', unsafe_allow_html=True)
@st.cache_data(show_spinner=False)
def application_header_art(path, modified_at):
    return base64.b64encode(Path(path).read_bytes()).decode("ascii")

def application_display_date(value):
    if value is None:
        return "Not specified"
    try:
        return datetime.fromisoformat(str(value)).strftime("%b %d, %Y")
    except ValueError:
        return str(value)

art_path = assets / "images" / "applications_hero.png"
if art_path.is_file():
    art = application_header_art(str(art_path), art_path.stat().st_mtime_ns)
    st.markdown('<style>.cc-app-heading::before{background-image:url("data:image/png;base64,' + art + '");}</style>', unsafe_allow_html=True)
user_id = st.session_state.get("user_id")
if type(user_id) is not int:
    st.info("Complete onboarding to load your applications.")
    st.page_link("pages/Onboarding.py", label="Go to Onboarding")
    st.stop()
try:
    with SessionLocal() as session:
        user_service.get_user_profile(session, user_id)
        applications = application_service.list_user_applications(session, user_id)
        counts = application_service.get_application_status_counts(session, user_id)
except Exception:
    st.error("Could not load applications. Check your profile and database, then try again.")
    st.page_link("pages/Onboarding.py", label="Go to Onboarding")
    st.stop()
notice = st.session_state.pop("application_notice", None)
if notice:
    st.success(notice)
with st.container(key="cc-app-hero"):
    st.markdown('<div class="cc-app-heading"><p>YOUR JOB SEARCH</p><h1>Applications</h1><div>Keep your opportunities organized from first look to final decision.</div></div>', unsafe_allow_html=True)
    with st.container(key="cc-app-counts"):
        icons = {"saved": "bookmark", "applied": "send", "interview": "group", "offer": "emoji_events", "rejected": "close", "withdrawn": "remove_circle_outline"}
        for col, (status, count) in zip(st.columns(len(counts)), counts.items()):
            with col:
                with st.container(key=f"cc-app-count-{status}"):
                    st.markdown('<span class="cc-app-count-icon material-symbols-rounded" aria-hidden="true">' + icons.get(status, "bookmark") + '</span>', unsafe_allow_html=True)
                    st.metric(status.title(), count)
with st.container(key="cc-app-filters"):
    selected = st.radio("Application status", [None] + list(application_service.APPLICATION_STATUSES), format_func=lambda v: v.title() if v else "All applications", horizontal=True, key="application_status_filter")
with st.container(key="cc-app-add-link"):
    st.page_link("pages/Opportunities.py", label="Add application from Opportunities")
visible = [a for a in applications if selected is None or a["status"] == selected]
st.caption(f"Showing {len(visible)} applications")
if not visible:
    st.info("No tracked applications match this filter. Save an opportunity to start tracking.")
with st.container(key="cc-app-grid"):
    for item in visible:
        aid = item["application_id"]
        opportunity = item["opportunity"]
        # Versioned keys refresh widgets after persisted changes or a different user.
        version = f"{user_id}_{aid}_{item['updated_at']}"
        with st.container(key=f"cc-card-application-{aid}"):
            st.markdown(f'<div class="cc-app-company"><span class="cc-app-monogram" aria-hidden="true">{escape(opportunity["company"][:1].upper())}</span><div><strong>{escape(opportunity["company"])}</strong><small>{escape(opportunity["location"] or "Location not specified")} &middot; {escape(opportunity["opportunity_type"])}</small></div></div><h3>{escape(opportunity["title"])}</h3><span class="cc-app-status" aria-label="Status: {escape(item["status"])}">{escape(item["status"].title())}</span>', unsafe_allow_html=True)
            st.caption(f"Saved: {application_display_date(item['created_at'])} · Last updated: {application_display_date(item['updated_at'])}")
            st.caption(f"Deadline: {application_display_date(opportunity['deadline'])}")
            if opportunity["is_expired"]:
                st.caption("This opportunity has expired. Your tracking history is retained.")
            if opportunity["source_url"]:
                st.link_button("View opportunity", opportunity["source_url"])
            st.markdown('<div class="cc-app-notes"><span>Notes</span><p>' + escape(item["notes"] or "No notes yet.") + '</p></div>', unsafe_allow_html=True)
            with st.expander("Update status / Edit notes"):
                with st.form(f"application_edit_{version}"):
                    new_status = st.selectbox("Status", application_service.APPLICATION_STATUSES, index=application_service.APPLICATION_STATUSES.index(item["status"]), key=f"application_status_{version}")
                    notes = st.text_area("Notes", value=item["notes"] or "", help=f"Up to {application_service.MAX_NOTES_LENGTH} characters. Blank notes clear the saved note.", key=f"application_notes_{version}")
                    update_status = st.form_submit_button("Update status")
                    update_notes = st.form_submit_button("Save notes")
            remove = st.button("Remove saved application", key=f"application_remove_{aid}", disabled=item["status"] != "saved")
            if item["status"] != "saved":
                st.caption("Only applications in saved status can be removed.")
            if update_status or update_notes or remove:
                try:
                    with session_scope() as session:
                        if remove:
                            application_service.remove_saved_application(session, user_id, aid)
                        elif update_status:
                            application_service.update_application_status(session, user_id, aid, new_status)
                        else:
                            application_service.update_application_notes(session, user_id, aid, notes)
                except application_service.ApplicationNotRemovableError:
                    st.error("This application is no longer saved and cannot be removed. Reload to see its current status.")
                except ValueError as error:
                    st.error(f"Could not save changes: {error}")
                except Exception:
                    st.error("Could not save this application change. No changes were saved. Reload and try again.")
                else:
                    st.session_state["application_notice"] = "Application changes saved."
                    st.rerun()
