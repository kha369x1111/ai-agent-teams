"""
═══════════════════════════════════════════════════════════════════
🚀 Main Application - Complete Integration
═══════════════════════════════════════════════════════════════════
النقطة الرئيسية التي تدمج كل المكونات:
- Multi-Agent System
- ML Engine
- Database (PostgreSQL + Redis)
- WebSocket
- Multi-Exchange
- Streamlit Dashboard
- Celery Tasks
═══════════════════════════════════════════════════════════════════
"""

import asyncio
import signal
import sys
from pathlib import Path
from contextlib import asynccontextmanager
from datetime import datetime
from dotenv import load_dotenv
from loguru import logger

# إضافة المسار
sys.path.insert(0, str(Path(__file__).parent))

# Load environment
load_dotenv()

# استيراد المكونات
from agents.orchestrator.orchestrator import TradingOrchestrator
from ml_engine.ml_system import TradingMLModel
from ml_engine.database.database_manager import DatabaseManager
from websocket.websocket_manager import WebSocketManager
from multi_exchange.multi_exchange_manager import MultiExchangeManager, ExchangeCredentials, ExchangeType
from monitoring.alerts.telegram_bot import TelegramAlerter


class CompleteTradingSystem:
    """النظام الكامل المتكامل"""

    def __init__(self):
        logger.info("=" * 70)
        logger.info("🚀 INITIALIZING COMPLETE TRADING SYSTEM")
        logger.info("=" * 70)

        # 1. Database
        self.db = DatabaseManager()

        # 2. ML Engine
        self.ml_model = TradingMLModel()

        # 3. Multi-Exchange
        self.exchange_manager = MultiExchangeManager()

        # 4. WebSocket
        self.ws_manager = WebSocketManager()

        # 5. Multi-Agent Orchestrator
        self.orchestrator = None

        # 6. Alerts
        self.alerter = TelegramAlerter()

        self.is_running = False

    async def initialize(self):
        """تهيئة كل المكونات"""
        try:
            logger.info("🔧 Initializing components...")

            # 1. إعداد المنصات
            await self._setup_exchanges()

            # 2. إعداد Orchestrator مع كل المكونات
            self.orchestrator = TradingOrchestrator({
                'symbols': ['BTC/USDT', 'ETH/USDT'],
                'analysis_interval': 3600,
                'ml_model': self.ml_model,
                'db': self.db,
                'exchange_manager': self.exchange_manager,
                'ws_manager': self.ws_manager,
            })

            # 3. اتصال WebSocket
            await self.ws_manager.connect_binance(['BTCUSDT', 'ETHUSDT'])

            logger.success("✅ All components initialized")

        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            raise

    async def _setup_exchanges(self):
        """إعداد المنصات"""
        try:
            # Binance
            if os.getenv('BINANCE_API_KEY'):
                await self.exchange_manager.add_exchange(
                    ExchangeCredentials(
                        exchange_type=ExchangeType.BINANCE,
                        api_key=os.getenv('BINANCE_API_KEY'),
                        api_secret=os.getenv('BINANCE_API_SECRET'),
                        testnet=True,
                    )
                )

            # Bybit
            if os.getenv('BYBIT_API_KEY'):
                await self.exchange_manager.add_exchange(
                    ExchangeCredentials(
                        exchange_type=ExchangeType.BYBIT,
                        api_key=os.getenv('BYBIT_API_KEY'),
                        api_secret=os.getenv('BYBIT_API_SECRET'),
                        testnet=True,
                    )
                )

            # OKX
            if os.getenv('OKX_API_KEY'):
                await self.exchange_manager.add_exchange(
                    ExchangeCredentials(
                        exchange_type=ExchangeType.OKX,
                        api_key=os.getenv('OKX_API_KEY'),
                        api_secret=os.getenv('OKX_API_SECRET'),
                        passphrase=os.getenv('OKX_PASSPHRASE'),
                        testnet=True,
                    )
                )

        except Exception as e:
            logger.error(f"Exchange setup failed: {e}")

    async def start(self):
        """بدء النظام"""
        try:
            self.is_running = True

            # إشعار البدء
            self.alerter.system_status('start', {
                'System': 'Complete Trading System v2.0',
                'Components': '6 Agents + ML + DB + WebSocket + Multi-Exchange',
            })

            # بدء Orchestrator
            await self.orchestrator.start()

        except KeyboardInterrupt:
            await self.stop()
        except Exception as e:
            logger.error(f"System error: {e}")
            await self.stop()

    async def stop(self):
        """إيقاف النظام"""
        logger.info("🛑 Stopping complete system...")
        self.is_running = False

        # إيقاف المكونات
        if self.orchestrator:
            await self.orchestrator.stop()

        await self.ws_manager.stop()
        await self.exchange_manager.close_all()
        self.db.close()

        logger.success("✅ System stopped cleanly")


# ══════════════ نقطة الدخول ══════════════

async def main():
    system = CompleteTradingSystem()

    # Signal handlers
    def shutdown_handler(sig, frame):
        asyncio.create_task(system.stop())

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    await system.initialize()
    await system.start()


if __name__ == "__main__":
    import os
    asyncio.run(main())
