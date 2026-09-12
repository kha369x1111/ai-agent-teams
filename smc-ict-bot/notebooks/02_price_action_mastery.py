# ===================================================================
# 📓 SMC/ICT Knowledge Base - الجزء الثاني
# ===================================================================
# Price Action Mastery - إتقان حركة السعر
# ===================================================================
# الشمعات, الأنماط, Market Structure, Price Action
# ===================================================================

# ╔══════════════════════════════════════════════════════════════╗
# ║ 1. أنواع الشموع المتقدمة (Advanced Candles)              ║
# ╚══════════════════════════════════════════════════════════════╝

"""
📌 أهم الشموع في سياق SMC/ICT:

1. ENGULFING (الابتلاع):
   Bullish: شمعة خضراء تبتلع حمراء سابقة
   Bearish: شمعة حمراء تبتلع خضراء سابقة

   ┌───┐
   │ R │  ← مبتلعة
   ├───┤
   │ G │
   └───┘  ← مبتلية

2. HAMMER / SHOOTING STAR:
   Hammer (أسفل): جسم صغير + ظل سفلي طويل
   → انعكاس صعودي

   Shooting Star (أعلى): جسم صغير + ظل علوي طويل
   → انعكاس هبوطي

3. MORNING / EVENING STAR:
   نمط 3 شموع = انعكاس قوي

4. THREE WHITE SOLDIERS / BLACK CROWS:
   3 شموع متتالية في اتجاه = قوة كبيرة
"""


def detect_candlestick_patterns(df: pd.DataFrame) -> list:
    """كشف أنماط الشموع المتقدمة"""
    patterns = []

    for i in range(1, len(df)):
        current = df.iloc[i]
        prev = df.iloc[i-1]

        # Bullish Engulfing
        if (current['close'] > current['open'] and  # خضراء
            prev['close'] < prev['open'] and         # حمراء سابقة
            current['close'] > prev['open'] and      # تبتلع
            current['open'] < prev['close']):
            patterns.append({
                'type': 'bullish_engulfing',
                'index': i,
                'strength': 70,
                'timestamp': df.index[i]
            })

        # Bearish Engulfing
        if (current['close'] < current['open'] and
            prev['close'] > prev['open'] and
            current['close'] < prev['open'] and
            current['open'] > prev['close']):
            patterns.append({
                'type': 'bearish_engulfing',
                'index': i,
                'strength': 70,
                'timestamp': df.index[i]
            })

        # Hammer
        body = abs(current['close'] - current['open'])
        lower_wick = min(current['open'], current['close']) - current['low']
        upper_wick = current['high'] - max(current['open'], current['close'])

        if lower_wick > body * 2 and upper_wick < body * 0.5:
            patterns.append({
                'type': 'hammer',
                'index': i,
                'strength': 60,
                'timestamp': df.index[i]
            })

        # Shooting Star
        if upper_wick > body * 2 and lower_wick < body * 0.5:
            patterns.append({
                'type': 'shooting_star',
                'index': i,
                'strength': 60,
                'timestamp': df.index[i]
            })

    return patterns


# ╔══════════════════════════════════════════════════════════════╗
# ║ 2. Higher Highs & Higher Lows (HH, HL, LH, LL)            ║
# ╚══════════════════════════════════════════════════════════════╝

"""
📌 Market Structure - الهيكل السوقي:

Bullish Structure:
   HH ──┐    HH ──┐
        │         │
        HH ──┘    HH
                  │
   HL ──┐    HL ──┘
        │
        HL

Bearish Structure:
   LH ──┐    LH
        │
   LL ──┘    LL ──┐
                  │
                  LL
"""


def identify_market_structure(df: pd.DataFrame, lookback: int = 5) -> dict:
    """تحديد هيكل السوق"""
    highs = df['high']
    lows = df['low']

    swing_highs = []
    swing_lows = []

    for i in range(lookback, len(df) - lookback):
        if highs.iloc[i] == highs.iloc[i-lookback:i+lookback+1].max():
            swing_highs.append({'index': i, 'price': highs.iloc[i]})

        if lows.iloc[i] == lows.iloc[i-lookback:i+lookback+1].min():
            swing_lows.append({'index': i, 'price': lows.iloc[i]})

    # تحديد الترند
    structure = {
        'swing_highs': swing_highs,
        'swing_lows': swing_lows,
        'trend': 'ranging',
        'last_hh': None,
        'last_ll': None,
    }

    if len(swing_highs) >= 2 and len(swing_lows) >= 2:
        last_sh = swing_highs[-1]['price']
        prev_sh = swing_highs[-2]['price']
        last_sl = swing_lows[-1]['price']
        prev_sl = swing_lows[-2]['price']

        if last_sh > prev_sh and last_sl > prev_sl:
            structure['trend'] = 'bullish'
            structure['last_hh'] = swing_highs[-1]
        elif last_sh < prev_sh and last_sl < prev_sl:
            structure['trend'] = 'bearish'
            structure['last_ll'] = swing_lows[-1]

    return structure


# ╔══════════════════════════════════════════════════════════════╗
# ║ 3. Supply & Demand Zones                                    ║
# ╚══════════════════════════════════════════════════════════════╝

"""
📌 Supply Zone (منطقة عرض):
- منطقة يرتفع منها السعر بقوة ثم ينخفض
- = Order Block هبوطي
- المؤسسات باعت هنا

📌 Demand Zone (منطقة طلب):
- منطقة ينخفض إليها السعر بقوة ثم يرتفع
- = Order Block صعودي
- المؤسسات اشترت هنا

📌 الفرق عن OB:
- Supply/Demand: مناطق واسعة، زمن أطول
- OB: شمعة واحدة، زمن أقصر
"""


def detect_supply_demand_zones(df: pd.DataFrame, atr_multiplier: float = 1.5) -> dict:
    """كشف مناطق العرض والطلب"""
    zones = {'supply': [], 'demand': []}

    # حساب ATR
    tr = pd.concat([
        df['high'] - df['low'],
        abs(df['high'] - df['close'].shift()),
        abs(df['low'] - df['close'].shift())
    ], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()

    for i in range(10, len(df) - 5):
        current_atr = atr.iloc[i]

        # Demand Zone: هبوط قوي ثم صعود
        if df['close'].iloc[i] < df['open'].iloc[i]:  # هابطة
            for j in range(i+1, min(i+5, len(df))):
                move = df['close'].iloc[j] - df['low'].iloc[i]
                if move > current_atr * atr_multiplier:
                    zones['demand'].append({
                        'top': df['high'].iloc[i],
                        'bottom': df['low'].iloc[i],
                        'timestamp': df.index[i],
                        'strength': min(100, (move / current_atr) * 30)
                    })
                    break

        # Supply Zone: صعود قوي ثم هبوط
        if df['close'].iloc[i] > df['open'].iloc[i]:  # صاعدة
            for j in range(i+1, min(i+5, len(df))):
                move = df['high'].iloc[i] - df['close'].iloc[j]
                if move > current_atr * atr_multiplier:
                    zones['supply'].append({
                        'top': df['high'].iloc[i],
                        'bottom': df['low'].iloc[i],
                        'timestamp': df.index[i],
                        'strength': min(100, (move / current_atr) * 30)
                    })
                    break

    return zones


# ╔══════════════════════════════════════════════════════════════╗
# ║ 4. ICT Macro Timeframes (1H, 4H, Daily)                  ║
# ╚══════════════════════════════════════════════════════════════╝

"""
📌 ICT يركز على 3 Timeframes:

1. Daily (Macro):
   - تحديد Bias العام
   - رسم Premium/Discount
   - تحديد Order Blocks الرئيسية

2. 4H (Setup):
   - البحث عن Setup
   - رسم FVG
   - تحديد نقاط الدخول

3. 1H (Entry):
   - تأكيد CHoCH
   - رسم OB أصغر
   - تنفيذ الصفقة

📌 القاعدة الذهبية:
- HTF يعطيك الاتجاه
- LTF يعطيك التوقيت
"""


def macro_timeframe_analysis(df_daily: pd.DataFrame, df_4h: pd.DataFrame, df_1h: pd.DataFrame) -> dict:
    """تحليل الأطر الزمنية الثلاثة"""
    # Daily - Bias
    daily_structure = identify_market_structure(df_daily, lookback=10)
    daily_pd = calculate_premium_discount(df_daily, lookback=100)

    # 4H - Setup
    h4_structure = identify_market_structure(df_4h, lookback=7)
    h4_obs = detect_institutional_order_blocks(df_4h)
    h4_fvgs = detect_fair_value_gaps(df_4h)

    # 1H - Entry
    h1_structure = identify_market_structure(df_1h, lookback=5)

    # Alignment Check
    aligned = (daily_structure['trend'] == h4_structure['trend'] == h1_structure['trend'])

    return {
        'daily_bias': daily_structure['trend'],
        'h4_setup': h4_structure['trend'],
        'h1_entry': h1_structure['trend'],
        'aligned': aligned,
        'confidence': 'high' if aligned else 'low',
        'obs_count': len(h4_obs),
        'fvg_count': len(h4_fvgs),
    }


# ╔══════════════════════════════════════════════════════════════╗
# ║ 5. Rejection & Continuation Patterns                        ║
# ╚══════════════════════════════════════════════════════════════╝

"""
📌 Rejection (الرفض):
السعر يلمس منطقة معينة ويرفض بقوة

   ───── Resistance
       │
       ╲
        ╲  ← Rejection wick
         │
         Body

📌 Continuation (الاستمرار):
- Bullish flag, bearish flag
- Pennants, triangles
- بعد حركة قوية = استمرار
"""


def detect_rejection_patterns(df: pd.DataFrame, min_rejection_pct: float = 0.5) -> list:
    """كشف أنماط الرفض"""
    rejections = []

    for i in range(1, len(df)):
        candle = df.iloc[i]
        total_range = candle['high'] - candle['low']

        if total_range == 0:
            continue

        upper_wick = candle['high'] - max(candle['open'], candle['close'])
        lower_wick = min(candle['open'], candle['close']) - candle['low']
        body = abs(candle['close'] - candle['open'])

        # Upper rejection (رفض علوي = إشارة هبوطية)
        if upper_wick / total_range > 0.6 and upper_wick > body * 2:
            rejections.append({
                'type': 'upper_rejection',
                'index': i,
                'strength': min(100, (upper_wick / total_range) * 100),
                'timestamp': df.index[i]
            })

        # Lower rejection (رفض سفلي = إشارة صعودية)
        if lower_wick / total_range > 0.6 and lower_wick > body * 2:
            rejections.append({
                'type': 'lower_rejection',
                'index': i,
                'strength': min(100, (lower_wick / total_range) * 100),
                'timestamp': df.index[i]
            })

    return rejections


# ╔══════════════════════════════════════════════════════════════╗
# ║ 6. Volume Profile (Volume Analysis)                        ║
# ╚══════════════════════════════════════════════════════════════╝

"""
📌 Volume - أهم مؤشر في Price Action:

- Volume ↑ + Price ↑ = Trend قوي ✅
- Volume ↑ + Price ↓ = Trend قوي ✅
- Volume ↓ + Price ↑ = Trend ضعيف ⚠️
- Volume ↓ + Price ↓ = Trend ضعيف ⚠️

📌 Volume Climax:
- حجم استثنائي
- = نهاية الترند المحتملة
- = Institutions distributing

📌 Volume Dry-up:
- حجم منخفض جداً
- = تجميع
- = بداية ترند جديدة
"""


def analyze_volume(df: pd.DataFrame, period: int = 20) -> dict:
    """تحليل الحجم"""
    avg_volume = df['volume'].rolling(period).mean()
    current_volume = df['volume'].iloc[-1]
    volume_ratio = current_volume / avg_volume.iloc[-1]

    # تحديد نوع الحجم
    if volume_ratio > 2.0:
        volume_type = 'climax'
    elif volume_ratio > 1.5:
        volume_type = 'high'
    elif volume_ratio < 0.5:
        volume_type = 'dry_up'
    elif volume_ratio < 0.8:
        volume_type = 'low'
    else:
        volume_type = 'normal'

    # Volume-Price Confirmation
    price_change = df['close'].iloc[-1] - df['close'].iloc[-2]
    price_change_pct = (price_change / df['close'].iloc[-2]) * 100

    if abs(price_change_pct) > 1:
        if (price_change > 0 and volume_ratio > 1) or (price_change < 0 and volume_ratio > 1):
            confirmation = 'confirmed'
        else:
            confirmation = 'divergence'
    else:
        confirmation = 'neutral'

    return {
        'current_volume': current_volume,
        'avg_volume': avg_volume.iloc[-1],
        'volume_ratio': volume_ratio,
        'volume_type': volume_type,
        'confirmation': confirmation,
    }


# ╔══════════════════════════════════════════════════════════════╗
# ║ 7. Volatility & Momentum                                    ║
# ╚══════════════════════════════════════════════════════════════╝

"""
📌 Volatility Measures:
- ATR (Average True Range)
- Bollinger Bands
- Keltner Channels

📌 Momentum:
- RSI (Relative Strength Index)
- MACD
- Stochastic

📌 في سياق SMC:
- ATR لتحديد SL/TP
- RSI للـ divergence
- Bollinger للـ squeezes
"""


def calculate_momentum_indicators(df: pd.DataFrame) -> dict:
    """حساب مؤشرات الزخم"""
    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))

    # MACD
    ema_12 = df['close'].ewm(span=12).mean()
    ema_26 = df['close'].ewm(span=26).mean()
    macd = ema_12 - ema_26
    signal = macd.ewm(span=9).mean()
    histogram = macd - signal

    return {
        'rsi': rsi.iloc[-1],
        'macd': macd.iloc[-1],
        'macd_signal': signal.iloc[-1],
        'macd_histogram': histogram.iloc[-1],
        'rsi_overbought': rsi.iloc[-1] > 70,
        'rsi_oversold': rsi.iloc[-1] < 30,
    }


# ╔══════════════════════════════════════════════════════════════╗
# ║ 8. ICT Concepts - Final Summary                            ║
# ╚══════════════════════════════════════════════════════════════╝

"""
📌 الـ "DNA" الكامل لاستراتيجية ICT:

Daily:
  1. حدد Bias (Bullish/Bearish/Ranging)
  2. ارسم Premium/Discount zones
  3. حدد Order Blocks الرئيسية
  4. حدد Liquidity Pools

4H:
  1. ابحث عن FVG داخل Discount (للشراء) أو Premium (للبيع)
  2. حدد Order Block ثانوي
  3. انتظر Liquidity Sweep

1H/15m:
  1. انتظر CHoCH
  2. ادخل عند OB/FVG
  3. SL تحت/فوق OB
  4. TP عند Liquidity Pool المقابل

📌 عوامل النجاح:
- HTF Bias ✅
- LTF Confirmation ✅
- Liquidity Sweep ✅
- OB/FVG Confluence ✅
- Kill Zone Timing ✅
- Risk Management ✅

بدون أي من هذه = صفقة ضعيفة
مع 4-5 = A+ Setup
"""


def final_setup_quality_score(
    htf_bias: str,
    ltf_choch: bool,
    liquidity_sweep: bool,
    ob_confluence: bool,
    fvg_confluence: bool,
    in_kill_zone: bool,
    volume_confirmed: bool,
) -> dict:
    """تقييم نهائي لجودة الـ Setup"""
    score = 0
    reasons = []

    if htf_bias in ['bullish', 'bearish']:
        score += 20
        reasons.append(f"✅ HTF Bias: {htf_bias} (+20)")

    if ltf_choch:
        score += 15
        reasons.append("✅ LTF CHoCH (+15)")

    if liquidity_sweep:
        score += 20
        reasons.append("✅ Liquidity Sweep (+20)")

    if ob_confluence:
        score += 15
        reasons.append("✅ Order Block Confluence (+15)")

    if fvg_confluence:
        score += 10
        reasons.append("✅ FVG Confluence (+10)")

    if in_kill_zone:
        score += 10
        reasons.append("✅ In Kill Zone (+10)")

    if volume_confirmed:
        score += 10
        reasons.append("✅ Volume Confirmed (+10)")

    # Grade
    if score >= 85:
        grade = 'A+'
    elif score >= 75:
        grade = 'A'
    elif score >= 65:
        grade = 'B'
    elif score >= 50:
        grade = 'C'
    else:
        grade = 'D'

    return {
        'score': score,
        'grade': grade,
        'reasons': reasons,
        'tradeable': score >= 65,
    }


# ═══════════════════════════════════════════════════════════════════
print("=" * 60)
print("✅ Price Action Mastery - Knowledge Base Loaded")
print("=" * 60)
print("📊 8 مفاهيم رئيسية")
print("🎯 جاهز للاستخدام مع ML")
print("=" * 60)
