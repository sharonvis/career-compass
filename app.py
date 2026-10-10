"""Public Career Compass landing page."""

import base64
from pathlib import Path

import streamlit as st

st.set_page_config(
    page_title="Career Compass",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="collapsed",
)

ROOT = Path(__file__).resolve().parent
ASSET = ROOT / "assets" / "images"


def image_uri(name: str) -> str:
    path = ASSET / name
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


css = (ROOT / "assets" / "styles.css").read_text(encoding="utf-8")
# Load the landing's font set here; other pages retain the shared font import.
css = "\n".join(line for line in css.splitlines() if not line.startswith("@import "))
st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

with st.container(key="cc-public-landing"):
    st.markdown(
        f"""
        <div class="cc-landing">
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:wght@600;700;800&amp;family=Inter:wght@400;500;600;700&amp;family=JetBrains+Mono:wght@500;600&amp;display=swap">
        <header id="top" class="topbar">
          <a class="brand" href="#top" target="_self"><span class="brand-mark" aria-hidden="true"><img src="{image_uri('CareerCompassLogo.png')}" alt=""></span><span>CAREER COMPASS</span></a>
          <nav aria-label="Main navigation"><a href="#how" target="_self">How It Works</a><a href="#about" target="_self">About</a><a class="signin" href="#start" target="_self">Sign In</a></nav>
        </header>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.container(key="landing-hero"):
        hero_copy, hero_art = st.columns([1.55, .85], vertical_alignment="center")
        with hero_copy:
            st.markdown(
                """
                <div class="cc-landing hero-copy">
                  <div class="eyebrow">CLAIM &middot; ASSESS &middot; IMPROVE</div>
                  <h1><span class="hero-line">Know what you know.</span><em class="hero-line">Know what to do next.</em></h1>
                  <p>Career Compass compares the skills you claim with what you can<br class="desktop"> actually demonstrate, then turns that gap into your next best action.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            with st.container(key="landing-hero-cta"):
                st.page_link(
                    "pages/Onboarding.py",
                    label="Get Started",
                    icon=":material/arrow_forward:",
                    width="content",
                )
        with hero_art:
            st.image(
                ASSET / "Peopleoncompass.png",
                
                width="stretch",
            )

    st.markdown(
        f"""
        <div class="cc-landing">
        <section id="about" class="features">
          <div class="eyebrow">WHAT CAREER COMPASS DOES</div>
          <div class="feature-grid">
            <article class="feature-card card-one"><span class="feature-index" aria-hidden="true">01</span><h3 class="feature-title">Assess Your Skills</h3><p>Take focused assessments and<br> see your demonstrated level.</p><img src="{image_uri('Assessyouskills.png')}" alt=""></article>
            <article class="feature-card card-two"><span class="feature-index" aria-hidden="true">02</span><h3 class="feature-title">Find the Gap</h3><p>Compare claimed vs demonstrated<br> skills for your target career.</p><img src="{image_uri('Findthegap.png')}" alt=""></article>
            <article class="feature-card card-three"><span class="feature-index" aria-hidden="true">03</span><h3 class="feature-title">Take Action</h3><p>Get one clear next action and<br> a gap-driven learning roadmap.</p><img src="{image_uri('TakeAction.png')}" alt=""></article>
          </div>
        </section>

        <section id="how" class="how">
          <div class="eyebrow">HOW IT WORKS</div>
          <h2>A simple loop that keeps moving.</h2>
          <div class="steps">
            <details open><summary><b><span class="step-number">01</span>&nbsp; Claim your current skills</b></summary><p>Tell Career Compass what you think you know.</p></details>
            <details><summary><b><span class="step-number">02</span>&nbsp; Assess selected skills</b></summary><p>Complete focused assessments that show what you can demonstrate.</p></details>
            <details><summary><b><span class="step-number">03</span>&nbsp; Find the skill gap</b></summary><p>Compare your claimed readiness with your demonstrated level.</p></details>
            <details><summary><b><span class="step-number">04</span>&nbsp; Improve with a focused roadmap</b></summary><p>Follow clear learning actions tied to your target career.</p></details>
            <details><summary><b><span class="step-number">05</span>&nbsp; Reassess and recompute your next step</b></summary><p>Track progress and get an updated next action.</p></details>
          </div>
        </section>

        <section class="product">
          <div class="eyebrow">SEE THE PRODUCT</div>
          <h2>Your next action, not another dashboard.</h2>
          <p class="product-subtitle">The logged-in experience stays clean and task-focused.</p>
          <div class="dashboard">
            <aside><strong>CAREER<br>COMPASS</strong><span>Dashboard</span><span>My Career</span><span>Roadmap</span><span>Opportunities</span></aside>
            <div class="dashboard-main"><h3>Next Action</h3><div class="action-box"><b>Assess SQL</b><p>Your SQL claim is high but not yet demonstrated.</p></div></div>
            <div class="stats"><div><small>Claimed Readiness</small><b>81%</b><span class="preview-meter claimed" aria-hidden="true"><i></i></span></div><div><small>Demonstrated</small><b class="orange">51%</b><span class="preview-meter demonstrated" aria-hidden="true"><i></i></span></div><div><small>Assessment Coverage</small><b>2 of 6 skills</b></div><span class="product-decor" aria-hidden="true"><img src="{image_uri('navigationelement.png')}" alt=""></span></div>
          </div>
        </section>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.container(key="landing-bottom-cta"):
        cta_copy, cta_link = st.columns([1, .35], vertical_alignment="center")
        with cta_copy:
            st.markdown('<div class="cc-landing"><strong id="start">Turn your skill gap into your next step.</strong></div>', unsafe_allow_html=True)
        with cta_link:
            with st.container(key="landing-bottom-cta-link"):
                st.page_link(
                    "pages/Onboarding.py",
                    label="Get Started",
                    icon=":material/arrow_forward:",
                    width="content",
                )
