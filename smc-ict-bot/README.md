# SMC/ICT Trading Bot 🤖📈

> نظام آلي احترافي لتداول العملات الرقمية بأسلوب **Smart Money Concepts (SMC)** و **Inner Circle Trader (ICT)**

## 🎯 الاستراتيجية

يركز هذا البوت على **Liquidity Sweeps** (جذب السيولة) على الإطارات الزمنية العليا (4H/Daily) مع تأكيد متعدد الإطارات الزمنية.

### المفاهيم الأساسية المستخدمة:

- **Liquidity Sweeps** - جذب السيولة وكسر المستويات (التركيز الأساسي)
- **Order Blocks (OB)** - مناطق العرض والطلب المؤسسية
- **Fair Value Gaps (FVG)** - فجوات القيمة العادلة
- **Break of Structure (BOS)** - كسر الهيكل
- **Change of Character (CHoCH)** - تغيير الاتجاه
- **Premium/Discount Zones** - مناطقPremium والخصم

### منطق الدخول:

```
1. كشف Liquidity Sweep على إطار 4H (كسر مستوى سيولة + رفض)
2. تأكيد الاتجاه من الإطار الأعلى (Daily)
3. البحث عن Confluence مع OB / FVG / Structure
4. حساب Confluence Score (يجب >= 60/100)
5. حساب R:R Ratio (يجب >= 1:2)
6. تنفيذ الصفقة مع SL/TP
```

## 📁 هيكل المشروع

```
smc-ict-bot/
├── config/
│   └── settings.py           # إعدادات النظام
├── core/
│   ├── data/
│   │   └── binance_connector.py  # الاتصال بـ Binance
│   ├── analysis/
│   │   └── smc_detector.py       # محركات التحليل SMC/ICT
│   └── signals/
├── strategies/
│   └── liquidity_sweep_strategy.py  # استراتيجية Liquidity Sweep
├── risk/
│   └── risk_manager.py          # إدارة المخاطر
├── execution/                   # طبقة التنفيذ
├── monitoring/
│   ├── alerts/
│   │   └── telegram_bot.py      # تنبيهات Telegram
│   └── dashboard/               # لوحة التحكم
├── tests/                       # الاختبارات
├── main.py                      # نقطة الدخول الرئيسية
├── requirements.txt
└── .env.example
```

## 🚀 التثبيت والتشغيل

### 1. متطلبات النظام

```bash
# Python 3.11+
python --version

# TA-Lib (Technical Analysis Library)
# Ubuntu/Debian:
sudo apt-get install ta-lib

# macOS:
brew install ta-lib

# Windows: تحميل من https://github.com/ta-lib/ta-lib
```

### 2. تثبيت المكتبات

```bash
# إنشاء virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# أو: venv\Scripts\activate  # Windows

# تثبيت المكتبات
pip install -r requirements.txt
```

### 3. إعداد البيئة

```bash
# نسخ ملف البيئة
cp .env.example .env

# تعديل القيم في .env:
# - BINANCE_API_KEY و BINANCE_API_SECRET (ابدأ بـ Testnet!)
# - TELEGRAM_BOT_TOKEN و TELEGRAM_CHAT_ID
```

### 4. الحصول على مفاتيح Binance Testnet

```bash
# 1. اذهب إلى: https://testnet.binancefuture.com
# 2. سجل دخول بحساب GitHub
# 3. اذهب إلى API Management
# 4. أنشئ API Key جديدة
# 5. انسخ المفتاح والسر إلى .env
```

### 5. تشغيل البوت

```bash
# تشغيل عادي
python main.py

# مع logs مباشرة
python main.py 2>&1 | tee logs/run.log
```

## ⚙️ الإعدادات (Configuration)

### الاستراتيجية

| المعامل | القيمة الافتراضية | الوصف |
|---------|-------------------|-------|
| `primary_timeframe` | `4h` | الإطار الزمني الأساسي |
| `higher_timeframe` | `1d` | الإطار الأعلى للتأكيد |
| `swing_lookback` | `20` | عدد الشموع لكشف القمم/القيعان |
| `sweep_threshold_pct` | `0.5` | نسبة اختراق مستوى السيولة |
| `min_sweep_rejection` | `0.3` | حد أدنى لرفض الشمعة |
| `min_confluence_score` | `60` | حد أدنى لنقاط التوافق |
| `min_rr_ratio` | `2.0` | حد أدنى لـ R:R |

### إدارة المخاطر

| المعامل | القيمة | الوصف |
|---------|--------|-------|
| `risk_per_trade_pct` | `1.0%` | المخاطرة لكل صفقة |
| `max_position_size_pct` | `5.0%` | الحد الأقصى لحجم الصفقة |
| `max_daily_loss_pct` | `3.0%` | حد الخسارة اليومية |
| `max_daily_trades` | `5` | حد الصفقات اليومية |
| `max_drawdown_pct` | `10.0%` | أقصى تراجع → إيقاف البوت |
| `max_consecutive_losses` | `3` | خسائر متتالية → إيقاف |

## 🛡️ الأمان والحماية

### قبل التشغيل الفعلي (LIVE):

```
✅ 1. اختبر على Testnet لمدة شهر على الأقل
✅ 2. احصل على نتائج إيجابية في Backtest
✅ 3. ابدأ بمبلغ صغير جداً
✅ 4. تأكد من فهمك الكامل للكود
✅ 5. راقب البوت يومياً في البداية
✅ 6. حدد API Key بـ IP restrictions
✅ 7. لا تشارك مفاتيح API مع أحد
✅ 8. فعّل 2FA على حساب Binance
```

### حدود API:

```python
# في Binance، حدد:
# - IP whitelist
# - لا تفعّل Withdrawal
# - فعّل فقط Read + Trading
```

## 📊 المراقبة والأداء

### Telegram Alerts

البوت يرسل تلقائياً:
- 🟢 إشارات جديدة
- ✅ تنفيذ الصفقات
- 🎯/🛑 إغلاق الصفقات (TP/SL)
- 📊 التقرير اليومي
- 🚨 تنبيهات الأخطاء

### Performance Metrics

```python
{
    'total_trades': عدد الصفقات,
    'win_rate': نسبة الربح %,
    'profit_factor': عامل الربح,
    'sharpe_ratio': نسبة شارب,
    'max_drawdown': أقصى تراجع,
    'avg_win': متوسط الربح,
    'avg_loss': متوسط الخسارة,
}
```

## 🧪 الاختبار

```bash
# تشغيل جميع الاختبارات
pytest tests/

# اختبار وحدة محددة
pytest tests/test_strategy.py -v

# مع تغطية
pytest --cov=. tests/
```

## 📚 مراجع SMC/ICT

### كتب:
- "Trading in the Zone" - Mark Douglas
- "The Art and Science of Technical Analysis" - Adam Hoss

### YouTube Channels:
- ICT (Inner Circle Trader) - المرجع الأساسي
- Smart Risk - Mark S.
- The Trading Channel - SMC

### مفاهيم مهمة:
1. **Liquidity is King** - السيولة هي الملك
2. **Trade with Smart Money** - تداول مع المؤسسات
3. **Multi-timeframe Analysis** - تحليل متعدد الإطارات
4. **Risk Management First** - إدارة المخاطر أولاً

## 🔧 التطوير المستقبلي

### يمكن إضافة:

```
[ ] Machine Learning لتحسين Confluence Score
[ ] Backtesting framework متقدم
[ ] Dashboard تفاعلي (React/Streamlit)
[ ] دعم منصات إضافية (Bybit, OKX)
[ ] استراتيجية ICT Silver Bullet
[ ] Order Flow Analysis
[ ] Smart Order Routing
[ ] Portfolio Optimization
```

## ⚠️ تحذيرات مهمة

> **هذا البوت أداة تعليمية وأداة مساعدة، وليس ضماناً للربح.**

```
⚠️ التداول ينطوي على مخاطر عالية
⚠️ لا تستثمر أموالاً لا تتحمل خسارتها
⚠️ اختبر دائماً قبل الاستخدام الفعلي
⚠️ الأداء السابق لا يضمن النتائج المستقبلية
⚠️ راقب البوت باستمرار
⚠️ حافظ على إدارة مخاطر صارمة
```

## 📞 الدعم

```
🐛 للإبلاغ عن مشاكل: افتح Issue على GitHub
💡 لاقتراح ميزات: افتح Discussion
📖 للتوثيق: راجع مجلد docs/
```

---

**Built with ❤️ for the SMC/ICT community**

⛓️ لا تنسَ: *Liquidity is the fuel that powers all market movements.*
