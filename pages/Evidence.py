"""Supporting evidence metadata; this page never establishes demonstrated skills."""
from contextlib import ExitStack
from datetime import date
from html import escape
from pathlib import Path
import base64
import streamlit as st
from database.db import SessionLocal, session_scope
from services import evidence_service, evidence_storage_service, progress_service, user_service
from ui.components.header import render_header
from ui.components.sidebar import render_sidebar

st.set_page_config(page_title="Evidence · Career Compass", page_icon="🧭", layout="wide", initial_sidebar_state="expanded")
render_sidebar("Evidence")
render_header()
st.markdown("<style>" + (Path(__file__).resolve().parents[1] / "assets/evidence.css").read_text(encoding="utf-8-sig") + "</style>", unsafe_allow_html=True)
@st.cache_data
def evidence_art(path, modified):
    return base64.b64encode(Path(path).read_bytes()).decode("ascii")
art_path = Path(__file__).resolve().parents[1] / "assets/images/EVIDENCE.png"
art = evidence_art(str(art_path), art_path.stat().st_mtime_ns)
st.markdown(f'<div class="cc-ev-hero"><img src="data:image/png;base64,{art}" alt="" aria-hidden="true"><div class="cc-ev-hero-copy"><p>YOUR EVIDENCE</p><h1>Evidence and credentials</h1><div>Keep supporting records alongside your career profile.</div><small>Evidence is supporting metadata. It does not verify skills or change demonstrated levels, readiness, skill gaps, or your next action.</small></div></div>', unsafe_allow_html=True)
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

notice = st.session_state.pop("evidence_notice", None)
if notice:
    st.success(notice)
with st.container(key="cc-card-evidence-add"):
    st.subheader("Add evidence")
    if not catalog:
        st.info("No skills are available in the catalog.")
    else:
        with st.form(f"evidence_add_{user_id}", clear_on_submit=True):
            upload_col, fields_col = st.columns([1, 2.1], gap="medium")
            with upload_col, st.container(key="cc-ev-upload-box"):
                st.markdown('<div class="cc-ev-upload-intro"><span aria-hidden="true">&#8679;</span><strong>Upload certificate or document</strong><small>PDF, PNG, JPG, JPEG (max 10 MB)</small></div>', unsafe_allow_html=True)
                attachment = st.file_uploader("Certificate attachment (optional)", type=["pdf", "png", "jpg", "jpeg"], max_upload_size=10, key="evidence_add_attachment", help="One PDF or certificate image, up to 10 MB. Supporting evidence only; not skill verification.")
            with fields_col:
                left, right = st.columns(2)
                with left:
                    title = st.text_input("Title", key="evidence_add_title", placeholder="e.g. Python for Data Science Certificate")
                    skill_id = st.selectbox("Skill", list(catalog), format_func=lambda sid: catalog[sid], key="evidence_add_skill")
                    evidence_date = st.date_input("Evidence date", value=None, min_value=date(1900, 1, 1), key="evidence_add_date")
                with right:
                    issuer = st.text_input("Issuer", key="evidence_add_issuer", placeholder="e.g. Coursera, NPTEL")
                    url = st.text_input("URL", key="evidence_add_url", placeholder="https://...", help="Optional HTTP or HTTPS link. Certificates are not fetched or verified.")
                    add = st.form_submit_button("Add evidence")
        if add:
            try:
                with ExitStack() as cleanup:
                    with session_scope() as session:
                        existing_ids = {row["evidence_id"] for row in evidence_service.list_user_evidence(session, user_id)}
                        added = evidence_service.add_evidence(session, user_id, skill_id, title, issuer, url, evidence_date)
                        if attachment is not None:
                            cleanup.enter_context(evidence_storage_service.stage_attachment(session, user_id, added["evidence_id"], attachment.name, attachment.getvalue(), attachment.type))
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
st.html(f'<div class="cc-ev-list-heading"><div class="cc-ev-list-title">Your evidence</div><span>{len(evidence)}</span></div>')
if not evidence:
    st.markdown('<div class="cc-ev-empty">No evidence added yet.</div>', unsafe_allow_html=True)
with st.container(key="cc-ev-grid"):
    for item in evidence:
        eid = item["evidence_id"]
        # Refresh widgets after edits while keeping only simple widget values in state.
        version = f"{user_id}_{eid}_{item['title']}_{item['issuer']}_{item['url']}_{item['evidence_date']}"
        with st.container(key=f"cc-card-evidence-{eid}"):
            st.markdown(f'<div class="cc-ev-record"><span class="cc-ev-record-tag">Supporting evidence</span><h3>{escape(item["title"])}</h3><p>{escape(item["issuer"] or "Not specified")}</p><span class="cc-ev-skill">{escape(item["skill_name"])}</span><small>{escape(str(item["evidence_date"] or "Not specified"))}</small></div>', unsafe_allow_html=True)
            if item["url"]:
                st.link_button("Open evidence link", item["url"])
            try:
                with SessionLocal() as session:
                    stored_attachment = evidence_storage_service.get_attachment(session, user_id, eid)
                if stored_attachment is not None:
                    if stored_attachment["mime_type"].startswith("image/"):
                        st.image(stored_attachment["data"], width=110)
                    st.caption(f"Attachment: {stored_attachment['original_filename']} | {stored_attachment['mime_type']} | {stored_attachment['size'] / 1024:.1f} KB")
                    st.download_button("Download attachment", data=stored_attachment["data"], file_name=stored_attachment["original_filename"], mime=stored_attachment["mime_type"], key=f"evidence_download_{eid}")
            except Exception:
                st.warning("This attachment could not be loaded. Your evidence metadata remains available.")
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
                    with ExitStack() as cleanup:
                        with session_scope() as session:
                            evidence_service.get_evidence(session, user_id, eid)
                            if delete:
                                cleanup.enter_context(evidence_storage_service.delete_attachment_after_commit(session, user_id, eid))
                                evidence_service.delete_evidence(session, user_id, eid)
                            else:
                                evidence_service.update_evidence(session, user_id, eid, title=edit_title, issuer=edit_issuer, url=edit_url, evidence_date=edit_date)
                except evidence_storage_service.AttachmentCleanupError:
                    st.warning("Evidence was deleted, but its attachment could not be removed from local storage. Please check file permissions.")
                except ValueError as error:
                    st.error(f"Could not save evidence: {error}")
                except Exception:
                    st.error("Could not change evidence. No changes were saved. Reload and try again.")
                else:
                    st.session_state["evidence_notice"] = "Evidence deleted." if delete else "Evidence updated."
                    st.rerun()
st.page_link("pages/Dashboard.py", label="View recent activity on Dashboard")
