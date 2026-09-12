"""
═══════════════════════════════════════════════════════════════════
🧪 Test Connection - اختبار شامل
═══════════════════════════════════════════════════════════════════
يفحص كل المكونات ويعطي تقرير مفصّل
═══════════════════════════════════════════════════════════════════
"""

import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

print("=" * 60)
print("🧪 SMC/ICT Bot - Connection Test")
print("=" * 60)
print()

results = {'passed': 0, 'failed': 0, 'warnings': 0}

def test(name, func):
    """تنفيذ اختبار واحد"""
    print(f"⏳ {name}...", end=' ')
    try:
        result = func()
        if result == 'success':
            print("✅")
            results['passed'] += 1
        elif result == 'warning':
            print("⚠️")
            results['warnings'] += 1
        else:
            print("✅")
            results['passed'] += 1
        return True
    except Exception as e:
        print(f"❌\n   خطأ: {e}")
        results['failed'] += 1
        return False


# 1. Python
def test_python():
    import sys
    version = sys.version.split()[0]
    print(f"\n   Python {version}")
    return 'success'

test("Python Version", test_python)


# 2. Libraries
def test_libraries():
    libs = {
        'pandas': 'pandas',
        'numpy': 'numpy',
        'ccxt': 'ccxt',
        'sklearn': 'sklearn',
        'xgboost': 'xgboost',
    }
    missing = []
    for name, module in libs.items():
        try:
            __import__(module)
        except ImportError:
            missing.append(name)

    if missing:
        print(f"\n   مفقود: {', '.join(missing)}")
        print(f"   ثبّت: pip install {' '.join(missing)}")
        return 'warning'
    print("\n   كل المكتبات مثبتة")
    return 'success'

test("Required Libraries", test_libraries)


# 3. Binance
def test_binance():
    from core.data.binance_connector import BinanceConnector
    conn = BinanceConnector()
    balance = conn.get_balance()
    usdt = balance.get('free', {}).get('USDT', 0)
    print(f"\n   الرصيد: {usdt} USDT")
    return 'success'

test("Binance Connection", test_binance)


# 4. Telegram
def test_telegram():
    from monitoring.alerts.telegram_bot import TelegramAlerter
    alerter = TelegramAlerter()
    if not alerter.enabled:
        print("\n   Telegram غير مفعّل - تحقق من .env")
        return 'warning'
    result = alerter.test_connection()
    if result:
        print("\n   Telegram متصل")
        return 'success'
    print("\n   فشل الإرسال")
    return 'warning'

test("Telegram", test_telegram)


# 5. Database
def test_database():
    from ml_engine.database.database_manager import DatabaseManager
    db = DatabaseManager()
    print("\n   Database جاهز")
    db.close()
    return 'success'

test("Database", test_database)


# 6. ML
def test_ml():
    from ml_engine.ml_system import TradingMLModel
    ml = TradingMLModel()
    print("\n   ML Model جاهز")
    return 'success'

test("ML Model", test_ml)


# النتيجة
print()
print("=" * 60)
print(f"📊 النتائج: ✅ {results['passed']} | ⚠️ {results['warnings']} | ❌ {results['failed']}")
print("=" * 60)

if results['failed'] == 0:
    print("🎉 كل شيء يعمل بشكل ممتاز!")
elif results['failed'] <= 2:
    print("⚠️  بعض المكونات تحتاج إصلاح")
else:
    print("❌ يجب إصلاح عدة مشاكل قبل الاستخدام")

print()
print("⏸️  اضغط Enter للمتابعة...")
input()
