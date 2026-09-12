"""
═══════════════════════════════════════════════════════════════════
🖥️ Desktop Trading App - تطبيق سطح المكتب الكامل
═══════════════════════════════════════════════════════════════════
تطبيق GUI كامل بدون cmd - مثل أي برنامج Windows عادي
═══════════════════════════════════════════════════════════════════
"""

import sys
import os
import asyncio
import threading
import subprocess
from pathlib import Path
from datetime import datetime
from tkinter import ttk
import tkinter as tk
from tkinter import messagebox, scrolledtext, filedialog

sys.path.insert(0, str(Path(__file__).parent))


class TradingDesktopApp:
    """تطبيق سطح المكتب الرئيسي"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🚀 SMC/ICT Trading Bot")
        self.root.geometry("1100x750")
        self.root.configure(bg='#0a0a0a')

        # منع الإغلاق المفاجئ
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # الألوان
        self.colors = {
            'bg': '#0a0a0a',
            'bg2': '#1e1e1e',
            'bg3': '#2d2d2d',
            'fg': '#ffffff',
            'fg2': '#cccccc',
            'green': '#00ff88',
            'red': '#ff4444',
            'yellow': '#ffaa00',
            'blue': '#00aaff',
            'purple': '#aa00ff',
        }

        # الحالة
        self.bot_process = None
        self.dashboard_process = None
        self.is_running = False

        # بناء الواجهة
        self.setup_ui()

        # تحديث دوري
        self.update_status()

    def setup_ui(self):
        """بناء الواجهة الرئيسية"""
        # ══════ Header ══════
        header = tk.Frame(self.root, bg=self.colors['bg2'], height=80)
        header.pack(fill='x', padx=10, pady=10)
        header.pack_propagate(False)

        title = tk.Label(
            header,
            text="🚀 SMC/ICT Multi-Agent Trading Bot",
            font=("Arial", 22, "bold"),
            bg=self.colors['bg2'],
            fg=self.colors['green']
        )
        title.pack(side='left', padx=20, pady=20)

        self.status_label = tk.Label(
            header,
            text="● STOPPED",
            font=("Arial", 14, "bold"),
            bg=self.colors['bg2'],
            fg=self.colors['red']
        )
        self.status_label.pack(side='right', padx=20, pady=20)

        # ══════ Main Container ══════
        main_container = tk.Frame(self.root, bg=self.colors['bg'])
        main_container.pack(fill='both', expand=True, padx=10)

        # ══════ Left Panel (Controls) ══════
        left_panel = tk.Frame(main_container, bg=self.colors['bg2'], width=280)
        left_panel.pack(side='left', fill='y', padx=(0, 5))
        left_panel.pack_propagate(False)

        self.setup_left_panel(left_panel)

        # ══════ Right Panel (Tabs) ══════
        right_panel = tk.Frame(main_container, bg=self.colors['bg'])
        right_panel.pack(side='right', fill='both', expand=True)

        self.setup_right_panel(right_panel)

    def setup_left_panel(self, parent):
        """اللوحة اليسرى - أزرار التحكم"""
        # العنوان
        tk.Label(
            parent,
            text="⚙️ CONTROL PANEL",
            font=("Arial", 14, "bold"),
            bg=self.colors['bg2'],
            fg=self.colors['fg']
        ).pack(pady=15)

        # قسم: Bot Control
        self.create_section_label(parent, "🤖 BOT CONTROL")

        self.start_btn = self.create_button(
            parent, "🚀 START BOT", self.start_bot,
            bg=self.colors['green']
        )
        self.stop_btn = self.create_button(
            parent, "🛑 STOP BOT", self.stop_bot,
            bg=self.colors['red']
        )

        # قسم: Services
        self.create_section_label(parent, "📊 SERVICES")

        self.create_button(parent, "📊 Open Dashboard", self.open_dashboard)
        self.create_button(parent, "📓 Open Notebooks", self.open_notebooks)
        self.create_button(parent, "🧪 Test Connection", self.test_connection)

        # قسم: Settings
        self.create_section_label(parent, "⚙️ SETTINGS")

        self.create_button(parent, "📝 Edit .env", self.edit_env)
        self.create_button(parent, "📁 Open Project Folder", self.open_folder)
        self.create_button(parent, "📂 Open Logs Folder", self.open_logs)
        self.create_button(parent, "🔄 Restart Everything", self.restart_all)

        # قسم: Help
        self.create_section_label(parent, "❓ HELP")

        self.create_button(parent, "📖 Quick Guide", self.show_guide)
        self.create_button(parent, "🆘 Get Support", self.show_support)

    def setup_right_panel(self, parent):
        """اللوحة اليمنى - التبويبات"""
        # Notebook (Tabs)
        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill='both', expand=True)

        # Style for tabs
        style = ttk.Style()
        style.configure('TNotebook.Tab', padding=[20, 10], font=('Arial', 10, 'bold'))

        # ══════ Tab 1: Dashboard ══════
        tab_dashboard = tk.Frame(self.notebook, bg=self.colors['bg'])
        self.notebook.add(tab_dashboard, text='📊 Dashboard')
        self.setup_dashboard_tab(tab_dashboard)

        # ══════ Tab 2: Logs ══════
        tab_logs = tk.Frame(self.notebook, bg=self.colors['bg'])
        self.notebook.add(tab_logs, text='📜 Live Logs')
        self.setup_logs_tab(tab_logs)

        # ══════ Tab 3: Trades ══════
        tab_trades = tk.Frame(self.notebook, bg=self.colors['bg'])
        self.notebook.add(tab_trades, text='💼 Trades')
        self.setup_trades_tab(tab_trades)

        # ══════ Tab 4: ML Performance ══════
        tab_ml = tk.Frame(self.notebook, bg=self.colors['bg'])
        self.notebook.add(tab_ml, text='🧠 ML')
        self.setup_ml_tab(tab_ml)

        # ══════ Tab 5: Settings ══════
        tab_settings = tk.Frame(self.notebook, bg=self.colors['bg'])
        self.notebook.add(tab_settings, text='⚙️ Settings')
        self.setup_settings_tab(tab_settings)

    def setup_dashboard_tab(self, parent):
        """تاب الـ Dashboard"""
        # KPIs
        kpi_frame = tk.Frame(parent, bg=self.colors['bg'])
        kpi_frame.pack(fill='x', padx=20, pady=20)

        kpis = [
            ("💰 PnL", "$0.00", self.colors['green']),
            ("📊 Trades", "0", self.colors['blue']),
            ("🎯 Win Rate", "0%", self.colors['yellow']),
            ("🧠 ML Acc", "0%", self.colors['purple']),
            ("📉 Drawdown", "0%", self.colors['red']),
        ]

        for i, (label, value, color) in enumerate(kpis):
            card = tk.Frame(kpi_frame, bg=self.colors['bg2'], relief='flat', bd=2)
            card.grid(row=0, column=i, padx=5, sticky='nsew')
            kpi_frame.grid_columnconfigure(i, weight=1)

            tk.Label(
                card, text=label,
                font=("Arial", 10),
                bg=self.colors['bg2'],
                fg=self.colors['fg2']
            ).pack(pady=(10, 5))

            tk.Label(
                card, text=value,
                font=("Arial", 18, "bold"),
                bg=self.colors['bg2'],
                fg=color
            ).pack(pady=(0, 10))

        # معلومات إضافية
        info_frame = tk.Frame(parent, bg=self.colors['bg2'])
        info_frame.pack(fill='both', expand=True, padx=20, pady=10)

        info_text = """
        ┌─────────────────────────────────────────┐
        │  📊 Welcome to SMC/ICT Trading Bot      │
        │                                          │
        │  ✅ Click START BOT to begin             │
        │  ✅ Click Dashboard for live view        │
        │  ✅ All trades will appear in Trades tab │
        │  ✅ ML learns automatically              │
        │                                          │
        │  💡 Status: Ready                        │
        └─────────────────────────────────────────┘
        """

        tk.Label(
            info_frame,
            text=info_text,
            font=("Consolas", 11),
            bg=self.colors['bg2'],
            fg=self.colors['fg'],
            justify='left'
        ).pack(padx=20, pady=20, anchor='w')

    def setup_logs_tab(self, parent):
        """تاب اللوجات"""
        # شريط أدوات
        toolbar = tk.Frame(parent, bg=self.colors['bg2'])
        toolbar.pack(fill='x', padx=10, pady=10)

        tk.Button(
            toolbar, text="🔄 Refresh", command=self.refresh_logs,
            bg=self.colors['bg3'], fg=self.colors['fg'],
            font=("Arial", 10), padx=15, pady=5
        ).pack(side='left', padx=5)

        tk.Button(
            toolbar, text="🗑️ Clear", command=self.clear_logs,
            bg=self.colors['bg3'], fg=self.colors['fg'],
            font=("Arial", 10), padx=15, pady=5
        ).pack(side='left', padx=5)

        tk.Button(
            toolbar, text="💾 Save", command=self.save_logs,
            bg=self.colors['bg3'], fg=self.colors['fg'],
            font=("Arial", 10), padx=15, pady=5
        ).pack(side='left', padx=5)

        # منطقة اللوجات
        self.logs_text = scrolledtext.ScrolledText(
            parent,
            bg='#000000',
            fg=self.colors['fg'],
            font=("Consolas", 10),
            insertbackground=self.colors['fg']
        )
        self.logs_text.pack(fill='both', expand=True, padx=10, pady=10)

        self.add_log("✅ Logs viewer ready")
        self.add_log("⏳ Waiting for bot to start...")

    def setup_trades_tab(self, parent):
        """تاب الصفقات"""
        tk.Label(
            parent,
            text="💼 Trading History",
            font=("Arial", 16, "bold"),
            bg=self.colors['bg'],
            fg=self.colors['fg']
        ).pack(pady=20)

        # Treeview للصفقات
        columns = ('Time', 'Symbol', 'Side', 'Entry', 'Exit', 'PnL', 'Status')
        self.trades_tree = ttk.Treeview(parent, columns=columns, show='headings', height=20)

        for col in columns:
            self.trades_tree.heading(col, text=col)
            self.trades_tree.column(col, width=120, anchor='center')

        self.trades_tree.pack(fill='both', expand=True, padx=20, pady=10)

        tk.Label(
            parent,
            text="📊 Start the bot to see trades here",
            bg=self.colors['bg'],
            fg=self.colors['fg2'],
            font=("Arial", 11)
        ).pack(pady=10)

    def setup_ml_tab(self, parent):
        """تاب ML"""
        tk.Label(
            parent,
            text="🧠 Machine Learning Performance",
            font=("Arial", 16, "bold"),
            bg=self.colors['bg'],
            fg=self.colors['purple']
        ).pack(pady=20)

        ml_info = """
        ┌─────────────────────────────────────────┐
        │  🧠 ML Model Status                     │
        │                                          │
        │  Algorithm:    XGBoost                  │
        │  Status:       Training                 │
        │  Samples:      Learning continuously    │
        │  Auto-Retrain: Every 50 trades          │
        │                                          │
        │  📈 Metrics (after training):           │
        │  ─ Accuracy   ─ Precision              │
        │  ─ Recall     ─ F1 Score               │
        │  ─ Win Rate   ─ Profit Factor          │
        │                                          │
        │  🔄 The model learns from each trade    │
        │  📊 Performance improves over time      │
        └─────────────────────────────────────────┘
        """

        tk.Label(
            parent,
            text=ml_info,
            font=("Consolas", 11),
            bg=self.colors['bg2'],
            fg=self.colors['fg'],
            justify='left'
        ).pack(padx=30, pady=20, anchor='w')

    def setup_settings_tab(self, parent):
        """تاب الإعدادات"""
        tk.Label(
            parent,
            text="⚙️ Settings",
            font=("Arial", 16, "bold"),
            bg=self.colors['bg'],
            fg=self.colors['fg']
        ).pack(pady=20)

        settings_frame = tk.Frame(parent, bg=self.colors['bg2'])
        settings_frame.pack(fill='both', expand=True, padx=20, pady=10)

        # الإعدادات
        settings = [
            ("🎯 Risk per Trade:", "1.0%"),
            ("📊 Max Drawdown:", "10.0%"),
            ("📅 Max Daily Loss:", "3.0%"),
            ("🔢 Max Open Positions:", "3"),
            ("⏰ Primary Timeframe:", "4h"),
            ("📈 Higher Timeframe:", "1d"),
            ("💰 Min R:R Ratio:", "1:2.0"),
            ("⭐ Min Confluence:", "60"),
            ("🔌 Exchange:", "Binance Testnet"),
        ]

        for i, (label, value) in enumerate(settings):
            tk.Label(
                settings_frame,
                text=label,
                font=("Arial", 11),
                bg=self.colors['bg2'],
                fg=self.colors['fg2'],
                anchor='w'
            ).grid(row=i, column=0, sticky='w', padx=20, pady=8)

            tk.Label(
                settings_frame,
                text=value,
                font=("Arial", 11, "bold"),
                bg=self.colors['bg2'],
                fg=self.colors['green'],
                anchor='w'
            ).grid(row=i, column=1, sticky='w', padx=20, pady=8)

    # ══════ Helper Methods ══════

    def create_section_label(self, parent, text):
        """إنشاء عنوان قسم"""
        tk.Label(
            parent,
            text=text,
            font=("Arial", 10, "bold"),
            bg=self.colors['bg2'],
            fg=self.colors['yellow'],
            anchor='w'
        ).pack(fill='x', padx=15, pady=(15, 5))

    def create_button(self, parent, text, command, bg=None):
        """إنشاء زر"""
        bg = bg or self.colors['bg3']
        btn = tk.Button(
            parent,
            text=text,
            command=command,
            font=("Arial", 10, "bold"),
            bg=bg,
            fg=self.colors['fg'],
            relief='flat',
            cursor='hand2',
            padx=15,
            pady=8,
            activebackground=self.colors['blue']
        )
        btn.pack(fill='x', padx=15, pady=3)
        return btn

    # ══════ Bot Control ══════

    def start_bot(self):
        """تشغيل البوت"""
        try:
            if self.is_running:
                messagebox.showwarning("⚠️", "البوت يعمل بالفعل!")
                return

            self.add_log("🚀 Starting bot...")

            # تشغيل في thread منفصل
            self.bot_thread = threading.Thread(target=self._run_bot, daemon=True)
            self.bot_thread.start()

            self.is_running = True
            self.status_label.config(text="● RUNNING", fg=self.colors['green'])
            self.add_log("✅ Bot started!", 'success')

        except Exception as e:
            messagebox.showerror("❌ Error", f"Failed to start: {e}")
            self.add_log(f"❌ Error: {e}", 'error')

    def _run_bot(self):
        """تشغيل البوت في الخلفية"""
        try:
            # تشغيل main.py كـ subprocess
            script_path = Path(__file__).parent / "main.py"
            self.bot_process = subprocess.Popen(
                [sys.executable, str(script_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            # قراءة المخرجات
            while True:
                line = self.bot_process.stdout.readline()
                if not line:
                    break
                self.root.after(0, self.add_log, line.decode().strip())

        except Exception as e:
            self.root.after(0, self.add_log, f"❌ {e}", 'error')

    def stop_bot(self):
        """إيقاف البوت"""
        try:
            if self.bot_process:
                self.bot_process.terminate()
                self.bot_process = None

            self.is_running = False
            self.status_label.config(text="● STOPPED", fg=self.colors['red'])
            self.add_log("🛑 Bot stopped")

        except Exception as e:
            messagebox.showerror("❌", str(e))

    # ══════ Actions ══════

    def open_dashboard(self):
        """فتح Dashboard في المتصفح"""
        try:
            import webbrowser
            webbrowser.open("http://localhost:8501")
            self.add_log("📊 Opening dashboard...")

            # تشغيل Streamlit
            if not self.dashboard_process:
                script_path = Path(__file__).parent / "dashboard" / "streamlit_app" / "dashboard.py"
                self.dashboard_process = subprocess.Popen(
                    [sys.executable, "-m", "streamlit", "run", str(script_path)],
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                self.add_log("✅ Dashboard started!", 'success')
        except Exception as e:
            messagebox.showerror("❌", str(e))

    def open_notebooks(self):
        """فتح Jupyter"""
        try:
            subprocess.Popen(
                [sys.executable, "-m", "jupyter", "notebook"],
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            self.add_log("📓 Opening notebooks...")
        except Exception as e:
            messagebox.showerror("❌", str(e))

    def test_connection(self):
        """اختبار الاتصال"""
        try:
            subprocess.Popen(
                [sys.executable, "test_connection_gui.py"],
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            self.add_log("🧪 Opening test window...")
        except Exception as e:
            messagebox.showerror("❌", str(e))

    def edit_env(self):
        """تعديل .env"""
        try:
            env_path = Path(__file__).parent / ".env"
            if not env_path.exists():
                from shutil import copy
                copy(".env.example", ".env")
            os.startfile(str(env_path))
            self.add_log("📝 Opening .env...")
        except Exception as e:
            messagebox.showerror("❌", str(e))

    def open_folder(self):
        """فتح مجلد المشروع"""
        try:
            os.startfile(str(Path(__file__).parent))
        except Exception as e:
            messagebox.showerror("❌", str(e))

    def open_logs(self):
        """فتح مجلد اللوجات"""
        try:
            logs_path = Path(__file__).parent / "logs"
            logs_path.mkdir(exist_ok=True)
            os.startfile(str(logs_path))
        except Exception as e:
            messagebox.showerror("❌", str(e))

    def restart_all(self):
        """إعادة تشغيل كل شيء"""
        if messagebox.askyesno("🔄 Restart", "هل تريد إعادة تشغيل كل شيء؟"):
            self.stop_bot()
            self.add_log("🔄 Restarting...")
            self.root.after(3000, self.start_bot)

    def show_guide(self):
        """عرض الدليل السريع"""
        guide = """
═══════════════════════════════════════
📖 QUICK GUIDE - دليل سريع
═══════════════════════════════════════

1️⃣ SETUP (مرة واحدة فقط):
   • ضع مفاتيح Binance في .env
   • ضع مفاتيح Telegram في .env
   • شغّل START BOT

2️⃣ DAILY USE:
   • START BOT → يبدأ العمل
   • Dashboard → متابعة لحظية
   • Telegram → تنبيهات

3️⃣ IMPORTANT:
   • ابدأ بـ Testnet دائماً!
   • لا تستثمر أموالاً لا تتحمل خسارتها
   • راقب البوت يومياً

═══════════════════════════════════════
        """
        messagebox.showinfo("📖 Guide", guide)

    def show_support(self):
        """عرض الدعم"""
        support = """
═══════════════════════════════════════
🆘 SUPPORT - الدعم
═══════════════════════════════════════

📧 Issues: افتح Issue على GitHub
📖 Docs: راجع README.md
💬 Community: ICT Telegram Groups

═══════════════════════════════════════
        """
        messagebox.showinfo("🆘 Support", support)

    # ══════ Logs ══════

    def add_log(self, message, status='info'):
        """إضافة رسالة للوجات"""
        if hasattr(self, 'logs_text'):
            timestamp = datetime.now().strftime('%H:%M:%S')
            self.logs_text.insert('end', f"[{timestamp}] {message}\n")
            self.logs_text.see('end')

    def refresh_logs(self):
        """تحديث اللوجات"""
        self.add_log("🔄 Refreshing logs...")

    def clear_logs(self):
        """مسح اللوجات"""
        if hasattr(self, 'logs_text'):
            self.logs_text.delete('1.0', 'end')

    def save_logs(self):
        """حفظ اللوجات"""
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
            )
            if filename and hasattr(self, 'logs_text'):
                with open(filename, 'w') as f:
                    f.write(self.logs_text.get('1.0', 'end'))
                messagebox.showinfo("✅", f"Saved to {filename}")
        except Exception as e:
            messagebox.showerror("❌", str(e))

    # ══════ Status Update ══════

    def update_status(self):
        """تحديث الحالة كل 5 ثواني"""
        try:
            # التحقق من حالة البوت
            if self.bot_process and self.bot_process.poll() is not None:
                self.is_running = False
                self.status_label.config(text="● STOPPED", fg=self.colors['red'])
        except:
            pass

        # تحديث دوري
        self.root.after(5000, self.update_status)

    def on_closing(self):
        """عند الإغلاق"""
        if self.is_running:
            if messagebox.askyesno("⚠️", "البوت يعمل. هل تريد الإيقاف؟"):
                self.stop_bot()
                self.root.destroy()
        else:
            self.root.destroy()

    def run(self):
        """تشغيل التطبيق"""
        self.root.mainloop()


if __name__ == "__main__":
    print("🚀 Starting Desktop App...")
    app = TradingDesktopApp()
    app.run()
