
"""
app.py
------
Support PM Pulsator - AI-Powered Review Intelligence Dashboard
Exposes reviews, trends, word cloud analysis, categories, and automated reporting orchestration.
"""

import datetime
import json
import os
import re
import string
import subprocess
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ─── Configuration ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Support PM Pulsator",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# Load Env
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

PROCESSED_DIR = ROOT / "data" / "processed"
OUTPUT_DIR = ROOT / "output"

# ─── Custom Premium Styling (Glassmorphism, Dark Theme) ────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap');
    
    /* Global Styles */
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
        color: #e2e8f0;
    }
    
    .stApp {
        background: radial-gradient(circle at 50% 50%, #0d0f1a 0%, #07080f 100%);
    }
    
    /* Header Area */
    .header-container {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 1.5rem 2rem;
        background: rgba(255, 255, 255, 0.03);
        backdrop-filter: blur(10px);
        border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 16px;
        margin-bottom: 2rem;
    }
    .brand-title {
        font-size: 2.2rem;
        font-weight: 700;
        background: linear-gradient(135deg, #34d399 0%, #6366f1 50%, #a855f7 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0;
    }
    .brand-subtitle {
        font-size: 0.95rem;
        color: #94a3b8;
        margin: 0;
    }
    
    /* Premium Cards */
    .metric-card {
        background: rgba(255, 255, 255, 0.03);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 16px;
        padding: 1.5rem;
        transition: transform 0.2s, border-color 0.2s;
    }
    .metric-card:hover {
        border-color: rgba(52, 211, 153, 0.3);
        transform: translateY(-2px);
    }
    .metric-title {
        color: #94a3b8;
        font-size: 0.9rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.5rem;
    }
    .metric-value {
        font-size: 2.5rem;
        font-weight: 700;
        color: #ffffff;
        line-height: 1.1;
    }
    .metric-delta {
        font-size: 0.85rem;
        margin-top: 0.5rem;
        font-weight: 500;
    }
    .delta-positive { color: #34d399; }
    .delta-negative { color: #f87171; }
    
    /* Section Headers */
    .section-title {
        font-size: 1.4rem;
        font-weight: 600;
        color: #ffffff;
        margin-bottom: 1rem;
        border-left: 4px solid #34d399;
        padding-left: 0.8rem;
    }
    
    /* Word Cloud Badge */
    .word-badge {
        display: inline-block;
        background: rgba(99, 102, 241, 0.08);
        border: 1px solid rgba(99, 102, 241, 0.2);
        color: #a5b4fc;
        padding: 0.4rem 0.8rem;
        border-radius: 20px;
        margin: 0.3rem;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.2s;
    }
    .word-badge:hover {
        background: rgba(99, 102, 241, 0.2);
        border-color: rgba(99, 102, 241, 0.5);
        color: #ffffff;
        transform: scale(1.05);
    }
    .word-badge-active {
        background: rgba(52, 211, 153, 0.15) !important;
        border-color: rgba(52, 211, 153, 0.5) !important;
        color: #34d399 !important;
    }
    
    /* Review Card */
    .review-item {
        background: rgba(255, 255, 255, 0.02);
        border: 1px solid rgba(255, 255, 255, 0.04);
        border-radius: 12px;
        padding: 1.2rem;
        margin-bottom: 0.8rem;
    }
    
    /* Tabs custom styling */
    div[data-testid="stTabs"] button {
        font-size: 1.1rem;
        font-weight: 600;
        color: #94a3b8;
        padding: 0.8rem 1.5rem;
    }
    div[data-testid="stTabs"] button[aria-selected="true"] {
        color: #34d399 !important;
        border-bottom-color: #34d399 !important;
    }
</style>
""", unsafe_allow_html=True)

# ─── Data Loading Helper Functions ─────────────────────────────────────────────
@st.cache_data
def load_reviews():
    path = PROCESSED_DIR / "normalized-reviews.json"
    if not path.exists():
        return pd.DataFrame()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    df = pd.DataFrame(data)
    if not df.empty:
        df['date'] = pd.to_datetime(df['date'])
    return df

@st.cache_data
def load_themes():
    path = PROCESSED_DIR / "themes.json"
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f).get("themes", [])

@st.cache_data
def load_normalization_summary():
    path = PROCESSED_DIR / "normalization-summary.json"
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

# ─── Sidebar Filter & Actions ──────────────────────────────────────────────────
with st.sidebar:
    st.image("https://img.icons8.com/color/96/lightning-bolt.png", width=64)
    st.markdown("### Control Panel")
    
    # Platform Switcher
    platform_filter = st.selectbox(
        "Platform Filter",
        ["All", "Android", "iOS"],
        index=0
    )
    
    # Time window filter
    time_filter = st.selectbox(
        "Time Period",
        ["Last 30 Days", "Last 15 Days", "Last 7 Days", "Yesterday", "Today", "All Time"],
        index=0
    )
    
    st.markdown("---")
    st.markdown("### System Configuration")
    product_name = os.getenv("PRODUCT_NAME", "Spotify")
    st.info(f"Target App: **{product_name}**")
    
    # Sync button action simulation
    if st.button("Sync Data Pipelines", type="primary", use_container_width=True):
        with st.spinner("Syncing App Store & Play Store exports..."):
            try:
                res = subprocess.run(
                    [sys.executable, str(ROOT / "scripts" / "normalize-reviews.py")],
                    capture_output=True, text=True, check=True
                )
                st.success("Pipelines Synced successfully!")
                st.cache_data.clear()
            except Exception as e:
                st.error(f"Sync failed: {e}")

# ─── Load Dataset ──────────────────────────────────────────────────────────────
df = load_reviews()
themes = load_themes()
summary_stats = load_normalization_summary()

# Exit early if data not processed
if df.empty:
    st.warning("⚠️ Normalized reviews data not found. Please sync the data pipelines in the sidebar.")
    st.stop()

# Filter Data according to time and platform
filtered_df = df.copy()

# Apply Platform Filter
if platform_filter == "Android":
    filtered_df = filtered_df[filtered_df['platform'] == 'playstore']
elif platform_filter == "iOS":
    filtered_df = filtered_df[filtered_df['platform'] == 'appstore']

# Apply Time Filter
max_date = filtered_df['date'].max()
if pd.notna(max_date):
    if time_filter == "Today":
        filtered_df = filtered_df[filtered_df['date'].dt.date == max_date.date()]
    elif time_filter == "Yesterday":
        filtered_df = filtered_df[filtered_df['date'].dt.date == (max_date - pd.Timedelta(days=1)).date()]
    elif time_filter == "Last 7 Days":
        filtered_df = filtered_df[filtered_df['date'] >= (max_date - pd.Timedelta(days=7))]
    elif time_filter == "Last 15 Days":
        filtered_df = filtered_df[filtered_df['date'] >= (max_date - pd.Timedelta(days=15))]
    elif time_filter == "Last 30 Days":
        filtered_df = filtered_df[filtered_df['date'] >= (max_date - pd.Timedelta(days=30))]

# Calculate Metrics
total_reviews_count = len(filtered_df)
avg_rating = filtered_df['rating'].mean() if total_reviews_count > 0 else 0.0

# NPS calculation
if total_reviews_count > 0:
    promoters = len(filtered_df[filtered_df['rating'].isin([4, 5])])
    detractors = len(filtered_df[filtered_df['rating'].isin([1, 2])])
    nps = ((promoters - detractors) / total_reviews_count) * 100
else:
    nps = 0.0

# ─── Brand Header ──────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="header-container">
    <div>
        <h1 class="brand-title">Support PM Pulsator</h1>
        <p class="brand-subtitle">AI-Powered Review Intelligence Dashboard for {product_name}</p>
    </div>
    <div style="text-align: right;">
        <span style="background: rgba(52, 211, 153, 0.1); color: #34d399; padding: 0.4rem 1rem; border-radius: 20px; font-weight: 600; border: 1px solid rgba(52, 211, 153, 0.2);">
            Active Filter: {platform_filter} / {time_filter}
        </span>
    </div>
</div>
""", unsafe_allow_html=True)

# ─── Navigation Tabs ───────────────────────────────────────────────────────────
tab_reviews, tab_analytics, tab_categories, tab_wordcloud, tab_ideation, tab_reporting = st.tabs([
    "⭐ Reviews", 
    "📊 Analytics", 
    "📂 Categories", 
    "☁️ Word Cloud", 
    "⚡ Ideation", 
    "📋 Reporting"
])

# TAB 1: Reviews
with tab_reviews:
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.markdown(f"""
        <div class="metric-card">
            <p class="metric-title">NPS Score</p>
            <p class="metric-value">{nps:+.1f}</p>
            <p class="metric-delta delta-positive">📈 Excellent Customer Sentiment</p>
        </div>
        """, unsafe_allow_html=True)
        
    with c2:
        st.markdown(f"""
        <div class="metric-card">
            <p class="metric-title">Total Reviews</p>
            <p class="metric-value">{total_reviews_count:,}</p>
            <p class="metric-delta delta-positive">🔄 Synced and Normalized</p>
        </div>
        """, unsafe_allow_html=True)
        
    with c3:
        st.markdown(f"""
        <div class="metric-card">
            <p class="metric-title">Average Rating</p>
            <p class="metric-value">{avg_rating:.2f} ★</p>
            <p class="metric-delta delta-positive">★ Rating Distribution Stable</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    col_dist, col_table = st.columns([1, 2])
    
    with col_dist:
        st.markdown('<p class="section-title">Rating Distribution</p>', unsafe_allow_html=True)
        if total_reviews_count > 0:
            stars = [5, 4, 3, 2, 1]
            counts = [len(filtered_df[filtered_df['rating'] == s]) for s in stars]
            pcts = [(c / total_reviews_count) * 100 for c in counts]
            
            fig = go.Figure()
            fig.add_trace(go.Bar(
                y=[f"{s} ★" for s in stars],
                x=pcts,
                orientation='h',
                marker=dict(
                    color=['#34d399', '#60a5fa', '#fbbf24', '#fb923c', '#f87171'],
                    line=dict(color='rgba(255,255,255,0.1)', width=1)
                ),
                text=[f"{p:.1f}% ({c})" for p, c in zip(pcts, counts)],
                textposition='auto',
                insidetextfont=dict(color='#ffffff', size=11)
            ))
            fig.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(showgrid=False, showticklabels=False),
                yaxis=dict(autorange="reversed", tickfont=dict(color='#e2e8f0')),
                margin=dict(l=0, r=0, t=10, b=10),
                height=260
            )
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
        else:
            st.write("No reviews match this time window.")
            
    with col_table:
        st.markdown('<p class="section-title">Review Triage Panel</p>', unsafe_allow_html=True)
        search_query = st.text_input("🔍 Search review titles or descriptions...", "")
        
        display_df = filtered_df.copy()
        if search_query:
            display_df = display_df[
                display_df['text'].str.contains(search_query, case=False, na=False) |
                display_df['title'].str.contains(search_query, case=False, na=False)
            ]
            
        page_size = 5
        total_pages = max(1, (len(display_df) + page_size - 1) // page_size)
        page_num = st.number_input("Page", min_value=1, max_value=total_pages, value=1)
        
        start_idx = (page_num - 1) * page_size
        end_idx = start_idx + page_size
        
        for idx, row in display_df.iloc[start_idx:end_idx].iterrows():
            stars_icon = "★" * int(row['rating']) + "☆" * (5 - int(row['rating']))
            badge_color = "#34d399" if row['platform'] == 'playstore' else "#60a5fa"
            badge_text = "Android" if row['platform'] == 'playstore' else "iOS"
            
            st.markdown(f"""
            <div class="review-item">
                <div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem;">
                    <span style="font-weight: 700; color: #ffffff;">{row['title'] if row['title'] else 'No Title'}</span>
                    <span style="color: #fb923c; font-weight: bold;">{stars_icon}</span>
                </div>
                <p style="color: #cbd5e1; font-size: 0.9rem; margin-bottom: 0.8rem;">{row['text']}</p>
                <div style="display: flex; justify-content: space-between; font-size: 0.75rem; color: #94a3b8;">
                    <span>📅 {row['date'].strftime('%Y-%m-%d')}</span>
                    <span style="background: {badge_color}22; color: {badge_color}; padding: 0.1rem 0.5rem; border-radius: 4px; font-weight: 600;">{badge_text}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

# TAB 2: Analytics
with tab_analytics:
    st.markdown('<p class="section-title">Sentiment & volume over time</p>', unsafe_allow_html=True)
    if not filtered_df.empty:
        trend_df = filtered_df.groupby(filtered_df['date'].dt.date).agg(
            Volume=('rating', 'count'),
            AvgRating=('rating', 'mean')
        ).reset_index()
        
        col_chart_vol, col_chart_avg = st.columns(2)
        
        with col_chart_vol:
            fig_vol = px.bar(
                trend_df, x='date', y='Volume',
                title="Review Volume Timeline",
                labels={'date': 'Date', 'Volume': 'Reviews Count'},
                color_discrete_sequence=['#6366f1']
            )
            fig_vol.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#e2e8f0'),
                xaxis=dict(showgrid=False),
                yaxis=dict(gridcolor='rgba(255,255,255,0.05)')
            )
            st.plotly_chart(fig_vol, use_container_width=True)
            
        with col_chart_avg:
            fig_avg = px.line(
                trend_df, x='date', y='AvgRating',
                title="Average Rating Timeline",
                labels={'date': 'Date', 'AvgRating': 'Average Rating (1-5★)'},
                color_discrete_sequence=['#34d399']
            )
            fig_avg.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#e2e8f0'),
                xaxis=dict(showgrid=False),
                yaxis=dict(gridcolor='rgba(255,255,255,0.05)')
            )
            st.plotly_chart(fig_avg, use_container_width=True)
    else:
        st.info("No data available for analytical visualization.")

# TAB 3: Categories
with tab_categories:
    st.markdown('<p class="section-title">AI-Clustered User Themes</p>', unsafe_allow_html=True)
    if themes:
        for theme in themes:
            sentiment_colors = {"positive": "#34d399", "negative": "#f87171", "mixed": "#fbbf24"}
            color = sentiment_colors.get(theme['sentiment'].lower(), "#ffffff")
            
            st.markdown(f"""
            <div style="background: rgba(255, 255, 255, 0.02); border: 1px solid rgba(255,255,255,0.06); border-radius: 16px; padding: 1.5rem; margin-bottom: 1.5rem;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                    <h3 style="margin: 0; font-size: 1.25rem; font-weight: 700; color: #ffffff;">🔥 {theme['theme_name']}</h3>
                    <div>
                        <span style="background: {color}22; color: {color}; font-weight: bold; border-radius: 8px; padding: 0.2rem 0.8rem; font-size: 0.85rem; text-transform: uppercase;">
                            {theme['sentiment']}
                        </span>
                        <span style="background: rgba(255,255,255,0.05); color: #e2e8f0; font-weight: bold; border-radius: 8px; padding: 0.2rem 0.8rem; font-size: 0.85rem; margin-left: 0.5rem;">
                            {theme.get('review_count', 'N/A')} reviews
                        </span>
                    </div>
                </div>
                <p style="color: #cbd5e1; font-size: 0.95rem; line-height: 1.5; margin-bottom: 1rem;">{theme['description']}</p>
                <div style="border-top: 1px solid rgba(255,255,255,0.05); padding-top: 1rem;">
                    <p style="font-size: 0.85rem; font-weight: bold; color: #94a3b8; text-transform: uppercase; margin-bottom: 0.5rem;">Sample Verbatim Feedback:</p>
            """, unsafe_allow_html=True)
            
            for quote in theme.get('sample_quotes', []):
                st.markdown(f"""
                <blockquote style="margin: 0.5rem 0; padding-left: 1rem; border-left: 3px solid #6366f1; color: #a5b4fc; font-style: italic; font-size: 0.9rem;">
                    "{quote}"
                </blockquote>
                """, unsafe_allow_html=True)
                
            st.markdown("</div></div>", unsafe_allow_html=True)
    else:
        st.info("No AI thematic clusters loaded. Run the Weekly Pulse orchestrator in the Reporting tab to generate themes.")

# TAB 4: Word Cloud
with tab_wordcloud:
    st.markdown('<p class="section-title">Interactive Keyword Frequency Cloud</p>', unsafe_allow_html=True)
    STOP_WORDS = {
        "i", "me", "my", "myself", "we", "our", "ours", "ourselves", "you", "your", "yours", 
        "yourself", "yourselves", "he", "him", "his", "himself", "she", "her", "hers", "herself", 
        "it", "its", "itself", "they", "them", "their", "theirs", "themselves", "what", "which", 
        "who", "whom", "this", "that", "these", "those", "am", "is", "are", "was", "were", "be", 
        "been", "being", "have", "has", "had", "having", "do", "does", "did", "doing", "a", "an", 
        "the", "and", "but", "if", "or", "because", "as", "until", "while", "of", "at", "by", "for", 
        "with", "about", "against", "between", "into", "through", "during", "before", "after", 
        "above", "below", "to", "from", "up", "down", "in", "out", "on", "off", "over", "under", 
        "again", "further", "then", "once", "here", "there", "when", "where", "why", "how", "all", 
        "any", "both", "each", "few", "more", "most", "other", "some", "such", "no", "nor", "not", 
        "only", "own", "same", "so", "than", "too", "very", "s", "t", "can", "will", "just", "don", 
        "should", "now", "app", "groww", "spotify"
    }
    
    def get_cloud_words(dataframe, max_words=40):
        counts = {}
        for text in dataframe['text'].dropna():
            cleaned = text.lower().translate(str.maketrans("", "", string.punctuation))
            words = re.findall(r"\w+", cleaned)
            for w in words:
                if w not in STOP_WORDS and len(w) > 2:
                    counts[w] = counts.get(w, 0) + 1
        sorted_c = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        return sorted_c[:max_words]

    word_counts = get_cloud_words(filtered_df)
    
    # Display Stats
    c1, c2, c3 = st.columns(3)
    c1.metric("Unique Keywords Extracted", len(word_counts))
    c2.metric("Total Tokens Processed", len(filtered_df))
    
    st.markdown("<br>", unsafe_allow_html=True)
    if 'selected_word' not in st.session_state:
        st.session_state.selected_word = None
        
    st.markdown("##### Click any keyword to filter the review database:")
    for word, count in word_counts:
        if st.button(f"{word} ({count})", key=f"cloud_{word}", help=f"Filter reviews by '{word}'"):
            st.session_state.selected_word = None if st.session_state.selected_word == word else word
            
    if st.session_state.selected_word:
        st.success(f"Filtering reviews containing keyword: **{st.session_state.selected_word}**")
        keyword_filtered_df = filtered_df[filtered_df['text'].str.contains(st.session_state.selected_word, case=False, na=False)]
        st.dataframe(keyword_filtered_df[['date', 'rating', 'title', 'text']], use_container_width=True)
    else:
        st.info("No active keyword filter. Click any word badge above to drill down.")

# TAB 5: Ideation
with tab_ideation:
    st.markdown('<p class="section-title">Support PM Recommendations</p>', unsafe_allow_html=True)
    st.markdown("""
    Based on the analyzed review cohort, the Support PM Pulsator recommends the following strategic features and corrections:
    
    *   **🎯 Action Item 1: High Brokerage Transparency Widget**
        *   *Context:* Users frequently voice complaints about hidden charges or brokerage.
        *   *Recommendation:* Introduce a real-time brokerage calculator inside the scalper and options placement screens so investors see final numbers upfront.
        
    *   **🎯 Action Item 2: Chart Caching & Speed Optimization**
        *   *Context:* Lag and freezing is a prominent issue causing loss during peak market hours.
        *   *Recommendation:* Re-architect chart streaming to preload and cache historical candles locally, minimizing server roundtrips.
        
    *   **🎯 Action Item 3: Direct Priority Ticket Routing**
        *   *Context:* Complaints of customer support disconnect.
        *   *Recommendation:* Integrate support tickets directly into the portfolio error dialog, routing failed transaction tickets instantly to L2 specialists.
    """)

# TAB 6: Reporting
with tab_reporting:
    st.markdown('<p class="section-title">Pulse Generation & Publishing Orchestrator</p>', unsafe_allow_html=True)
    col_orchestrate, col_preview = st.columns([1, 1])
    
    with col_orchestrate:
        st.markdown("### Generate & Run Report Pipelines")
        st.write("Orchestrate Weekly Review Pulse summaries and publish to Google Docs & Gmail via MCP credentials.")
        
        ref_date = st.date_input("Report Reference Date", datetime.date.today())
        ref_date_str = ref_date.strftime("%Y-%m-%d")
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Step 1: Run generate-pulse.py
        if st.button("🚀 Generate Weekly Pulse (Phase 3)", use_container_width=True):
            with st.spinner("Invoking LLM for theme clustering and report composition..."):
                try:
                    cmd = [sys.executable, str(ROOT / "scripts" / "generate-pulse.py"), "--ref-date", ref_date_str]
                    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
                    st.success("Weekly Pulse generated successfully!")
                    st.code(res.stdout)
                except subprocess.CalledProcessError as err:
                    st.error(f"Generation script failed: {err.stderr}")
                    
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Step 2: Run publish-pulse.py
        if st.button("📬 Publish to Google Docs & Gmail Draft (Phase 6)", use_container_width=True):
            with st.spinner("Authenticating with Google API & Publishing..."):
                try:
                    cmd = [sys.executable, str(ROOT / "scripts" / "publish-pulse.py")]
                    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
                    st.success("Pulse published successfully!")
                    st.code(res.stdout)
                except subprocess.CalledProcessError as err:
                    st.error(f"Publishing script failed: {err.stderr}")
                    
    with col_preview:
        st.markdown("### Latest Pulse Report Preview")
        pulse_files = sorted(OUTPUT_DIR.glob("weekly-pulse-*.md"), reverse=True)
        if pulse_files:
            latest_file = pulse_files[0]
            st.caption(f"Showing file: `{latest_file.name}`")
            with open(latest_file, "r", encoding="utf-8") as f:
                content = f.read()
            st.markdown(content)
        else:
            st.info("No weekly-pulse markdown files found in the output directory. Click the Generate button to produce the first report.")
