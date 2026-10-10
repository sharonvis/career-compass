"""Read-only dashboard projections from existing backend services."""
import base64
from pathlib import Path
from html import escape

import streamlit as st

from database.db import SessionLocal
from services import (application_service, assessment_service, career_service, opportunity_service,
                      progress_service, roadmap_service, user_service)
from ui.components.sidebar import render_sidebar

st.set_page_config(page_title="Dashboard · Career Compass", page_icon="🧭",
                   layout="wide", initial_sidebar_state="expanded")
render_sidebar("Dashboard")
assets = Path(__file__).resolve().parents[1] / "assets"
st.markdown(f"<style>{(assets / 'dashboard.css').read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)
st.markdown('<div class="cc-dashboard-shell" aria-hidden="true"></div>', unsafe_allow_html=True)


def decorative_art(filename, css_class):
    """Local decorative art with a plain palette fallback when absent."""
    path = assets / "dashboard" / filename
    if not path.is_file():
        return f'<div class="{css_class} cc-db-art-fallback" aria-hidden="true"></div>'
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f'<div class="{css_class}" aria-hidden="true"><img src="data:image/png;base64,{encoded}" alt=""></div>'

user_id = st.session_state.get("user_id")
if type(user_id) is not int:
    st.info("Complete onboarding to load your Career Compass.")
    st.page_link("pages/Onboarding.py", label="Go to Onboarding")
    st.stop()

try:
    with SessionLocal() as session:
        profile = user_service.get_user_profile(session, user_id)
        career_id = profile["target_career_id"]
        if career_id is None:
            st.info("Choose a target career in Onboarding to load your dashboard.")
            st.page_link("pages/Onboarding.py", label="Go to Onboarding")
            st.stop()
        summary = career_service.get_user_career_summary(session, user_id, career_id)
        roadmap = roadmap_service.get_user_roadmap(session, user_id, career_id)
        opportunities = opportunity_service.get_ranked_opportunities(session, user_id, career_id, limit=3)
        counts = application_service.get_application_status_counts(session, user_id)
        activity = progress_service.list_recent_progress_events(session, user_id, limit=5)
except Exception:
    st.error("Could not load your dashboard. Check your profile and database, then try again.")
    st.page_link("pages/Onboarding.py", label="Go to Onboarding")
    st.stop()

# A: Hero, real readiness projections, and the presentation-only product loop.
with st.sidebar:
    sidebar_panel = next((path for path in (assets / "dashboard").glob("side_panel.*") if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}), None)
    if sidebar_panel:
        st.markdown(decorative_art(sidebar_panel.name, "cc-db-sidebar-art"), unsafe_allow_html=True)
    st.markdown(f'<div class="cc-db-user-chip"><span>{escape(profile["name"])}</span><small>{escape(summary["career_name"])}</small></div>', unsafe_allow_html=True)
with st.container(key="dashboard-hero-next-action"):
    hero_image_path = assets / "dashboard" / "hero_banner.png"
    hero_image = base64.b64encode(hero_image_path.read_bytes()).decode("ascii")
    st.markdown(f'<div class="cc-db-hero-art" aria-hidden="true"><img src="data:image/png;base64,{hero_image}" alt=""></div>', unsafe_allow_html=True)
    first_name = profile["name"].strip().split()[0].title() if profile["name"].strip() else ""
    st.markdown(f'<div class="cc-db-greeting" aria-label="Signed in as {escape(profile["name"])}">Good morning, {escape(first_name)}.</div>'
                f'<div class="cc-db-target">Target &middot; {escape(summary["career_name"])}</div>'
                '<p class="cc-db-label">NEXT ACTION</p>', unsafe_allow_html=True)
    action = summary["next_action"]
    if action is None:
        st.markdown('<h1 class="cc-db-action">Up to date<span>.</span></h1>', unsafe_allow_html=True)
    else:
        st.markdown(f'<h1 class="cc-db-action">{escape(action["action_type"].capitalize())} {escape(action["skill_name"])}<span>.</span></h1>', unsafe_allow_html=True)
        if action["action_type"] == "assess":
            supported = {item["skill_name"] for item in assessment_service.list_supported_assessments()}
            if action["skill_name"] in supported:
                if st.button("Start Assessment", key="dashboard_start_assessment"):
                    st.session_state["assessment_skill"] = action["skill_name"]
                    st.session_state.pop("assessment_attempt_id", None)
                    st.switch_page("pages/Assessment.py")
            else:
                st.caption("Assessment is not available for this skill.")
        elif action["action_type"] in {"improve", "learn"}:
            st.caption("See the current roadmap preview below for learning guidance.")


with st.container(key="dashboard-stats"):
    metrics = (("Claimed Readiness", summary["claimed_readiness"], "claimed"),
               ("Effective Readiness", summary["effective_readiness"], "demonstrated"),
               ("Assessment Coverage", summary["assessment_coverage"], "coverage"))
    for col, (label, value, key) in zip(st.columns(3, gap="small"), metrics):
        with col:
            with st.container(key=f"dashboard-metric-{key}"):
                st.metric(label, f"{value:.1%}")
                caption = {"claimed": "From your self-ratings", "demonstrated": "Includes discounted unassessed claims", "coverage": "Weighted by skill importance"}[key]
                st.markdown(f'<div class="cc-db-metric-caption">{caption}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="cc-db-meter" role="img" aria-label="{escape(label)} {value:.1%}"><i style="width:{value:.6%}"></i></div>', unsafe_allow_html=True)

st.markdown('<div class="cc-db-loop-module"><p class="cc-db-loop-heading">CAREER COMPASS LOOP</p><div class="cc-db-loop-nodes">' + ''.join(f'<div class="cc-db-loop-step"><span class="cc-db-loop-number">{i:02}</span><span class="cc-db-loop-name">{label}</span></div>' for i, label in enumerate(("Claim", "Assess", "Find gap", "Improve", "Reassess"), 1)) + '</div></div>', unsafe_allow_html=True)

# B: Confirmed gaps and a three-item, backend-ordered roadmap preview.
with st.container(key="dashboard-middle"):
    gaps_card, roadmap_card = st.columns([.94, 1.06], gap="medium")
    with gaps_card:
        with st.container(key="dashboard-important-gaps"):
            st.markdown('<div class="cc-db-gap-eyebrow">CONFIRMED GAPS</div>', unsafe_allow_html=True)
            if not summary["confirmed_gaps"]:
                magnifier = base64.b64encode((assets / "images" / "Findthegap.png").read_bytes()).decode("ascii")
                st.markdown(f'<div class="cc-db-gap-empty"><div><h3>No confirmed gaps yet</h3><p>Unassessed skills are not confirmed gaps.</p></div><img src="data:image/png;base64,{magnifier}" alt="" aria-hidden="true"></div>', unsafe_allow_html=True)
            for gap in summary["confirmed_gaps"]:
                skill = next(skill for skill in summary["skills"] if skill["name"] == gap["skill_name"])
                st.markdown(f'<div class="cc-db-gap"><b>{escape(gap["skill_name"])}</b><div><span>Claimed {skill["claimed_level"]}</span><span>Demonstrated {gap["demonstrated_level"]}</span></div></div>', unsafe_allow_html=True)
    with roadmap_card:
        with st.container(key="dashboard-current-roadmap"):
            completed = sum(item["status"] == "completed" for item in roadmap)
            st.markdown(f'<div class="cc-db-roadmap-header"><h2>CURRENT ROADMAP</h2><span>{completed} of {len(roadmap)} completed</span></div>', unsafe_allow_html=True)
            if not roadmap:
                st.markdown('<p class="cc-db-muted">No roadmap items are currently recommended.</p>', unsafe_allow_html=True)
            else:
                current_index = next((i for i, item in enumerate(roadmap) if item["status"] == "current"), 0)
                preview = roadmap[current_index:current_index + 3]
                segments = ''.join(f'<span class="{"done" if i < completed else ""}"></span>' for i in range(len(roadmap)))
                st.markdown(f'<div class="cc-db-segments" role="img" aria-label="{completed} of {len(roadmap)} completed">{segments}</div>', unsafe_allow_html=True)
                rows = []
                for item in preview:
                    state = escape(item["status"], quote=True)
                    status = escape(item["status"].replace("_", " "))
                    node = "&#10003;" if item["status"] == "completed" else ""
                    chip_icon = "&#128274; " if item["status"] == "locked" else ""
                    description = f'<div class="cc-db-roadmap-description">{escape(item["reason"])}</div>' if item["status"] == "current" and "unverified learning guidance" not in item.get("reason", "") else ""
                    rows.append(f'<div class="cc-db-roadmap {state}"><span class="cc-db-node" aria-hidden="true">{node}</span><div class="cc-db-roadmap-copy"><b>{escape(item["title"])}</b>{description}</div><span class="cc-db-status">{chip_icon}{status}</span></div>')
                st.markdown('<div class="cc-db-roadmap-rows">' + ''.join(rows) + '</div>', unsafe_allow_html=True)
                guidance = next((item["reason"] for item in roadmap if "unverified learning guidance" in item.get("reason", "")), None)
                if guidance:
                    st.markdown(f'<div class="cc-db-roadmap-footnote">{escape(guidance)}</div>', unsafe_allow_html=True)
            st.page_link("pages/Roadmap.py", label="View Full Roadmap", width="content")

# C: Ranked opportunities, application counts, and persisted progress events.
def opportunity_card_html(opportunity, index):
    """Single-line presentation only; service fields remain unmodified."""
    from datetime import date, datetime

    def text(value):
        if value is None or str(value).strip().lower() in {"", "none", "nan"}:
            return ""
        return escape(str(value))

    band = opportunity.get("match_band")
    band_class = {"strong": "strong", "good": "good", "stretch": "stretch", "not_eligible": "ineligible"}.get(band, "neutral")
    chip = f'<div class="cc-opps-band cc-opps-band-{band_class}">{text(band)}</div>' if text(band) else ""
    title = f'<h3>{text(opportunity.get("title"))}</h3>' if text(opportunity.get("title")) else ""
    company = f'<div class="cc-opps-company">{text(opportunity.get("company"))}</div>' if text(opportunity.get("company")) else ""
    featured = index == 1
    eyebrow = '<div class="cc-opps-feature-label">TOP MATCH</div>' if featured else ""
    location = text(opportunity.get("location"))
    kind = text(opportunity.get("opportunity_type"))
    context = '<div class="cc-opps-context">' + '<span class="cc-opps-separator" aria-hidden="true"> &middot; </span>'.join(value for value in (location, kind) if value) + '</div>' if location or kind else ""
    footer = []
    deadline = opportunity.get("deadline")
    if text(deadline):
        parsed = deadline
        if isinstance(deadline, str):
            try:
                parsed = date.fromisoformat(deadline)
            except ValueError:
                pass
        shown = f'{parsed.day} {parsed.strftime("%b %Y").upper()}' if isinstance(parsed, (date, datetime)) else str(deadline)
        footer.append(f'<span>{text(shown)}</span>')
    if type(opportunity.get("is_seeded")) is bool:
        footer.append('<span class="cc-opps-source">' + ('DEMO DATA' if opportunity["is_seeded"] else 'LIVE') + '</span>')
    elif text(opportunity.get("source")):
        footer.append(f'<span class="cc-opps-source">{text(opportunity["source"])}</span>')
    metadata = '<div class="cc-opps-details">' + ''.join(footer) + '</div>' if footer else ""
    reason_rows = []
    reason_styles = {"demonstrated_gap": ("gap", "Skill gap", "Required skills"), "unverified_but_claimed": ("unverified", "Claim meets requirement / Unverified", "Required skills"), "claimed_below_requirement": ("unverified", "Below requirement / Unverified", "Required skills"), "all_required_skills_met": ("met", "Met", "Required skills"), "optional_skills_missing": ("optional", "Optional", "Optional skills"), "hard_filter_failed": ("gap", "Not met", "Eligibility"), "no_required_skills": ("neutral", "Not mapped", "Required skills")}
    for reason in opportunity.get("reasons", []):
        presentation = reason_styles.get(reason.get("code"))
        if presentation is None:
            continue
        style, label, group = presentation
        name = text(reason.get("skill_name")) or text(reason.get("filter")) or group
        reason_rows.append(f'<div class="cc-opps-reason-row"><span class="cc-opps-signal-name">{name}</span><span class="cc-opps-reason-badge cc-opps-reason-{style}">{label}</span></div>')
    signals = reason_rows[:3 if featured else 2]
    reasons = '<div class="cc-opps-reasons"><div class="cc-opps-reasons-label">MATCH SIGNALS</div>' + ''.join(signals) + '</div>' if signals else ""
    treatment = "featured" if featured else "secondary"
    art = f'<div class="cc-opps-polish-art cc-opps-polish-art-{index}" aria-hidden="true"></div>'
    return f'<div class="cc-opps-card cc-opps-{treatment}">{art}<div class="cc-opps-body">{eyebrow}<div class="cc-opps-top">{chip}</div>{title}{company}{context}{reasons}{metadata}</div></div>'


with st.container(key="dashboard-recommended-opportunity"):
    art_rules = []
    encoded_images = {}
    for index in range(1, 4):
        image = next((path for path in (assets / "dashboard").glob(f"opp_{index}.*") if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}), assets / "dashboard" / "hero_banner.png")
        if image.is_file():
            if image not in encoded_images:
                encoded_images[image] = base64.b64encode(image.read_bytes()).decode("ascii")
            mime = "image/jpeg" if image.suffix.lower() in {".jpg", ".jpeg"} else f"image/{image.suffix[1:].lower()}"
            art_rules.append(f'.cc-opps .cc-opps-polish-art-{index}::before' + '{background-image:url("data:' + mime + ';base64,' + encoded_images[image] + '");}')
    st.markdown('<style>' + ''.join(art_rules) + '</style>', unsafe_allow_html=True)
    header = '<div class="cc-opps-header"><div class="cc-opps-eyebrow">TOP RANKED MATCHES</div><h2>Recommended Opportunities</h2></div>'
    cards = '<div class="cc-opps-grid">' + ''.join(opportunity_card_html(item, i) for i, item in enumerate(opportunities[:3], 1)) + '</div>' if opportunities else '<div class="cc-opps-empty">No matching opportunities available yet.</div>'
    st.markdown('<div class="cc-opps">' + header + cards + '</div>', unsafe_allow_html=True)
with st.container(key="dashboard-bottom"):
    applications_column, activity_column = st.columns([7, 5], gap="medium")
    with applications_column:
        with st.container(key="dashboard-applications"):
            st.markdown('<div class="cc-db-bottom-eyebrow">APPLICATIONS</div>', unsafe_allow_html=True)
            primary = ''.join(f'<div class="cc-db-application-tile {"zero" if counts[status] == 0 else "nonzero"}"><div class="cc-db-application-value">{escape(str(counts[status]))}</div><div class="cc-db-application-label">{escape(status)}</div></div>' for status in ("saved", "applied", "interview", "offer"))
            secondary = ''.join(f'<div class="cc-db-application-secondary-item {"zero" if counts[status] == 0 else "nonzero"}"><span>{escape(status.capitalize())}</span><b>{escape(str(counts[status]))}</b></div>' for status in ("rejected", "withdrawn"))
            st.markdown('<div class="cc-db-application-tiles">' + primary + '</div><div class="cc-db-application-secondary">' + secondary + '</div>', unsafe_allow_html=True)
            st.page_link("pages/Applications.py", label="Open applications", width="content")
    with activity_column:
        with st.container(key="dashboard-recent-activity"):
            st.markdown('<div class="cc-db-bottom-eyebrow">RECENT ACTIVITY</div>', unsafe_allow_html=True)
            if not activity:
                st.markdown('<div class="cc-db-activity-empty"><span aria-hidden="true"></span><div>No recent activity yet.</div></div>', unsafe_allow_html=True)
            else:
                events = []
                for event in activity[:5]:
                    label = event["description"] or event["event_type"].replace("_", " ")
                    timestamp = event["created_at"].strftime("%d %b %Y, %H:%M UTC") if event["created_at"] else ''
                    events.append(f'<div class="cc-db-event"><span aria-hidden="true"></span><div><p>{escape(label)}</p><time>{escape(timestamp)}</time></div></div>')
                st.markdown('<div class="cc-db-timeline">' + ''.join(events) + '</div>', unsafe_allow_html=True)
