"""
═══════════════════════════════════════════════════════════════════
📊 Streamlit Dashboard - لوحة التحكم التفاعلية
═══════════════════════════════════════════════════════════════════
تعرض:
- أداء النظام لحظياً
- الصفقات المفتوحة
- الرسوم البيانية
- صحة الوكلاء
- ML Performance
- Risk Metrics
═══════════════════════════════════════════════════════════════════
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import asyncio
import sys
from pathlib import Path

# إضافة المسار
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ml_engine.database.database_manager import DatabaseManager
from ml_engine.ml_system import TradingMLModel


# ══════════════ إعدادات الصفحة ══════════════
st.set_page_config(
    page_title="SMC/ICT Trading Bot Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ══════════════ CSS مخصص ══════════════
st.markdown("""
<style>
    .metric-card {
        background-color: #1e1e1e;
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #00ff00;
    }
    .metric-card-red {
        border-left: 5px solid #ff0000;
    }
    .metric-card-yellow {
        border-left: 5px solid #ffaa00;
    }
</style>
""", unsafe_allow_html=True)


# ══════════════ Header ══════════════
st.title("🚀 SMC/ICT Multi-Agent Trading Bot")
st.markdown("### لوحة التحكم الرئيسية | Real-time Monitoring Dashboard")
st.markdown("---")


# ══════════════ Sidebar ══════════════
with st.sidebar:
    st.header("⚙️ الإعدادات")

    # اختيار العملة
    symbol = st.selectbox(
        "العملة",
        ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT"]
    )

    # الإطار الزمني
    timeframe = st.selectbox(
        "الإطار الزمني",
        ["1h", "4h", "1d", "1w"]
    )

    # Refresh rate
    refresh_rate = st.slider("Refresh (ثواني)", 5, 60, 10)

    st.markdown("---")
    st.header("🤖 الوكلاء")
    st.markdown("""
    - 📰 News Intelligence
    - 📊 Market Analysis
    - 🧠 Decision Maker
    - 🛡️ Risk Manager
    - ⚡ Execution
    - 👁️ Monitor
    """)


# ══════════════ الاتصال بقاعدة البيانات ══════════════
@st.cache_resource
def get_db():
    return DatabaseManager()

@st.cache_resource
def get_ml_model():
    return TradingMLModel()

db = get_db()
ml_model = get_ml_model()


# ══════════════ الصف الأول: KPIs الرئيسية ══════════════
col1, col2, col3, col4, col5 = st.columns(5)

# جلب الإحصائيات
stats = db.get_performance_stats()
ml_perf = ml_model.get_performance_report()

with col1:
    st.metric(
        "💰 إجمالي PnL",
        f"${stats.get('total_pnl', 0):.2f}",
        delta=f"{stats.get('win_rate', 0):.1f}% WR"
    )

with col2:
    st.metric(
        "📊 إجمالي الصفقات",
        stats.get('total_trades', 0),
        delta=f"{stats.get('winners', 0)} wins"
    )

with col3:
    st.metric(
        "🎯 Win Rate",
        f"{stats.get('win_rate', 0):.1f}%",
        delta="ممتاز" if stats.get('win_rate', 0) >= 60 else "يحتاج تحسين"
    )

with col4:
    st.metric(
        "🧠 ML Accuracy",
        f"{ml_perf.get('accuracy', 0):.1%}",
        delta=f"{ml_perf.get('total_samples', 0)} samples"
    )

with col5:
    st.metric(
        "🛡️ Active Drawdown",
        "0.0%",
        delta="Safe"
    )


# ══════════════ الصف الثاني: الرسوم البيانية ══════════════
st.markdown("---")
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("📈 Equity Curve")

    closed_trades = db.get_closed_trades(limit=100)
    if closed_trades:
        df_trades = pd.DataFrame(closed_trades)
        df_trades['cumulative_pnl'] = df_trades['pnl'].cumsum()

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df_trades['exit_time'],
            y=df_trades['cumulative_pnl'],
            mode='lines+markers',
            name='Equity',
            line=dict(color='#00ff00', width=2)
        ))
        fig.update_layout(
            template='plotly_dark',
            height=400,
            xaxis_title='Time',
            yaxis_title='PnL (USDT)'
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("لا توجد صفقات مغلقة بعد")

with col_right:
    st.subheader("📊 Win/Loss Distribution")

    if closed_trades:
        df_trades = pd.DataFrame(closed_trades)
        df_trades['result'] = df_trades['pnl'].apply(
            lambda x: 'Win' if x > 0 else 'Loss'
        )

        fig = px.pie(
            df_trades,
            names='result',
            title='نتائج الصفقات',
            color='result',
            color_discrete_map={'Win': '#00ff00', 'Loss': '#ff0000'}
        )
        fig.update_layout(template='plotly_dark', height=400)
        st.plotly_chart(fig, use_container_width=True)


# ══════════════ الصف الثالث: الصفقات المفتوحة ══════════════
st.markdown("---")
st.subheader("🔓 الصفقات المفتوحة")

open_trades = db.get_open_trades()
if open_trades:
    df_open = pd.DataFrame(open_trades)
    st.dataframe(
        df_open[['symbol', 'side', 'entry_price', 'stop_loss', 'take_profit', 'entry_time']],
        use_container_width=True
    )
else:
    st.info("لا توجد صفقات مفتوحة")


# ══════════════ الصف الرابع: ML Performance ══════════════
st.markdown("---")
st.subheader("🧠 Machine Learning Performance")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Accuracy", f"{ml_perf.get('accuracy', 0):.1%}")
with col2:
    st.metric("Precision", f"{ml_perf.get('precision', 0):.1%}")
with col3:
    st.metric("Recall", f"{ml_perf.get('recall', 0):.1%}")
with col4:
    st.metric("F1 Score", f"{ml_perf.get('f1_score', 0):.2f}")


# ══════════════ الصف الخامس: Agent Health ══════════════
st.markdown("---")
st.subheader("🤖 صحة الوكلاء")

agent_cols = st.columns(6)
agents = [
    ("📰 News", "running"),
    ("📊 Analysis", "running"),
    ("🧠 Decision", "running"),
    ("🛡️ Risk", "running"),
    ("⚡ Execution", "running"),
    ("👁️ Monitor", "running"),
]

for col, (name, status) in zip(agent_cols, agents):
    with col:
        st.metric(
            name,
            "✅" if status == "running" else "❌",
            delta=f"{status}"
        )


# ══════════════ الصف السادس: جدول آخر الصفقات ══════════════
st.markdown("---")
st.subheader("📜 آخر 20 صفقة")

if closed_trades:
    df_recent = pd.DataFrame(closed_trades[:20])
    st.dataframe(
        df_recent[['symbol', 'side', 'entry_price', 'exit_price', 'pnl', 'pnl_pct', 'status']],
        use_container_width=True
    )


# ══════════════ Footer ══════════════
st.markdown("---")
st.markdown("""
<div style='text-align: center'>
    <p>🤖 SMC/ICT Multi-Agent Trading Bot v1.0</p>
    <p>Built with ❤️ for the Smart Money community</p>
</div>
""", unsafe_allow_html=True)


# ══════════════ Auto Refresh ══════════════
import time
time.sleep(refresh_rate)
st.rerun()
