# ===================================================================
# 📓 SMC/ICT Knowledge Base - الجزء الأول
# ===================================================================
# المنطق المؤسسي الكامل (Institutional Trading Logic)
# ===================================================================
# هذا الملف يحتوي على كل المفاهيم المؤسسية:
# - Smart Money Concepts (SMC)
# - Inner Circle Trader (ICT)
# - Wyckoff Method
# - Auction Market Theory
# - Order Flow
# - Liquidity Engineering
# ===================================================================

# ╔══════════════════════════════════════════════════════════════╗
# ║ 1. مفهوم السيولة (Liquidity) - قلب كل شيء                ║
# ╚══════════════════════════════════════════════════════════════╝

"""
📌 التعريف المؤسسي:
السيولة هي وقود السوق. المؤسسات تحتاج سيولة لملء أوامرها الكبيرة.

   RETAIL TRADERS    →    يبحثون عن SLs
   INSTITUTIONS      →    يبحثون عن LIQUIDITY

📌 أنواع السيولة:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
| النوع                    | الأهمية |
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
| Buy-Side Liquidity       | ⭐⭐⭐⭐⭐ |
| Sell-Side Liquidity      | ⭐⭐⭐⭐⭐ |
| Equal Highs/Lows         | ⭐⭐⭐⭐   |
| Stop Losses              | ⭐⭐⭐⭐⭐ |
| Round Numbers            | ⭐⭐⭐    |
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

# ══════════════ الكود ══════════════
import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime


def detect_liquidity_zones(df: pd.DataFrame, lookback: int = 20) -> Dict:
    """
    كشف مناطق السيولة المؤسسية
    """
    liquidity_zones = {
        'buy_side': [],   # فوق القمم
        'sell_side': [],  # تحت القيعان
        'equal_highs': [],
        'equal_lows': [],
    }

    # كشف القمم والقيعان
    for i in range(lookback, len(df) - 1):
        current_high = df['high'].iloc[i]
        current_low = df['low'].iloc[i]

        # Equal Highs (قمتين متساويتين = سيولة قوية)
        similar_highs = []
        for j in range(max(0, i - lookback*3), i):
            if abs(df['high'].iloc[j] - current_high) / current_high < 0.001:
                similar_highs.append(j)

        if len(similar_highs) >= 2:
            liquidity_zones['equal_highs'].append({
                'price': current_high,
                'indices': similar_highs + [i],
                'strength': len(similar_highs) * 10,
                'type': 'buy_side',
                'timestamp': df.index[i]
            })

        # Equal Lows
        similar_lows = []
        for j in range(max(0, i - lookback*3), i):
            if abs(df['low'].iloc[j] - current_low) / current_low < 0.001:
                similar_lows.append(j)

        if len(similar_lows) >= 2:
            liquidity_zones['equal_lows'].append({
                'price': current_low,
                'indices': similar_lows + [i],
                'strength': len(similar_lows) * 10,
                'type': 'sell_side',
                'timestamp': df.index[i]
            })

    return liquidity_zones


# ╔══════════════════════════════════════════════════════════════╗
# ║ 2. Order Blocks (OB) - بصمة المؤسسات                     ║
# ╚══════════════════════════════════════════════════════════════╝

"""
📌 التعريف:
Order Block = آخر شمعة معاكسة قبل حركة قوية (Displacement)

Bullish OB:
   ┌─────────┐
   │ Bearish │ ← OB (آخر شمعة هابطة)
   └─────────┘
       ↓
   ┌─────────┐
   │DISPLACE │ ← حركة قوية صاعدة
   └─────────┘

المؤسسات: اشترت في OB → دفعت السعر بقوة

📌 خصائص Order Block الجيد:
1. ✅ يأتي بعد displacement قوي
2. ✅ حجم تداول عالي
3. ✅ لم يُختبر (Unmitigated)
4. ✅ في منطقة Premium/Discount مناسبة
5. ✅ Confluence مع FVG أو BOS
"""


def detect_institutional_order_blocks(df: pd.DataFrame, atr_period: int = 14) -> List[Dict]:
    """كشف OB بأسلوب مؤسسي مع تقييم القوة"""
    obs = []

    # حساب ATR
    tr = pd.concat([
        df['high'] - df['low'],
        abs(df['high'] - df['close'].shift()),
        abs(df['low'] - df['close'].shift())
    ], axis=1).max(axis=1)
    atr = tr.rolling(atr_period).mean()

    for i in range(2, len(df) - 1):
        current_atr = atr.iloc[i]
        if pd.isna(current_atr):
            continue

        # Bullish OB: شمعة هابطة قبل صعود قوي
        if df['close'].iloc[i] < df['open'].iloc[i]:  # هابطة
            next_move = df['close'].iloc[i+1] - df['low'].iloc[i]
            if next_move > current_atr * 0.8:
                ob = {
                    'type': 'bullish',
                    'index': i,
                    'top': df['high'].iloc[i],
                    'bottom': df['low'].iloc[i],
                    'midpoint': (df['high'].iloc[i] + df['low'].iloc[i]) / 2,
                    'strength': min(100, (next_move / current_atr) * 50),
                    'volume_ratio': df['volume'].iloc[i] / df['volume'].rolling(20).mean().iloc[i],
                    'mitigated': False,
                    'timestamp': df.index[i]
                }
                obs.append(ob)

        # Bearish OB: شمعة صاعدة قبل هبوط قوي
        elif df['close'].iloc[i] > df['open'].iloc[i]:  # صاعدة
            next_move = df['high'].iloc[i+1] - df['close'].iloc[i]
            if next_move > current_atr * 0.8:
                ob = {
                    'type': 'bearish',
                    'index': i,
                    'top': df['high'].iloc[i],
                    'bottom': df['low'].iloc[i],
                    'midpoint': (df['high'].iloc[i] + df['low'].iloc[i]) / 2,
                    'strength': min(100, (next_move / current_atr) * 50),
                    'volume_ratio': df['volume'].iloc[i] / df['volume'].rolling(20).mean().iloc[i],
                    'mitigated': False,
                    'timestamp': df.index[i]
                }
                obs.append(ob)

    return obs


# ╔══════════════════════════════════════════════════════════════╗
# ║ 3. Fair Value Gaps (FVG) - عدم الكفاءة                  ║
# ╚══════════════════════════════════════════════════════════════╝

"""
📌 التعريف:
FVG = فجوة بين 3 شموع حيث لا يتداخل الـ wicks

Bullish FVG:
   Candle 1   Candle 2 (big)   Candle 3
   ─┬─         ─┬─              ─┬─
    │          ▓▓▓▓▓▓           │  ← gap (low[3] > high[1])
   ─┴─         ─┴─              ─┴─

Bearish FVG: العكس

📌 لماذا FVG مهم؟
- يُظهر عدم كفاءة في السعر
- المؤسسات تتحرك بقوة → السعر "يتخطى" منطقة
- السوق يعود لاحقاً لملء هذه الفجوة
"""


def detect_fair_value_gaps(df: pd.DataFrame, min_size_pct: float = 0.1) -> List[Dict]:
    """كشف الفجوات السعرية"""
    fvgs = []

    for i in range(2, len(df)):
        candle_2_ago = df.iloc[i - 2]
        current = df.iloc[i]

        # Bullish FVG
        if current['low'] > candle_2_ago['high']:
            gap_size = current['low'] - candle_2_ago['high']
            gap_pct = (gap_size / candle_2_ago['high']) * 100

            if gap_pct >= min_size_pct:
                fvg = {
                    'type': 'bullish',
                    'index': i,
                    'top': current['low'],
                    'bottom': candle_2_ago['high'],
                    'midpoint': (current['low'] + candle_2_ago['high']) / 2,
                    'size': gap_size,
                    'size_pct': gap_pct,
                    'filled': False,
                    'timestamp': df.index[i]
                }
                fvgs.append(fvg)

        # Bearish FVG
        elif current['high'] < candle_2_ago['low']:
            gap_size = candle_2_ago['low'] - current['high']
            gap_pct = (gap_size / candle_2_ago['low']) * 100

            if gap_pct >= min_size_pct:
                fvg = {
                    'type': 'bearish',
                    'index': i,
                    'top': candle_2_ago['low'],
                    'bottom': current['high'],
                    'midpoint': (candle_2_ago['low'] + current['high']) / 2,
                    'size': gap_size,
                    'size_pct': gap_pct,
                    'filled': False,
                    'timestamp': df.index[i]
                }
                fvgs.append(fvg)

    return fvgs


# ╔══════════════════════════════════════════════════════════════╗
# ║ 4. Break of Structure (BOS) & CHoCH                       ║
# ╚══════════════════════════════════════════════════════════════╝

"""
📌 BOS (Break of Structure):
- كسر الهيكل في نفس اتجاه الترند
- تأكيد استمرارية الترند

📌 CHoCH (Change of Character):
- كسر الهيكل في عكس اتجاه الترند
- أول إشارة لانعكاس محتمل

Bullish BOS:  HH → HL → HH → BOS (استمرار صعودي)
Bullish CHoCH: LH → HL → CHoCH فوق LH (انعكاس صعودي)

📌 الأهمية:
- BOS = تأكيد، CHoCH = تحذير
- ICT يقول: "BOS is your entry, CHoCH is your warning"
"""


def detect_bos_choch(df: pd.DataFrame, swing_lookback: int = 10) -> Dict:
    """كشف كسر وتغيير الهيكل"""
    structures = {
        'bos': [],
        'choch': [],
        'trend': 'ranging',
    }

    # كشف Swing Points
    swing_highs = []
    swing_lows = []

    for i in range(swing_lookback, len(df) - swing_lookback):
        # Swing High
        if df['high'].iloc[i] == df['high'].iloc[i-swing_lookback:i+swing_lookback+1].max():
            swing_highs.append({'index': i, 'price': df['high'].iloc[i], 'timestamp': df.index[i]})

        # Swing Low
        if df['low'].iloc[i] == df['low'].iloc[i-swing_lookback:i+swing_lookback+1].min():
            swing_lows.append({'index': i, 'price': df['low'].iloc[i], 'timestamp': df.index[i]})

    # تحديد الترند
    if len(swing_highs) >= 2 and len(swing_lows) >= 2:
        last_hh = swing_highs[-1]['price'] > swing_highs[-2]['price']
        last_hl = swing_lows[-1]['price'] > swing_lows[-2]['price']
        last_lh = swing_highs[-1]['price'] < swing_highs[-2]['price']
        last_ll = swing_lows[-1]['price'] < swing_lows[-2]['price']

        if last_hh and last_hl:
            structures['trend'] = 'bullish'
        elif last_lh and last_ll:
            structures['trend'] = 'bearish'

    return structures


# ╔══════════════════════════════════════════════════════════════╗
# ║ 5. Premium & Discount Zones                                ║
# ╚══════════════════════════════════════════════════════════════╝

"""
📌 المفهوم:
السوق يتأرجح بين Premium (فوق 50%) و Discount (تحت 50%)

        Premium Zone (50%-100%)
        ════════════════════ High
        ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒
        ───── Equilibrium (50%)
        ░░░░░░░░░░░░░░░░░░
        ════════════════════ Low
        Discount Zone (0%-50%)

📌 القواعد:
- اشترِ في Discount ✅
- بيع في Premium ✅
- هذا ما يفعله Money Manager الحقيقي

📌 Fibonacci Levels:
- 0%   = Low
- 50%  = Equilibrium
- 61.8% = Optimal Trade Entry (OTE)
- 100% = High
"""


def calculate_premium_discount(df: pd.DataFrame, lookback: int = 50) -> Dict:
    """حساب مناطق Premium/Discount"""
    recent_high = df['high'].tail(lookback).max()
    recent_low = df['low'].tail(lookback).min()
    range_size = recent_high - recent_low

    equilibrium = recent_low + (range_size * 0.5)
    ote_buy = recent_low + (range_size * 0.618)  # Optimal Trade Entry للشراء
    ote_sell = recent_high - (range_size * 0.618)  # للبيع

    return {
        'high': recent_high,
        'low': recent_low,
        'equilibrium': equilibrium,
        'ote_buy': ote_buy,
        'ote_sell': ote_sell,
        'premium_range': (equilibrium, recent_high),
        'discount_range': (recent_low, equilibrium),
        'range_size': range_size,
    }


# ╔══════════════════════════════════════════════════════════════╗
# ║ 6. ICT Kill Zones - أوقات التداول المثالية               ║
# ╚══════════════════════════════════════════════════════════════╝

"""
📌 Kill Zones (UTC times):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
| Zone              | Time (UTC) |
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
| London Open       | 02:00-05:00 |
| New York Open     | 07:00-10:00 |
| London Close      | 10:00-12:00 |
| New York Close    | 12:00-15:00 |
| Asian Session     | 00:00-08:00 |
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📌 Silver Bullet (أقوى الأوقات):
- 10:00-11:00 AM EST (NY Session)
- 02:00-03:00 AM EST (London)
- 03:00-04:00 AM EST (London/NY Overlap)

📌 لماذا؟
- أعلى سيولة
- تحركات كبيرة
- المؤسسات نشطة
"""


def is_kill_zone(dt: datetime) -> Tuple[bool, str]:
    """تحديد ما إذا كان الوقت في Kill Zone"""
    hour = dt.hour

    if 2 <= hour < 5:
        return True, "London Open"
    elif 7 <= hour < 10:
        return True, "New York Open"
    elif 10 <= hour < 12:
        return True, "London Close"
    elif 12 <= hour < 15:
        return True, "New York Close"

    return False, "Off-hours"


# ╔══════════════════════════════════════════════════════════════╗
# ║ 7. Wyckoff Method - تجميع المؤسسات                       ║
# ╚══════════════════════════════════════════════════════════════╝

"""
📌 Wyckoff 3 Laws:
1. Law of Supply & Demand
2. Law of Cause & Effect
3. Law of Effort & Result

📌 Wyckoff Phases:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ACCUMULATION (تجميع):
├─ Phase A: Stopping Action (PSY, SC, AR, ST)
├─ Phase B: Cause Building (Spring)
├─ Phase C: Test (Spring → Test → LPS)
└─ Phase D: Markup

DISTRIBUTION (توزيع):
├─ Phase A: Buying Climax (BC, AR, ST)
├─ Phase B: Cause Building (UTAD)
├─ Phase C: Test
└─ Phase D: Markdown
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""


# ╔══════════════════════════════════════════════════════════════╗
# ║ 8. Market Maker Model (3M) - نموذج صانع السوق            ║
# ╚══════════════════════════════════════════════════════════════╝

"""
📌 ICT's Market Maker Model:

الترند الصاعد:
   1. Accumulation (تجميع في القاع)
   2. Manipulation (كاذب تحت القاع - Judas Swing)
   3. Distribution (الحركة الحقيقية للأعلى)

الترند الهابط: العكس

📌 Judas Swing:
- حركة كاذبة في عكس الاتجاه
- لجمع السيولة (SLs) قبل الحركة الحقيقية
- يحدث عادة في Kill Zones
"""


# ╔══════════════════════════════════════════════════════════════╗
# ║ 9. Power of 3 (PO3) - القوة الثلاثية                    ║
# ╚══════════════════════════════════════════════════════════════╝

"""
📌 Power of 3:
أي جلسة تداول تتكون من 3 مراحل:

   ┌─────────────────────────────────────┐
   │  1. ACCUMULATION (التجميع)        │ ← المؤسسات تجمع
   ├─────────────────────────────────────┤
   │  2. MANIPULATION (التلاعب)        │ ← Judas Swing
   ├─────────────────────────────────────┤
   │  3. DISTRIBUTION (التوزيع)        │ ← الحركة الحقيقية
   └─────────────────────────────────────┘

📌 كيف تكشفها؟
- شوشعة كبيرة = Accumulation
- كسر وهمي في اتجاه = Manipulation
- حركة قوية في الاتجاه الحقيقي = Distribution
"""


# ╔══════════════════════════════════════════════════════════════╗
# ║ 10. الاستراتيجية الكاملة (الدمج)                          ║
# ╚══════════════════════════════════════════════════════════════╝

"""
📌 ICT 2022 Strategy (الأقوى):

الخطوة 1: حدد Higher Timeframe Bias (Daily)
الخطوة 2: انتظر في Discount/OTE
الخطوة 3: ابحث عن FVG + OB في المنطقة
الخطوة 4: انتظر Liquidity Sweep
الخطوة 5: دخول بعد CHoCH على LTF
الخطوة 6: SL تحت OB, TP عند Liquidity Pool

📌 Confluence Requirements:
- HTF Bias ✅
- HTF OB/FVG ✅
- LTF CHoCH ✅
- Liquidity Sweep ✅
- في Kill Zone ✅
"""


def full_strategy_check(
    df_htf: pd.DataFrame,   # Higher Timeframe (Daily)
    df_ltf: pd.DataFrame,   # Lower Timeframe (4H)
) -> Dict:
    """تطبيق الاستراتيجية الكاملة"""
    # HTF Analysis
    htf_structure = detect_bos_choch(df_htf, swing_lookback=20)
    htf_pd = calculate_premium_discount(df_htf, lookback=50)

    # LTF Analysis
    ltf_structure = detect_bos_choch(df_ltf, swing_lookback=10)
    ltf_obs = detect_institutional_order_blocks(df_ltf)
    ltf_fvgs = detect_fair_value_gaps(df_ltf)
    ltf_liquidity = detect_liquidity_zones(df_ltf)

    return {
        'htf_trend': htf_structure['trend'],
        'htf_equilibrium': htf_pd['equilibrium'],
        'ltf_trend': ltf_structure['trend'],
        'ltf_order_blocks': len(ltf_obs),
        'ltf_fvgs': len(ltf_fvgs),
        'ltf_liquidity_zones': len(ltf_liquidity['equal_highs']) + len(ltf_liquidity['equal_lows']),
        'bias': 'bullish' if htf_structure['trend'] == 'bullish' else 'bearish' if htf_structure['trend'] == 'bearish' else 'neutral',
    }


# ═══════════════════════════════════════════════════════════════════
# 📌 ملخص Knowledge Base
# ═══════════════════════════════════════════════════════════════════
"""
✅ 10 مفاهيم أساسية مغطاة
✅ كل مفهوم له كود قابل للتنفيذ
✅ جاهز للاستخدام في البوت
✅ جاهز للتعلم الآلي (ML)

الخطوة التالية: ML يتعلم من هذه المفاهيم ويحسن الـ Confluence Score
"""
