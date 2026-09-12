"""
═══════════════════════════════════════════════════════════════════
🧪 Test Connection - GUI Window
═══════════════════════════════════════════════════════════════════
اختبار كل الاتصالات بنافذة GUI جميلة
═══════════════════════════════════════════════════════════════════
"""

import sys
import os
from pathlib import Path
from datetime import datetime

try:
    import tkinter as tk
    from tkinter import ttk, messagebox, scrolledtext
except ImportError:
    print("❌ tkinter غير متوفر!")
    sys.exit(1)

# إضافة مسار المشروع
sys.path.insert(0, str(Path(__file__).parent))


class TestConnectionGUI:
    """نافذة اختبار الاتصال"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🧪 SMC/ICT - Test Connection")
        self.root.geometry("800x600")
        self.root.configure(bg='#1e1e1e')

        # الألوان
        self.colors = {
            'bg': '#1e1e1e',
            'fg': '#ffffff',
            'success': '#00ff00',
            'error': '#ff4444',
            'warning': '#ffaa00',
            'info': '#00aaff',
        }

        self.setup_ui()

    def setup_ui(self):
        """إعداد الواجهة"""
        # العنوان
        title = tk.Label(
            self.root,
            text="🧪 SMC/ICT Connection Test",
            font=("Arial", 20, "bold"),
            bg=self.colors['bg'],
            fg=self.colors['fg']
        )
        title.pack(pady=20)

        # الأزرار
        button_frame = tk.Frame(self.root, bg=self.colors['bg'])
        button_frame.pack(pady=10)

        tests = [
            ("🐍 اختبار Python", self.test_python),
            ("📦 اختبار المكتبات", self.test_libraries),
            ("🔌 اختبار Binance", self.test_binance),
            ("📱 اختبار Telegram", self.test_telegram),
            ("💾 اختبار Database", self.test_database),
            ("🧠 اختبار ML Model", self.test_ml),
            ("🚀 اختبار كل شيء", self.test_all),
        ]

        for text, command in tests:
            btn = tk.Button(
                button_frame,
                text=text,
                command=command,
                font=("Arial", 11),
                width=20,
                bg='#2d2d2d',
                fg=self.colors['fg'],
                relief='flat',
                padx=10,
                pady=5,
                cursor='hand2'
            )
            btn.pack(pady=3)

        # منطقة النتائج
        result_label = tk.Label(
            self.root,
            text="📋 النتائج:",
            font=("Arial", 12, "bold"),
            bg=self.colors['bg'],
            fg=self.colors['fg']
        )
        result_label.pack(pady=10)

        self.result_text = scrolledtext.ScrolledText(
            self.root,
            height=15,
            bg='#0a0a0a',
            fg=self.colors['fg'],
            font=("Consolas", 10),
            insertbackground=self.colors['fg']
        )
        self.result_text.pack(padx=20, pady=10, fill='both', expand=True)

    def log(self, message, status='info'):
        """إضافة رسالة للنتيجة"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        colors = {
            'success': '✅',
            'error': '❌',
            'warning': '⚠️',
            'info': 'ℹ️',
        }
        icon = colors.get(status, '•')

        self.result_text.insert('end', f"[{timestamp}] {icon} {message}\n")

        # تلوين
        if status == 'success':
            self.result_text.tag_add('success', 'end-2c linestart', 'end')
            self.result_text.tag_config('success', foreground=self.colors['success'])
        elif status == 'error':
            self.result_text.tag_add('error', 'end-2c linestart', 'end')
            self.result_text.tag_config('error', foreground=self.colors['error'])
        elif status == 'warning':
            self.result_text.tag_add('warning', 'end-2c linestart', 'end')
            self.result_text.tag_config('warning', foreground=self.colors['warning'])

        self.result_text.see('end')
        self.root.update()

    def test_python(self):
        """اختبار Python"""
        self.log("اختبار Python...", 'info')
        try:
            import sys
            version = sys.version.split()[0]
            self.log(f"Python {version} ✅", 'success')
        except Exception as e:
            self.log(f"فشل: {e}", 'error')

    def test_libraries(self):
        """اختبار المكتبات"""
        self.log("اختبار المكتبات...", 'info')

        libraries = [
            ('pandas', 'pandas'),
            ('numpy', 'numpy'),
            ('ccxt', 'ccxt'),
            ('sklearn', 'sklearn'),
            ('xgboost', 'xgboost'),
            ('streamlit', 'streamlit'),
        ]

        for name, module in libraries:
            try:
                __import__(module)
                self.log(f"{name} ✅", 'success')
            except ImportError:
                self.log(f"{name} ❌ - ثبّته: pip install {module}", 'error')

    def test_binance(self):
        """اختبار Binance"""
        self.log("اختبار Binance...", 'info')
        try:
            from core.data.binance_connector import BinanceConnector
            connector = BinanceConnector()
            balance = connector.get_balance()
            self.log(f"Binance متصل ✅ | الرصيد: {balance.get('free', {}).get('USDT', 0)} USDT", 'success')
        except Exception as e:
            self.log(f"Binance فشل ❌ | {e}", 'error')

    def test_telegram(self):
        """اختبار Telegram"""
        self.log("اختبار Telegram...", 'info')
        try:
            from monitoring.alerts.telegram_bot import TelegramAlerter
            alerter = TelegramAlerter()
            if alerter.enabled:
                result = alerter.test_connection()
                if result:
                    self.log("Telegram متصل ✅", 'success')
                else:
                    self.log("Telegram فشل في الإرسال ❌", 'error')
            else:
                self.log("Telegram غير مفعّل - تحقق من .env ⚠️", 'warning')
        except Exception as e:
            self.log(f"Telegram فشل ❌ | {e}", 'error')

    def test_database(self):
        """اختبار Database"""
        self.log("اختبار Database...", 'info')
        try:
            from ml_engine.database.database_manager import DatabaseManager
            db = DatabaseManager()
            stats = db.get_performance_stats()
            self.log(f"Database متصل ✅ | الجداول جاهزة", 'success')
            db.close()
        except Exception as e:
            self.log(f"Database فشل ❌ | {e}", 'error')

    def test_ml(self):
        """اختبار ML"""
        self.log("اختبار ML Model...", 'info')
        try:
            from ml_engine.ml_system import TradingMLModel
            ml = TradingMLModel()
            self.log("ML Model جاهز ✅", 'success')
        except Exception as e:
            self.log(f"ML فشل ❌ | {e}", 'error')

    def test_all(self):
        """اختبار كل شيء"""
        self.result_text.delete('1.0', 'end')
        self.log("=" * 50, 'info')
        self.log("🚀 بدء اختبار شامل...", 'info')
        self.log("=" * 50, 'info')

        self.test_python()
        self.test_libraries()
        self.test_binance()
        self.test_telegram()
        self.test_database()
        self.test_ml()

        self.log("=" * 50, 'info')
        self.log("✅ اكتمل الاختبار!", 'success')
        self.log("=" * 50, 'info')

    def run(self):
        """تشغيل النافذة"""
        self.root.mainloop()


if __name__ == "__main__":
    app = TestConnectionGUI()
    app.run()
