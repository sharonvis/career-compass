"""Discover normalized opportunities using backend ranking and match explanations."""
from datetime import date
from html import escape
import re
import streamlit as st
import config
from database.db import SessionLocal, session_scope
from services import application_service, opportunity_service, user_service
from services import opportunity_ingestion_service
from ui.components.sidebar import render_sidebar

st.set_page_config(page_title="Opportunities · Career Compass", page_icon="🧭", layout="wide", initial_sidebar_state="expanded")
render_sidebar("Opportunities")
st.markdown('<p class="cc-header-eyebrow">YOUR NEXT POSSIBILITY</p><h1 class="cc-header-title">Opportunities</h1><p class="cc-header-subtitle">Explore roles that fit your career direction and growing skills.</p>', unsafe_allow_html=True)
user_id = st.session_state.get("user_id")
if type(user_id) is not int:
    st.info("Complete onboarding to discover opportunities.")
    st.page_link("pages/Onboarding.py", label="Go to Onboarding")
    st.stop()
try:
    with SessionLocal() as session:
        profile = user_service.get_user_profile(session, user_id)
        career_id = profile["target_career_id"]
        opportunities = opportunity_service.get_ranked_opportunities(session, user_id, career_id) if career_id is not None else []
        applications = application_service.list_user_applications(session, user_id)
except Exception:
    st.error("Could not load opportunities. Check your profile and database, then try again.")
    st.page_link("pages/Onboarding.py", label="Go to Onboarding")
    st.stop()
if career_id is None:
    st.info("Choose a target career in Onboarding to discover opportunities.")
    st.page_link("pages/Onboarding.py", label="Go to Onboarding")
    st.stop()
notice = st.session_state.pop("opportunity_notice", None)
if notice:
    st.success(notice)
query_col, location_col, sort_col = st.columns([1.4, 1, .7], gap="medium")
with query_col:
    query = st.text_input("Search roles", placeholder="Role, company, or location", key="opportunity_search").strip().casefold()
with location_col:
    location = st.selectbox("Location", [None] + sorted({o["location"] for o in opportunities if o["location"]}), format_func=lambda v: v if v is not None else "Any location", key="opportunity_location")
with sort_col:
    sorting = st.selectbox("Sort by", ("Best match", "Closing soon", "Title"), key="opportunity_sort")
if st.button("Refresh live opportunities", key="refresh_live_opportunities"):
    if not config.get_serpapi_api_key():
        st.info("SerpAPI is not configured yet.")
    else:
        career_name = profile["target_career_name"]
        keywords = {"AI/ML Engineer": "machine learning"}.get(career_name, career_name.casefold())
        search_location = location.strip() if location else None
        if search_location and (
            search_location.casefold() in {"remote", "any location"}
            or re.search(r"\(\s*\+\d+\s+others?\s*\)", search_location, re.IGNORECASE)
        ):
            search_location = None
        try:
            with st.spinner("Refreshing live opportunities..."):
                with session_scope() as session:
                    result = opportunity_ingestion_service.ingest_opportunities(
                        session, "internship", keywords=keywords, location=search_location or None, refresh=True,
                    )
        except Exception:
            st.error("Could not refresh live opportunities. Please try again later. Your stored opportunities remain available.")
        else:
            st.session_state["opportunity_notice"] = (
                "Live opportunity search refreshed."
                if result["fetched"] else "No live opportunities were returned. Your stored opportunities remain available."
            )
            st.rerun()
visible = [o for o in opportunities if (location is None or o["location"] == location)
           and (not query or any(query in (o[field] or "").casefold() for field in ("title", "company", "location")))]
if sorting == "Closing soon":
    visible = sorted(visible, key=lambda o: (o["deadline"] is None, o["deadline"] or date.max))
elif sorting == "Title":
    visible = sorted(visible, key=lambda o: o["title"].casefold())
st.caption(f"Showing {len(visible)} of {len(opportunities)} opportunities for {profile['target_career_name']}")
st.page_link("pages/Applications.py", label="View Applications")
if not visible:
    st.info("No opportunities match your current career and filters.")
tracked = {a["opportunity_id"]: a["status"] for a in applications}
columns = st.columns(2, gap="large")
for index, item in enumerate(visible):
    oid = item["opportunity_id"]
    with columns[index % 2]:
        with st.container(key=f"cc-card-opportunity-{oid}"):
            st.markdown(f'<p class="cc-stat-label">{escape(item["company"])}</p><h3>{escape(item["title"])}</h3>', unsafe_allow_html=True)
            st.caption(f"{item['location'] or 'Location not specified'} · {item['opportunity_type']}")
            st.write("Match: " + (item["match_band"].replace("_", " ").title() if item["match_band"] else "Unavailable"))
            if not item["eligibility_checked"]:
                st.caption("Eligibility requirements have not been checked.")
            st.caption(f"Deadline: {item['deadline'] or 'Not specified'}")
            with st.expander("Opportunity details"):
                for field, label in (("required_skills", "Required skills"), ("optional_skills", "Optional skills")):
                    st.write(label)
                    if not item[field]:
                        st.caption("None listed")
                    for skill in item[field]:
                        st.write(f"{skill['skill_name']} — required level {skill['required_level']}; claimed {skill['claimed_level']}; demonstrated {skill['demonstrated_level'] if skill['demonstrated_level'] is not None else 'Unassessed'}")
                for reason in item["reasons"]:
                    st.write(reason["text"])
                source_label = "DEMO DATA" if item["is_seeded"] else "LIVE" if item["source"] == "serpapi" else item["source"]
                st.caption(f"Source: {source_label}")
            if item["source_url"]:
                st.link_button("View opportunity", item["source_url"])
            if oid in tracked:
                st.caption(f"Tracking status: {tracked[oid]}")
            if st.button("Save opportunity" if oid not in tracked else "Saved / tracked", key=f"save_opportunity_{oid}"):
                try:
                    with session_scope() as session:
                        application_service.save_opportunity(session, user_id, oid)
                except Exception:
                    st.error("Could not save this opportunity. No changes were saved. Please try again.")
                else:
                    st.session_state["opportunity_notice"] = "Opportunity saved. Your existing tracking status and notes were preserved."
                    st.rerun()
