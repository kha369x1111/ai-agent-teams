# 🚀 ابدأ من هنا - دليل سريع

## الإجابة المباشرة على أسئلتك:

---

## ❓ "أين الملف الذي أضغطه مرتين؟"

### الجواب:

```
الملفات في المستودع على GitHub
يجب أن تنزّلها على جهازك أولاً
```

### 📍 الموقع الحالي:

```
على GitHub:
https://github.com/kha369x1111/ai-agent-teams
→ مجلد: smc-ict-bot
→ ستجد: START.bat, MENU.bat, APP.bat, إلخ

على جهازك (بعد التنزيل):
C:\Users\اسمك\Desktop\trading-bot\ai-agent-teams\smc-ict-bot\
→ نفس الملفات
```

### 📥 طريقة التنزيل:

```
الطريقة 1: Git (الموصى بها)
1. ثبّت Git من: https://git-scm.com/download/win
2. افتح cmd واكتب:
   cd Desktop
   git clone https://github.com/kha369x1111/ai-agent-teams.git
   cd ai-agent-teams\smc-ict-bot

الطريقة 2: ZIP (الأسهل)
1. افتح: https://github.com/kha369x1111/ai-agent-teams
2. اضغط الزر الأخضر "Code"
3. اضغط "Download ZIP"
4. فك الضغط في سطح المكتب
5. ادخل مجلد smc-ict-bot
```

---

## ❓ "هل يلزم ربط API؟"

### الجواب:

```
✅ نعم - Binance API ضروري
⚠️ Telegram - موصى به (اختياري)
```

### 🤔 ليش API ضروري؟

```
تخيل API = مفتاح بيتك

بدون مفتاح:
❌ ما تقدر تدخل بيتك
❌ ما تقدر تاخذ أغراضك
❌ ما تقدر تسكن فيه

مع مفتاح:
✅ تدخل بيتك
✅ تاخذ أغراضك
✅ تسكن براحتك
```

### 📋 ما تحتاجه من APIs:

```
الضروري:
━━━━━━━━━━━
1. 🔑 Binance Testnet API
   • المكان: https://testnet.binancefuture.com
   • التكلفة: مجاني 100%
   • الاستخدام: تداول تجريبي

الموصى به:
━━━━━━━━━━
2. 📱 Telegram Bot Token
   • المكان: @BotFather في Telegram
   • التكلفة: مجاني
   • الاستخدام: تنبيهات

3. 📱 Telegram Chat ID
   • المكان: @userinfobot
   • التكلفة: مجاني
   • الاستخدام: معرفة مكان إرسال التنبيهات

اختياري (لاحقاً):
━━━━━━━━━━━━━━━
4. 🔑 Bybit API
5. 🔑 OKX API
6. 🔑 Binance Live API (بعد شهر+)
```

---

## 🚀 خطوات البدء (15 دقيقة):

### الخطوة 1️⃣: تنزيل Python (5 دقائق)

```
1. افتح: https://www.python.org/downloads/
2. اضغط "Download Python 3.11.x"
3. شغّل الملف
4. ☑️ ضع علامة على "Add Python to PATH" ← مهم جداً!
5. اضغط "Install Now"
```

### الخطوة 2️⃣: تنزيل المشروع (3 دقائق)

```
1. افتح: https://github.com/kha369x1111/ai-agent-teams
2. اضغط الزر الأخضر "Code"
3. اضغط "Download ZIP"
4. فك الضغط في سطح المكتب
5. ادخل مجلد smc-ict-bot
```

### الخطوة 3️⃣: تثبيت المكتبات (5 دقائق)

```
1. في مجلد smc-ict-bot
2. اضغط مرتين على: MENU.bat
3. اختر رقم [5] Install Dependencies
4. انتظر 5-15 دقيقة
```

### الخطوة 4️⃣: إعداد API (5 دقائق)

```
4.1 - Binance API:
━━━━━━━
• افتح: https://testnet.binancefuture.com
• سجّل دخول بـ GitHub
• اذهب لـ: API Management
• اضغط: Create API
• انسخ: API Key و Secret Key

4.2 - Telegram Bot (اختياري):
━━━━━━━━━━━━━━
• افتح Telegram
• ابحث عن: @BotFather
• أرسل: /newbot
• اتبع التعليمات
• انسخ: Bot Token

• ابحث عن: @userinfobot
• أرسل أي رسالة
• انسخ: رقم الـ ID
```

### الخطوة 5️⃣: تعديل .env

```
1. في المجلد، اضغط مرتين: MENU.bat
2. اختر [4] Setup .env
3. سيفتح ملف في Notepad
4. استبدل:

BINANCE_API_KEY=الصق_مفتاحك_هنا
BINANCE_API_SECRET=الصق_سر_هنا
TELEGRAM_BOT_TOKEN=الصق_التوكن_هنا
TELEGRAM_CHAT_ID=الصق_الرقم_هنا

5. احفظ: Ctrl + S
6. أغلق Notepad
```

### الخطوة 6️⃣: اختبار

```
1. شغّل MENU.bat
2. اختر [6] Test Connection
3. يجب أن ترى:
   ✅ Python OK
   ✅ Libraries OK
   ✅ Binance Connected
   ✅ Telegram Connected
```

### الخطوة 7️⃣: التشغيل!

```
1. شغّل MENU.bat
2. اختر [1] Start Bot
   أو
3. اضغط مرتين على START.bat مباشرة
```

---

## 🎯 الملفات المهمة:

```
📄 START.bat         - تشغيل سريع (للخبراء)
📄 MENU.bat          - قائمة بكل الخيارات (للمبتدئين)
📄 APP.bat           - تطبيق GUI جميل
📄 DASHBOARD.bat     - فتح Dashboard
📄 NOTEBOOKS.bat     - فتح Jupyter

📄 .env.example      - نموذج ملف الإعدادات
📄 README.md         - الدليل الكامل
```

---

## 🆘 إذا واجهت مشكلة:

```
❌ "Python is not recognized"
→ أعد تثبيت Python مع "Add to PATH"

❌ "No module named X"
→ شغّل MENU.bat → [5] Install Dependencies

❌ "API key invalid"
→ تحقق من .env - هل نسخت المفتاح بشكل صحيح؟

❌ "Telegram failed"
→ تحقق من BOT_TOKEN و CHAT_ID

💡 أرسل لي رسالة الخطأ وسأساعدك!
```

---

## ⚡ ملخص في 3 خطوات:

```
1️⃣  حمّل Python + المشروع
2️⃣  شغّل MENU.bat → [5] Install
3️⃣  ضع المفاتيح في .env → شغّل البوت

🎉 خلاص!
```

---

**🎯 الإجابة النهائية:**

```
❓ أين الملف؟
→ في مجلد smc-ict-bot بعد التنزيل
→ اضغط مرتين على MENU.bat

❓ هل يلزم API؟
→ نعم، Binance ضروري
→ Telegram موصى به
→ بدونهم البوت لن يعمل
```
