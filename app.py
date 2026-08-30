import os
import time
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from config import Config
from modules.monday_client import MondayClient
from modules.data_cleaner import DataCleaner
from modules.bi_engine import BIEngine
from modules.agent import SkylarkBIAgent
from modules.leadership_summary import LeadershipSummaryGenerator

# Page setup
st.set_page_config(
    page_title="Skylark Drones | Executive BI Agent",
    page_icon="🚁",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for Authentic ChatGPT Pure Black & Charcoal Fixed-Bottom Layout
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    /* Base Colors & Fonts */
    html, body, [class*="css"], .stApp {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        background-color: #0B0C0E !important;
        color: #EDEDED !important;
    }
    
    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background-color: #141517 !important;
        border-right: 1px solid #202226 !important;
    }
    
    /* Main Content Container Padding for Fixed Bottom Bar */
    .block-container {
        padding-bottom: 130px !important;
        max-width: 1200px !important;
    }
    
    /* Top Metric Tiles (Matte Charcoal) */
    .metric-card {
        background-color: #17181A;
        border: 1px solid #26282D;
        border-radius: 10px;
        padding: 14px 16px;
        color: #EDEDED;
        transition: border-color 0.2s ease;
    }
    .metric-card:hover {
        border-color: #3F4248;
    }
    .metric-title {
        font-size: 0.75rem;
        color: #8E929B;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .metric-value {
        font-size: 1.55rem;
        font-weight: 700;
        color: #FFFFFF;
        margin-top: 4px;
    }
    .metric-sub {
        font-size: 0.75rem;
        color: #71757E;
        margin-top: 2px;
    }
    
    /* Chat Messages - ChatGPT Minimalist Style */
    div[data-testid="stChatMessage"] {
        background-color: transparent !important;
        border-bottom: 1px solid #1A1B1E;
        padding: 16px 8px !important;
    }
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) {
        background-color: #131416 !important;
        border-radius: 12px;
        margin-bottom: 12px;
        border: 1px solid #212327;
        padding: 14px 18px !important;
    }
    
    /* ChatGPT-style Fixed Bottom Floating Chat Input */
    div[data-testid="stChatInput"] {
        position: fixed !important;
        bottom: 24px !important;
        left: 50% !important;
        transform: translateX(-50%) !important;
        width: min(850px, 85%) !important;
        z-index: 999999 !important;
        background-color: #161719 !important;
        border: 1px solid #303239 !important;
        border-radius: 14px !important;
        box-shadow: 0 8px 30px rgba(0, 0, 0, 0.7) !important;
    }
    div[data-testid="stChatInput"]:focus-within {
        border-color: #555863 !important;
    }
    div[data-testid="stChatInput"] textarea {
        background-color: transparent !important;
        color: #FFFFFF !important;
    }
    
    /* Buttons in Sidebar */
    .stButton>button {
        background-color: #1C1E22 !important;
        color: #D1D5DB !important;
        border: 1px solid #282A30 !important;
        border-radius: 8px !important;
        font-weight: 500 !important;
        transition: all 0.2s ease !important;
    }
    .stButton>button:hover {
        background-color: #26282E !important;
        color: #FFFFFF !important;
        border-color: #3F434C !important;
    }
    
    /* Badges */
    .badge-online {
        display: inline-block;
        padding: 3px 8px;
        background-color: #10241A;
        color: #4ADE80;
        border: 1px solid #183C2A;
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .badge-board {
        display: inline-block;
        padding: 2px 7px;
        background-color: #1E2024;
        color: #D1D5DB;
        border-radius: 4px;
        font-size: 0.72rem;
        margin-right: 4px;
        border: 1px solid #2A2C32;
    }
    .caveat-box {
        background-color: #171510;
        border-left: 3px solid #D97706;
        padding: 10px 14px;
        border-radius: 6px;
        color: #FDE68A;
        margin: 8px 0;
        font-size: 0.88rem;
    }
    
    /* Tabs Styling */
    .stTabs [data-baseweb="tab-list"] {
        background-color: #0B0C0E;
        border-bottom: 1px solid #1E2024;
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        color: #8E929B !important;
        padding: 8px 16px;
        border-radius: 6px;
    }
    .stTabs [aria-selected="true"] {
        color: #FFFFFF !important;
        background-color: #161719 !important;
        border-bottom: 2px solid #EDEDED !important;
    }
</style>
""", unsafe_allow_html=True)

# Session state initialization
if "messages" not in st.session_state:
    st.session_state.messages = []
if "deals_df" not in st.session_state:
    st.session_state.deals_df = pd.DataFrame()
if "wo_df" not in st.session_state:
    st.session_state.wo_df = pd.DataFrame()
if "deals_quality" not in st.session_state:
    st.session_state.deals_quality = {}
if "wo_quality" not in st.session_state:
    st.session_state.wo_quality = {}
if "last_sync" not in st.session_state:
    st.session_state.last_sync = None
if "deals_board_id" not in st.session_state:
    st.session_state.deals_board_id = None
if "wo_board_id" not in st.session_state:
    st.session_state.wo_board_id = None

monday_client = MondayClient()
bi_agent = SkylarkBIAgent()

def sync_data(force_refresh=False):
    with st.spinner("Syncing live board data from monday.com..."):
        try:
            board_ids = monday_client.discover_board_ids()
            deals_id = board_ids["deals_board_id"]
            wo_id = board_ids["work_orders_board_id"]

            st.session_state.deals_board_id = deals_id
            st.session_state.wo_board_id = wo_id

            if not deals_id or not wo_id:
                if os.path.exists("Deal funnel Data.xlsx") and os.path.exists("Work_Order_Tracker Data.xlsx"):
                    df_d_raw = pd.read_excel("Deal funnel Data.xlsx").to_dict(orient="records")
                    df_wo_raw_f = pd.read_excel("Work_Order_Tracker Data.xlsx", header=0)
                    df_wo_headers = list(df_wo_raw_f.iloc[0].values)
                    df_wo_sub = df_wo_raw_f.iloc[1:].copy()
                    df_wo_sub.columns = df_wo_headers
                    df_wo_raw = df_wo_sub.to_dict(orient="records")
                    
                    cleaned_deals, dq_deals = DataCleaner.clean_deals(df_d_raw)
                    cleaned_wo, dq_wo = DataCleaner.clean_work_orders(df_wo_raw)
                    st.session_state.deals_df = cleaned_deals
                    st.session_state.wo_df = cleaned_wo
                    st.session_state.deals_quality = dq_deals
                    st.session_state.wo_quality = dq_wo
                    st.session_state.last_sync = time.strftime("%H:%M:%S") + " (Local Fallback)"
                    return True

            deals_data = monday_client.fetch_board_items(deals_id, force_refresh=force_refresh)
            wo_data = monday_client.fetch_board_items(wo_id, force_refresh=force_refresh)

            cleaned_deals, dq_deals = DataCleaner.clean_deals(deals_data.get("records", []))
            cleaned_wo, dq_wo = DataCleaner.clean_work_orders(wo_data.get("records", []))

            st.session_state.deals_df = cleaned_deals
            st.session_state.wo_df = cleaned_wo
            st.session_state.deals_quality = dq_deals
            st.session_state.wo_quality = dq_wo
            st.session_state.last_sync = time.strftime("%H:%M:%S")
            return True
        except Exception as e:
            st.error(f"Error syncing with Monday.com: {e}")
            return False

# Initial sync
if st.session_state.deals_df.empty:
    sync_data(force_refresh=False)

# Sidebar (Charcoal Grey)
with st.sidebar:
    st.image("https://images.unsplash.com/photo-1508614589041-895b88991e3e?w=800&auto=format&fit=crop&q=80", use_container_width=True)
    st.markdown("### 🚁 Skylark Drones BI")
    st.markdown("<span class='badge-online'>● Monday.com Live API Connected</span>", unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("#### 📋 Board Connections")
    if st.session_state.deals_board_id:
        st.markdown(f"<span class='badge-board'>Deals</span> `{st.session_state.deals_board_id}`", unsafe_allow_html=True)
    if st.session_state.wo_board_id:
        st.markdown(f"<span class='badge-board'>Work Orders</span> `{st.session_state.wo_board_id}`", unsafe_allow_html=True)
    
    st.caption(f"Last Synced: {st.session_state.last_sync or 'Never'}")
    if st.button("🔄 Refresh Monday Data", use_container_width=True):
        sync_data(force_refresh=True)
        st.success("Board telemetry refreshed!")
        st.rerun()

    st.markdown("---")
    st.markdown("#### ⚡ Quick Prompts")
    if st.button("📊 Leadership Update", use_container_width=True):
        st.session_state.user_prompt_inject = "Prepare an executive leadership update for this quarter."
    if st.button("⛏️ Mining Sector Analysis", use_container_width=True):
        st.session_state.user_prompt_inject = "How is the Mining sector performing in terms of open pipeline and billed revenue?"
    if st.button("⚡ Powerline vs Mining", use_container_width=True):
        st.session_state.user_prompt_inject = "Compare the Powerline and Mining sectors. Which one has more deals and which has higher receivables?"
    if st.button("💰 Receivables Risk", use_container_width=True):
        st.session_state.user_prompt_inject = "Which specific work orders and clients represent our biggest receivables risk?"
    if st.button("🧹 Data Quality Audit", use_container_width=True):
        st.session_state.user_prompt_inject = "Explain why our weighted pipeline is different from our total pipeline, and what data gaps exist."

# Top KPI Tiles
deals_df = st.session_state.deals_df
wo_df = st.session_state.wo_df

if not deals_df.empty and not wo_df.empty:
    pipe_summary = BIEngine.analyze_pipeline(deals_df)
    ops_summary = BIEngine.analyze_operations(wo_df)

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.markdown(f"""
        <div class='metric-card'>
            <div class='metric-title'>Total Pipeline</div>
            <div class='metric-value'>{pipe_summary.get('total_pipeline_formatted')}</div>
            <div class='metric-sub'>{pipe_summary.get('open_deals_count')} active deals</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class='metric-card'>
            <div class='metric-title'>Weighted Pipeline</div>
            <div class='metric-value'>{pipe_summary.get('weighted_pipeline_formatted')}</div>
            <div class='metric-sub'>Risk-adjusted forecast</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div class='metric-card'>
            <div class='metric-title'>Billed Revenue</div>
            <div class='metric-value'>{ops_summary.get('total_billed_formatted')}</div>
            <div class='metric-sub'>Billing Eff: {ops_summary.get('billing_efficiency_pct')}%</div>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        st.markdown(f"""
        <div class='metric-card'>
            <div class='metric-title'>Collected Cash</div>
            <div class='metric-value'>{ops_summary.get('total_collected_formatted')}</div>
            <div class='metric-sub'>Collection Eff: {ops_summary.get('collection_efficiency_pct')}%</div>
        </div>
        """, unsafe_allow_html=True)
    with col5:
        st.markdown(f"""
        <div class='metric-card'>
            <div class='metric-title'>Outstanding AR</div>
            <div class='metric-value'>{ops_summary.get('total_receivables_formatted')}</div>
            <div class='metric-sub'>Unpaid receivables</div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

# Main Navigation Tabs
tab_chat, tab_visuals, tab_brief, tab_quality, tab_boards = st.tabs([
    "💬 Conversational BI Assistant",
    "📈 Performance Visuals",
    "📋 Leadership Hub",
    "⚠️ Data Governance & Caveats",
    "🗂️ Live Board Explorer"
])

# TAB 1: Conversational Chat (ChatGPT Style)
with tab_chat:
    # Render all chat messages sequentially
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"], avatar="👤" if msg["role"] == "user" else "🚁"):
            st.markdown(msg["content"])

# Bottom pinned chat input (ChatGPT style fixed input)
user_input = st.chat_input("Ask a business question (e.g. pipeline health, receivables, sector comparison)...")

# Handle quick prompt injection from sidebar
if "user_prompt_inject" in st.session_state and st.session_state.user_prompt_inject:
    user_input = st.session_state.user_prompt_inject
    st.session_state.user_prompt_inject = None

if user_input:
    # 1. Instantly display user message
    st.session_state.messages.append({"role": "user", "content": user_input})
    with tab_chat:
        with st.chat_message("user", avatar="👤"):
            st.markdown(user_input)

        # 2. Generate and display assistant response directly below
        with st.chat_message("assistant", avatar="🚁"):
            with st.spinner("Analyzing Monday.com telemetry & synthesizing intelligence..."):
                response_obj = bi_agent.answer_query(
                    user_input,
                    st.session_state.deals_df,
                    st.session_state.wo_df,
                    st.session_state.deals_quality,
                    st.session_state.wo_quality
                )
                answer_text = response_obj["answer"]
                st.markdown(answer_text)
                st.session_state.messages.append({"role": "assistant", "content": answer_text})
    st.rerun()

# TAB 2: Interactive Analytics (Monochrome Theme)
with tab_visuals:
    st.markdown("### 📊 Cross-Board Performance Telemetry")
    if not deals_df.empty and not wo_df.empty:
        c1, c2 = st.columns(2)
        
        with c1:
            st.markdown("##### 💼 Open Sales Pipeline by Sector")
            pipe_data = BIEngine.analyze_pipeline(deals_df)
            sec_df = pd.DataFrame(pipe_data.get("sector_breakdown", []))
            if not sec_df.empty:
                fig_pipe = go.Figure()
                fig_pipe.add_trace(go.Bar(
                    x=sec_df["sector"], y=sec_df["total_value"],
                    name="Total Pipeline", marker_color="#E5E7EB"
                ))
                fig_pipe.add_trace(go.Bar(
                    x=sec_df["sector"], y=sec_df["weighted_value"],
                    name="Weighted Pipeline", marker_color="#6B7280"
                ))
                fig_pipe.update_layout(
                    barmode="group",
                    paper_bgcolor="#0B0C0E",
                    plot_bgcolor="#141517",
                    font=dict(color="#D1D5DB"),
                    margin=dict(l=20, r=20, t=30, b=20),
                    height=350
                )
                st.plotly_chart(fig_pipe, use_container_width=True)

        with c2:
            st.markdown("##### ⚙️ Work Order Fulfillment Distribution")
            status_counts = wo_df["execution_status"].value_counts().reset_index()
            status_counts.columns = ["Status", "Count"]
            fig_ops = px.pie(
                status_counts, values="Count", names="Status",
                color_discrete_sequence=["#F3F4F6", "#9CA3AF", "#4B5563", "#374151"],
                hole=0.45
            )
            fig_ops.update_layout(
                paper_bgcolor="#0B0C0E",
                font=dict(color="#D1D5DB"),
                margin=dict(l=20, r=20, t=30, b=20),
                height=350
            )
            st.plotly_chart(fig_ops, use_container_width=True)

        st.markdown("##### 🔍 Cross-Board Sector Telemetry Matrix")
        cross_res = BIEngine.cross_board_analysis(deals_df, wo_df)
        cross_matrix_df = pd.DataFrame(cross_res.get("cross_board_matrix", []))
        st.dataframe(cross_matrix_df, use_container_width=True, hide_index=True)

# TAB 3: Leadership Update Hub
with tab_brief:
    st.markdown("### 📋 Executive Leadership Update Hub")
    st.caption("Synthesizes multi-board sales, operations, receivables, and data caveat disclosures into an executive-ready brief.")
    
    if st.button("⚡ Refresh Leadership Brief", type="primary"):
        brief_data = LeadershipSummaryGenerator.generate_brief(
            st.session_state.deals_df,
            st.session_state.wo_df,
            st.session_state.deals_quality,
            st.session_state.wo_quality
        )
        st.markdown(brief_data["markdown_report"])
        st.download_button(
            "📥 Download Brief as Markdown",
            data=brief_data["markdown_report"],
            file_name="skylark_executive_leadership_update.md",
            mime="text/markdown"
        )
    else:
        brief_data = LeadershipSummaryGenerator.generate_brief(
            st.session_state.deals_df,
            st.session_state.wo_df,
            st.session_state.deals_quality,
            st.session_state.wo_quality
        )
        st.markdown(brief_data["markdown_report"])

# TAB 4: Data Quality & Caveats
with tab_quality:
    st.markdown("### ⚠️ Data Resilience & Quality Audit")
    st.markdown("Real-world business data contains noise, missing probabilities, and unbilled work orders. The agent explicitly tracks and communicates these caveats:")

    col_q1, col_q2 = st.columns(2)
    with col_q1:
        st.markdown("#### 💼 Deals Board Data Health")
        dq_d = st.session_state.deals_quality
        st.write(f"- **Total Records:** {dq_d.get('total_records', 0)}")
        st.write(f"- **Missing Deal Values:** {dq_d.get('missing_value_count', 0)} ({dq_d.get('missing_value_pct', 0)}%)")
        st.write(f"- **Missing Closure Probabilities:** {dq_d.get('missing_probability_count', 0)} ({dq_d.get('missing_probability_pct', 0)}%)")
        st.write(f"- **Missing Tentative Close Dates:** {dq_d.get('missing_tentative_close_count', 0)}")
        
        st.markdown("##### 🚨 Active Pipeline Caveats:")
        for c in dq_d.get("caveats", []):
            st.markdown(f"<div class='caveat-box'>⚠️ {c}</div>", unsafe_allow_html=True)

    with col_q2:
        st.markdown("#### ⚙️ Work Orders Data Health")
        dq_w = st.session_state.wo_quality
        st.write(f"- **Total Work Orders:** {dq_w.get('total_records', 0)}")
        st.write(f"- **Completed but Unbilled Orders:** {dq_w.get('completed_unbilled_count', 0)}")
        st.write(f"- **Missing Invoice Dates:** {dq_w.get('missing_invoice_date_count', 0)}")
        st.write(f"- **Total Receivables Tracked:** {BIEngine.format_currency_inr(dq_w.get('total_receivables', 0))}")
        
        st.markdown("##### 🚨 Active Operations Caveats:")
        for c in dq_w.get("caveats", []):
            st.markdown(f"<div class='caveat-box'>⚠️ {c}</div>", unsafe_allow_html=True)

# TAB 5: Live Monday Boards Explorer
with tab_boards:
    st.markdown("### 🗂️ Live Monday.com Board Data Explorer")
    board_choice = st.radio("Select Board to Inspect:", ["Deals Pipeline", "Work Order Tracker"], horizontal=True)
    
    if board_choice == "Deals Pipeline":
        st.dataframe(deals_df, use_container_width=True)
    else:
        st.dataframe(wo_df, use_container_width=True)
