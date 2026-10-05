import streamlit as st
from pathlib import Path
import base64

st.set_page_config(page_title="Career Compass", page_icon="🧭", layout="wide", initial_sidebar_state="collapsed")

ROOT = Path(__file__).parent
ASSET = ROOT / "assets" / "images"

def image_uri(name):
    path = ASSET / name
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")

logo = image_uri("CareerCompassLogo.png")
hero = image_uri("Peopleoncompass.png")
navigation = image_uri("navigationelement.png")

with open(ROOT / "assets" / "styles.css", encoding="utf-8") as f:
    css = f.read()

st.markdown("<style>" + css + "</style>", unsafe_allow_html=True)

st.markdown(f"""
<header class="topbar">
  <a class="brand" href="#top"><img src="{logo}" alt=""><span>CAREER COMPASS</span></a>
  <nav><a href="#how">How It Works</a><a href="#about">About</a><a class="signin" href="#start">Sign In</a></nav>
</header>
<main id="top">
<section class="hero">
  <div class="hero-copy">
    <div class="eyebrow">CLAIM &middot; ASSESS &middot; IMPROVE</div>
    <h1>Know what you know.<br><em>Know what to do next.</em></h1>
    <p>Career Compass compares the skills you claim with what you can<br class="desktop"> actually demonstrate, then turns that gap into your next best action.</p>
    <a class="button dark" href="#start">Get Started <span>&rarr;</span></a>
  </div>
  <div class="hero-art"><img src="{hero}" alt="People following a compass toward their career goals"></div>
</section>

<section id="about" class="features">
  <div class="eyebrow">WHAT CAREER COMPASS DOES</div>
  <div class="feature-grid">
    <article class="feature-card card-one"><h3>Assess Your Skills</h3><p>Take focused assessments and<br> see your demonstrated level.</p><img src="{image_uri("Assessyouskills.png")}" alt=""></article>
    <article class="feature-card card-two"><h3>Find the Gap</h3><p>Compare claimed vs demonstrated<br> skills for your target career.</p><img src="{image_uri("Findthegap.png")}" alt=""></article>
    <article class="feature-card card-three"><h3>Take Action</h3><p>Get one clear next action and<br> a gap-driven learning roadmap.</p><img src="{image_uri("TakeAction.png")}" alt=""></article>
  </div>
</section>

<section id="how" class="how">
  <div class="eyebrow">HOW IT WORKS</div>
  <h2>A simple loop that keeps moving.</h2>
  <div class="steps">
    <details open><summary><b>01&nbsp; Claim your current skills</b></summary><p>Tell Career Compass what you think you know.</p></details>
    <details><summary><b>02&nbsp; Assess selected skills</b></summary><p>Complete focused assessments that show what you can demonstrate.</p></details>
    <details><summary><b>03&nbsp; Find the skill gap</b></summary><p>Compare your claimed readiness with your demonstrated level.</p></details>
    <details><summary><b>04&nbsp; Improve with a focused roadmap</b></summary><p>Follow clear learning actions tied to your target career.</p></details>
    <details><summary><b>05&nbsp; Reassess and recompute your next step</b></summary><p>Track progress and get an updated next action.</p></details>
  </div>
</section>

<section class="product">
  <div class="eyebrow">SEE THE PRODUCT</div>
  <h2>Your next action, not another dashboard.</h2>
  <p class="product-subtitle">The logged-in experience stays clean and task-focused.</p>
  <img class="product-decor" src="{navigation}" alt="">
  <div class="dashboard">
    <aside><strong>CAREER<br>COMPASS</strong><span>Dashboard</span><span>My Career</span><span>Roadmap</span><span>Opportunities</span></aside>
    <div class="dashboard-main"><h3>Next Action</h3><div class="action-box"><b>Assess SQL</b><p>Your SQL claim is high but not yet demonstrated.</p></div></div>
    <div class="stats"><div><small>Claimed Readiness</small><b>81%</b></div><div><small>Demonstrated</small><b class="orange">51%</b></div><div><small>Assessment Coverage</small><b>2 of 6 skills</b></div></div>
  </div>
  <div id="start" class="bottom-cta"><strong>Turn your skill gap into your next step.</strong><a class="button orange-button" href="#top">Get Started <span>&rarr;</span></a></div>
</section>
</main>
""", unsafe_allow_html=True)


