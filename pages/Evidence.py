"""Supporting evidence metadata; this page never establishes demonstrated skills."""
from datetime import date
import streamlit as st
from database.db import SessionLocal, session_scope
from services import evidence_service, progress_service, user_service
from ui.components.header import render_header
from ui.components.sidebar import render_sidebar

st.set_page_config(page_title="Evidence · Career Compass", page_icon="🧭", layout="wide", initial_sidebar_state="expanded")
render_sidebar("Evidence")
render_header("Evidence and credentials", "Keep supporting records alongside your career profile.", "YOUR EVIDENCE")
user_id = st.session_state.get("user_id")
if type(user_id) is not int:
    st.info("Complete onboarding to manage evidence.")
    st.page_link("pages/Onboarding.py", label="Go to Onboarding")
    st.stop()
try:
    with SessionLocal() as session:
        user_service.get_user_profile(session, user_id)
        catalog = {skill["skill_id"]: skill["name"] for skill in user_service.list_skills(session)}
        evidence = evidence_service.list_user_evidence(session, user_id)
except Exception:
    st.error("Could not load evidence. Check your profile and database, then try again.")
    st.page_link("pages/Onboarding.py", label="Go to Onboarding")
    st.stop()
st.caption("Evidence is supporting metadata. It does not verify skills or change demonstrated levels, readiness, skill gaps, or your next action.")
notice = st.session_state.pop("evidence_notice", None)
if notice:
    st.success(notice)
with st.container(key="cc-card-evidence-add"):
    st.subheader("Add evidence")
    if not catalog:
        st.info("No skills are available in the catalog.")
    else:
        with st.form(f"evidence_add_{user_id}", clear_on_submit=True):
            title = st.text_input("Title", key="evidence_add_title")
            issuer = st.text_input("Issuer", key="evidence_add_issuer")
            skill_id = st.selectbox("Skill", list(catalog), format_func=lambda sid: catalog[sid], key="evidence_add_skill")
            url = st.text_input("URL", key="evidence_add_url", help="Optional HTTP or HTTPS link. Certificates are not fetched or verified.")
            evidence_date = st.date_input("Evidence date", value=None, min_value=date(1900, 1, 1), key="evidence_add_date")
            add = st.form_submit_button("Add evidence")
        if add:
            try:
                with session_scope() as session:
                    existing_ids = {row["evidence_id"] for row in evidence_service.list_user_evidence(session, user_id)}
                    added = evidence_service.add_evidence(session, user_id, skill_id, title, issuer, url, evidence_date)
                    if added["evidence_id"] not in existing_ids:
                        # Activity subjects allow 100 characters; evidence titles allow 200.
                        progress_service.record_progress_event(session, user_id, "evidence_added", subject=added["title"][:100])
            except ValueError as error:
                st.error(f"Could not add evidence: {error}")
            except Exception:
                st.error("Could not add evidence. No changes were saved. Please try again.")
            else:
                st.session_state["evidence_notice"] = "Evidence saved."
                st.rerun()
st.subheader("Your evidence")
if not evidence:
    st.info("No evidence added yet.")
for item in evidence:
    eid = item["evidence_id"]
    # Refresh widgets after edits while keeping only simple widget values in state.
    version = f"{user_id}_{eid}_{item['title']}_{item['issuer']}_{item['url']}_{item['evidence_date']}"
    with st.container(key=f"cc-card-evidence-{eid}"):
        st.subheader(item["title"])
        st.caption(f"Skill: {item['skill_name']} · Issuer: {item['issuer'] or 'Not specified'} · Date: {item['evidence_date'] or 'Not specified'}")
        if item["url"]:
            st.link_button("Open evidence link", item["url"])
        with st.expander("Edit evidence"):
            st.caption("The linked skill is fixed for an existing record. Delete and add a new record to choose a different skill.")
            with st.form(f"evidence_edit_{version}"):
                edit_title = st.text_input("Title", value=item["title"])
                edit_issuer = st.text_input("Issuer", value=item["issuer"] or "")
                edit_url = st.text_input("URL", value=item["url"] or "")
                edit_date = st.date_input("Evidence date", value=item["evidence_date"], min_value=date(1900, 1, 1))
                edit = st.form_submit_button("Save evidence")
        delete = st.button("Delete evidence", key=f"evidence_delete_{eid}")
        if edit or delete:
            try:
                with session_scope() as session:
                    evidence_service.get_evidence(session, user_id, eid)
                    if delete:
                        evidence_service.delete_evidence(session, user_id, eid)
                    else:
                        evidence_service.update_evidence(session, user_id, eid, title=edit_title, issuer=edit_issuer, url=edit_url, evidence_date=edit_date)
            except ValueError as error:
                st.error(f"Could not save evidence: {error}")
            except Exception:
                st.error("Could not change evidence. No changes were saved. Reload and try again.")
            else:
                st.session_state["evidence_notice"] = "Evidence deleted." if delete else "Evidence updated."
                st.rerun()
st.page_link("pages/Dashboard.py", label="View recent activity on Dashboard")
