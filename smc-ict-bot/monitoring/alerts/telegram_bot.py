"""
Telegram Alert System
=====================
Sends real-time notifications for:
- New trading signals
- Trade executions
- Stop loss / Take profit hits
- Daily performance summary
- System errors
"""

import requests
import asyncio
from typing import Dict, Optional
from datetime import datetime
from loguru import logger

from config.settings import CONFIG, MonitoringConfig
from strategies.liquidity_sweep_strategy import TradingSignal


class TelegramAlerter:
    """Telegram notification system"""

    def __init__(self, config: MonitoringConfig = None):
        self.config = config or CONFIG.monitoring
        self.enabled = self.config.telegram_enabled
        self.base_url = "https://api.telegram.org/bot"
        self._last_message_id = 0

        if self.enabled:
            if not self.config.telegram_bot_token or not self.config.telegram_chat_id:
                logger.warning("⚠️ Telegram credentials not set - alerts disabled")
                self.enabled = False
            else:
                logger.success("📱 Telegram alerts enabled")

    def _send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """Send a message to Telegram"""
        if not self.enabled:
            return False

        try:
            url = f"{self.base_url}{self.config.telegram_bot_token}/sendMessage"
            payload = {
                'chat_id': self.config.telegram_chat_id,
                'text': text,
                'parse_mode': parse_mode,
                'disable_web_page_preview': True,
            }

            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()

            return True

        except Exception as e:
            logger.error(f"Telegram send failed: {e}")
            return False

    def signal_alert(self, signal: TradingSignal):
        """Send new signal alert"""
        side_emoji = "🟢" if signal.side == 'long' else "🔴"

        message = f"""
{side_emoji} <b>NEW SMC/ICT SIGNAL</b>

📊 <b>Pair:</b> {signal.symbol}
📈 <b>Direction:</b> {signal.side.upper()}
⏰ <b>Timeframe:</b> {signal.timeframe}
⭐ <b>Confluence:</b> {signal.confluence_score}/100
💎 <b>R:R:</b> 1:{signal.risk_reward:.2f}

💰 <b>Entry:</b> {signal.entry_price:.4f}
🛑 <b>Stop Loss:</b> {signal.stop_loss:.4f}
🎯 <b>Take Profit:</b> {signal.take_profit:.4f}

📝 <b>Reasons:</b>
{chr(10).join('  • ' + r for r in signal.reasons[:5])}

🕐 {signal.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
"""
        self._send_message(message)

    def trade_executed(self, trade_data: Dict):
        """Send trade execution alert"""
        side_emoji = "✅" if trade_data['side'] == 'long' else "✅"

        message = f"""
{side_emoji} <b>TRADE EXECUTED</b>

📊 <b>Pair:</b> {trade_data['symbol']}
📈 <b>Side:</b> {trade_data['side'].upper()}
💰 <b>Entry:</b> {trade_data['entry_price']:.4f}
📦 <b>Size:</b> {trade_data['amount']}
🛑 <b>SL:</b> {trade_data['stop_loss']:.4f}
🎯 <b>TP:</b> {trade_data['take_profit']:.4f}

🆔 <b>Trade ID:</b> {trade_data['id']}
"""
        self._send_message(message)

    def trade_closed(self, trade_data: Dict):
        """Send trade closure alert"""
        is_win = trade_data['pnl_pct'] > 0
        emoji = "🎉" if is_win else "😔"
        result = "WIN" if is_win else "LOSS"

        message = f"""
{emoji} <b>TRADE CLOSED - {result}</b>

📊 <b>Pair:</b> {trade_data['symbol']}
📈 <b>Side:</b> {trade_data['side'].upper()}
💵 <b>Exit Price:</b> {trade_data['exit_price']:.4f}

💰 <b>PnL:</b> {trade_data['pnl']:.2f} USDT ({trade_data['pnl_pct']:+.2f}%)
📝 <b>Reason:</b> {trade_data['reason']}

🕐 <b>Duration:</b> {trade_data.get('duration', 'N/A')}
"""
        self._send_message(message)

    def daily_report(self, stats: Dict):
        """Send daily performance report"""
        message = f"""
📊 <b>DAILY PERFORMANCE REPORT</b>
📅 {datetime.now().strftime('%Y-%m-%d')}

<b>Trading Activity:</b>
• Total Trades: {stats.get('total_trades', 0)}
• Wins: {stats.get('wins', 0)} ✅
• Losses: {stats.get('losses', 0)} ❌
• Win Rate: {stats.get('win_rate', 0):.1f}%

<b>P&L:</b>
• Total: {stats.get('total_pnl', 0):+.2f} USDT
• Profit Factor: {stats.get('profit_factor', 0):.2f}
• Avg Win: {stats.get('avg_win', 0):+.2f}%
• Avg Loss: {stats.get('avg_loss', 0):.2f}%

<b>Risk Metrics:</b>
• Max Drawdown: {stats.get('max_drawdown', 0):.2f}%
• Sharpe Ratio: {stats.get('sharpe_ratio', 0):.2f}
• Open Positions: {stats.get('open_trades', 0)}
"""
        self._send_message(message)

    def error_alert(self, error_msg: str, context: str = ""):
        """Send error alert"""
        message = f"""
🚨 <b>ERROR ALERT</b>

<b>Context:</b> {context}
<b>Error:</b> <code>{error_msg}</code>

🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        self._send_message(message)

    def system_status(self, status: str, details: Dict = None):
        """Send system status update"""
        emoji_map = {
            'start': '🚀',
            'stop': '🛑',
            'pause': '⏸️',
            'resume': '▶️',
        }

        emoji = emoji_map.get(status, 'ℹ️')

        details_text = ""
        if details:
            details_text = "\n".join(f"• <b>{k}:</b> {v}" for k, v in details.items())

        message = f"""
{emoji} <b>SYSTEM {status.upper()}</b>

{details_text}

🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        self._send_message(message)

    def test_connection(self) -> bool:
        """Test Telegram connection"""
        return self._send_message("🧪 Test message - SMC/ICT Bot is connected!")
