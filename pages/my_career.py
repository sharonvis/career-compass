import streamlit as st

# 1. Page Configuration & Layout
st.set_page_config(
    page_title="Career Compass",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Inject CSS Theme & UI Component Overrides
st.markdown("""
    <style>
    /* Main container background & overall app font styling */
    .stApp {
        background-color: #FDF7F2;
        font-family: 'Inter', -apple-system, sans-serif;
    }
    
    /* Dark Theme Left Sidebar Overrides */
    [data-testid="stSidebar"] {
        background-color: #121113;
    }
    [data-testid="stSidebar"] * {
        color: #FFFFFF !important;
    }
    
    /* Active sidebar item simulation styling */
    .active-nav {
        background-color: #E0533C !important;
        color: white !important;
        border-radius: 8px;
        padding: 8px 12px;
        font-weight: bold;
    }
    
    /* Custom Headers matching the serif aesthetic */
    .main-title {
        font-family: 'Playfair Display', 'Georgia', serif;
        font-size: 42px;
        font-weight: 700;
        color: #121113;
        margin-top: -10px;
        margin-bottom: 5px;
    }
    .section-title {
        font-family: 'Playfair Display', 'Georgia', serif;
        font-size: 28px;
        font-weight: 700;
        color: #121113;
    }
    
    /* Custom Brutalist Border Blocks (The Card Styling) */
    .brutal-card {
        background-color: #FFFFFF;
        border: 2px solid #121113;
        border-radius: 20px;
        padding: 24px;
        box-shadow: 0px 4px 0px #121113;
        margin-bottom: 20px;
    }
    
    /* Custom Inline Components */
    .circle-index {
        background-color: #FDF7F2;
        border-radius: 50%;
        width: 32px;
        height: 32px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-weight: bold;
        color: #767473;
        margin-right: 12px;
    }
    
    /* Status Badge styling */
    .badge-gap {
        background-color: #FFEBE7;
        color: #E0533C;
        border-radius: 6px;
        padding: 4px 12px;
        font-size: 13px;
        font-weight: bold;
        display: inline-block;
    }
    .badge-na {
        background-color: #FBEFE6;
        color: #E0533C;
        opacity: 0.6;
        border-radius: 6px;
        padding: 4px 12px;
        font-size: 13px;
        font-weight: bold;
        display: inline-block;
    }
    
    /* Custom Progress Bar container */
    .custom-progress {
        background-color: #EAE5E0;
        border-radius: 10px;
        height: 8px;
        width: 100%;
        margin-top: 10px;
    }
    .custom-progress-fill {
        background-color: #E0533C;
        border-radius: 10px;
        height: 100%;
        width: 33.3%; /* 2 out of 6 */
    }
    </style>
""", unsafe_allow_html=True)


# ==========================================
# 3. SIDEBAR NAVIGATION
# ==========================================
with st.sidebar:
    st.markdown("### 🧭 CAREER COMPASS")
    st.markdown("<br>", unsafe_allow_html=True)
    
    # These destinations are placeholders until their Streamlit pages exist.
    st.markdown('<div style="padding: 8px 12px;">⬜ &nbsp; Dashboard</div>', unsafe_allow_html=True)
    st.markdown('<div class="active-nav">🔥 My Career</div>', unsafe_allow_html=True)
    st.markdown('<div style="padding: 8px 12px;">🛣️ &nbsp; Roadmap</div>', unsafe_allow_html=True)
    st.markdown('<div style="padding: 8px 12px;">💎 &nbsp; Opportunities</div>', unsafe_allow_html=True)
    st.markdown('<div style="padding: 8px 12px;">📂 &nbsp; Applications</div>', unsafe_allow_html=True)
    st.markdown('<div style="padding: 8px 12px;">⚙️ &nbsp; Settings</div>', unsafe_allow_html=True)


# ==========================================
# 4. APP MAIN HEADER BLOCK
# ==========================================
# Split title and change career button into columns
title_col, action_col = st.columns([4, 1], vertical_alignment="bottom")

with title_col:
    st.markdown('<p style="color: #E0533C; font-weight: bold; font-size: 12px; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 0;">My Career</p>', unsafe_allow_html=True)
    st.markdown('<h1 class="main-title">Data Analyst</h1>', unsafe_allow_html=True)
    st.markdown('<p style="color: #767473; margin-top: 0;">Explore the key skills for this career and track your progress.</p>', unsafe_allow_html=True)

with action_col:
    st.button("🔄 Change Career", use_container_width=True)

st.markdown("<br>", unsafe_allow_html=True)


# ==========================================
# 5. TOP METRIC / OVERVIEW GRID CARD
# ==========================================
st.markdown('<div class="brutal-card">', unsafe_allow_html=True)
metric_col1, metric_col2, metric_col3 = st.columns([1.5, 1, 1.5])

with metric_col1:
    st.markdown('<p style="color: #767473; text-transform: uppercase; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;">Career Overview</p>', unsafe_allow_html=True)
    st.markdown('<p style="color: #121113; font-size: 15px; line-height: 1.4;">Data analysts turn data into useful insights to help solve real-world problems.</p>', unsafe_allow_html=True)

with metric_col2:
    st.markdown('<div style="border-left: 1px solid #EAE5E0; padding-left: 24px;">', unsafe_allow_html=True)
    st.markdown('<p style="color: #767473; text-transform: uppercase; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;">Key Skills</p>', unsafe_allow_html=True)
    st.markdown('<h2 style="margin: 0; color: #121113; font-size: 28px; font-weight: bold;">6 skills</h2>', unsafe_allow_html=True)
    st.markdown('<p style="color: #767473; font-size: 13px; margin: 0;">to focus on</p>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

with metric_col3:
    st.markdown('<div style="border-left: 1px solid #EAE5E0; padding-left: 24px;">', unsafe_allow_html=True)
    st.markdown('<p style="color: #767473; text-transform: uppercase; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;">Your Progress</p>', unsafe_allow_html=True)
    st.markdown('<p style="margin: 0; font-size: 14px; font-weight: bold; color: #121113;">2 of 6 skills assessed</p>', unsafe_allow_html=True)
    st.markdown('<div class="custom-progress"><div class="custom-progress-fill"></div></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)


# ==========================================
# 6. CORE SKILLS TABLE LAYOUT
# ==========================================
section_header_col, section_info_col = st.columns([3, 2], vertical_alignment="bottom")
with section_header_col:
    st.markdown('<h2 class="section-title">Core Skills</h2>', unsafe_allow_html=True)
with section_info_col:
    st.markdown('<p style="color: #767473; text-align: right; margin-bottom: 10px; font-size: 14px;">The most important skills for a Data Analyst.</p>', unsafe_allow_html=True)

# Main container wrapping the skill rows
st.markdown('<div class="brutal-card" style="padding: 10px 24px;">', unsafe_allow_html=True)

# Data structure mapping out rows to streamline row processing cleanly
skills_data = [
    {"id": "1", "name": "SQL", "req": "Intermediate", "level": "Beginner", "status": "Gap", "action": "Reassess"},
    {"id": "2", "name": "Python", "req": "Intermediate", "level": "Not Assessed", "status": "Not Assessed", "action": "Assess"},
    {"id": "3", "name": "Statistics", "req": "Intermediate", "level": "Not Assessed", "status": "Not Assessed", "action": "Assess"},
    {"id": "4", "name": "Data Visualisation", "req": "Intermediate", "level": "Not Assessed", "status": "Not Assessed", "action": "Assess"}
]

for idx, skill in enumerate(skills_data):
    # Establish layout column widths matching grid rows
    r_col1, r_col2, r_col3, r_col4, r_col5 = st.columns([2.5, 1.5, 2, 1.5, 1.5], vertical_alignment="center")
    
    with r_col1:
        st.markdown(f'<p style="margin:0; font-size: 16px; font-weight: bold; color:#121113;"><span class="circle-index">{skill["id"]}</span> {skill["name"]}</p>', unsafe_allow_html=True)
        
    with r_col2:
        st.markdown(f'<p style="margin:0; font-size: 12px; color: #767473; line-height: 1.3;">Required<br><b style="color: #121113;">{skill["req"]}</b></p>', unsafe_allow_html=True)
        
    with r_col3:
        # Mock structural layout bars representing current skill levels
        filled_bar = '<div style="background-color: #E0533C; width: 16px; height: 6px; border-radius:2px; display:inline-block; margin-right:3px;"></div>' if skill["level"] == "Beginner" else '<div style="background-color: #EAE5E0; width: 16px; height: 6px; border-radius:2px; display:inline-block; margin-right:3px;"></div>'
        empty_bars = ''.join(['<div style="background-color: #EAE5E0; width: 16px; height: 6px; border-radius:2px; display:inline-block; margin-right:3px;"></div>' for _ in range(2)])
        st.markdown(f'<div style="margin-bottom: 2px;">{filled_bar}{empty_bars}</div><span style="font-size: 12px; color: #767473;">{skill["level"]}</span>', unsafe_allow_html=True)
        
    with r_col4:
        badge_style = "badge-gap" if skill["status"] == "Gap" else "badge-na"
        st.markdown(f'<div class="{badge_style}">{skill["status"]}</div>', unsafe_allow_html=True)
        
    with r_col5:
        # Toggle primary bright orange focus button vs neutral cream buttons
        btn_type = "primary" if skill["action"] == "Reassess" else "secondary"
        st.button(skill["action"], key=f"action_{skill['id']}", type=btn_type, use_container_width=True)
        
    # Render line break divider between rows, omitting trailing divider on final element
    if idx < len(skills_data) - 1:
        st.markdown('<hr style="margin: 12px 0; border: 0; border-top: 1px solid #EAE5E0;">', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)
