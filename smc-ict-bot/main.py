"""
SMC/ICT Trading Bot - Main Entry Point
======================================
Orchestrates all components:
1. Data fetching
2. Strategy analysis
3. Risk management
4. Trade execution
5. Monitoring & alerts
"""

import asyncio
import signal
import sys
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from loguru import logger

from config.settings import CONFIG, TradingMode, validate_config
from core.data.binance_connector import BinanceConnector
from strategies.liquidity_sweep_strategy import LiquiditySweepStrategy, TradingSignal
from risk.risk_manager import RiskManager, Trade
from monitoring.alerts.telegram_bot import TelegramAlerter


class SMCICTBot:
    """Main SMC/ICT Trading Bot"""

    def __init__(self):
        # Validate config
        if not validate_config(CONFIG):
            sys.exit(1)

        # Initialize components
        logger.info("=" * 60)
        logger.info(f"🚀 Starting {CONFIG.bot_name} v{CONFIG.version}")
        logger.info(f"📊 Mode: {CONFIG.mode.value}")
        logger.info("=" * 60)

        # Data layer
        self.connector = BinanceConnector(CONFIG.exchange)

        # Strategy
        self.strategy = LiquiditySweepStrategy({
            'swing_lookback': CONFIG.strategy.swing_lookback,
            'sweep_threshold_pct': CONFIG.strategy.sweep_threshold_pct,
            'min_sweep_rejection': CONFIG.strategy.min_sweep_rejection,
            'min_confluence_score': CONFIG.strategy.min_confluence_score,
            'min_rr_ratio': CONFIG.strategy.min_rr_ratio,
        })

        # Risk management
        self.risk_manager = RiskManager({
            'risk_per_trade_pct': CONFIG.risk.risk_per_trade_pct,
            'max_position_size_pct': CONFIG.risk.max_position_size_pct,
            'max_daily_loss_pct': CONFIG.risk.max_daily_loss_pct,
            'max_daily_trades': CONFIG.risk.max_daily_trades,
            'max_drawdown_pct': CONFIG.risk.max_drawdown_pct,
            'max_consecutive_losses': CONFIG.risk.max_consecutive_losses,
        }, self.connector)

        # Alerts
        self.alerter = TelegramAlerter(CONFIG.monitoring)

        # State
        self.is_running = False
        self.last_analysis_time = None

        # Setup logging
        self._setup_logging()

    def _setup_logging(self):
        """Configure logging"""
        logger.add(
            "logs/bot_{time}.log",
            rotation="100 MB",
            retention="30 days",
            level=CONFIG.monitoring.log_level
        )

    async def start(self):
        """Start the bot"""
        logger.info("🎯 Bot starting up...")

        # Initialize risk manager
        self.risk_manager.initialize()

        # Send startup notification
        self.alerter.system_status('start', {
            'Mode': CONFIG.mode.value,
            'Pairs': ', '.join(CONFIG.pairs.primary_pairs),
            'Timeframe': CONFIG.strategy.primary_timeframe,
            'Risk/Trade': f"{CONFIG.risk.risk_per_trade_pct}%",
        })

        # Test telegram
        self.alerter.test_connection()

        # Setup signal handlers
        self._setup_signal_handlers()

        self.is_running = True
        logger.success("✅ Bot started successfully")

        # Main loop
        await self._main_loop()

    def _setup_signal_handlers(self):
        """Setup graceful shutdown"""
        def handler(sig, frame):
            logger.info("🛑 Shutdown signal received")
            self.stop()

        signal.signal(signal.SIGINT, handler)
        signal.signal(signal.SIGTERM, handler)

    def stop(self):
        """Stop the bot"""
        logger.info("🛑 Stopping bot...")
        self.is_running = False
        self.alerter.system_status('stop')
        sys.exit(0)

    async def _main_loop(self):
        """Main trading loop"""
        while self.is_running:
            try:
                # 1. Update open trades (check SL/TP)
                self.risk_manager.update_open_trades()

                # 2. Analyze each pair
                signals = await self._analyze_pairs()

                # 3. Process signals
                for signal in signals:
                    await self._process_signal(signal)

                # 4. Sleep before next cycle
                # For HTF (4H), analyze once per hour
                sleep_seconds = self._calculate_sleep_time()
                logger.info(f"⏳ Next analysis in {sleep_seconds}s")

                await asyncio.sleep(sleep_seconds)

            except KeyboardInterrupt:
                self.stop()
            except Exception as e:
                logger.error(f"❌ Main loop error: {e}")
                self.alerter.error_alert(str(e), "Main Loop")
                await asyncio.sleep(60)

    def _calculate_sleep_time(self) -> int:
        """Calculate sleep time based on timeframe"""
        tf_map = {
            '1m': 60,
            '5m': 300,
            '15m': 900,
            '30m': 1800,
            '1h': 3600,
            '4h': 14400,  # 4 hours
            '1d': 86400,
        }
        # For HTF strategy, check every hour (not waiting full 4h)
        return 3600  # 1 hour

    async def _analyze_pairs(self) -> List[TradingSignal]:
        """Analyze all configured pairs"""
        signals = []

        for symbol in CONFIG.pairs.primary_pairs:
            try:
                logger.info(f"🔍 Analyzing {symbol}...")

                signal = self.strategy.analyze_symbol(
                    symbol=symbol,
                    connector=self.connector,
                    primary_tf=CONFIG.strategy.primary_timeframe,
                    higher_tf=CONFIG.strategy.higher_timeframe,
                )

                if signal:
                    signals.append(signal)

                # Rate limit protection
                await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"Failed to analyze {symbol}: {e}")
                continue

        self.last_analysis_time = datetime.now()
        return signals

    async def _process_signal(self, signal: TradingSignal):
        """Process a trading signal"""
        try:
            logger.info(f"📊 Processing signal: {signal.symbol} {signal.side}")

            # 1. Risk check
            can_trade, reason = self.risk_manager.can_take_trade(signal)
            if not can_trade:
                logger.warning(f"🚫 Trade rejected: {reason}")
                return

            # 2. Calculate position size
            position_size = self.risk_manager.calculate_position_size(signal)
            if position_size <= 0:
                logger.warning("⚠️ Invalid position size")
                return

            # 3. Send signal alert
            self.alerter.signal_alert(signal)

            # 4. Execute trade
            order = self.connector.create_order(
                symbol=signal.symbol,
                side='buy' if signal.side == 'long' else 'sell',
                order_type='limit',
                amount=position_size,
                price=signal.entry_price,
                stop_loss=signal.stop_loss,
                take_profit=signal.take_profit,
            )

            if order:
                # 5. Record trade
                trade = Trade(
                    id=str(uuid.uuid4()),
                    symbol=signal.symbol,
                    side=signal.side,
                    entry_price=signal.entry_price,
                    stop_loss=signal.stop_loss,
                    take_profit=signal.take_profit,
                    amount=position_size,
                    entry_time=datetime.now(),
                    status='open',
                )

                self.risk_manager.record_trade(trade)

                self.alerter.trade_executed({
                    'id': trade.id,
                    'symbol': trade.symbol,
                    'side': trade.side,
                    'entry_price': trade.entry_price,
                    'amount': trade.amount,
                    'stop_loss': trade.stop_loss,
                    'take_profit': trade.take_profit,
                })

        except Exception as e:
            logger.error(f"❌ Signal processing failed: {e}")
            self.alerter.error_alert(str(e), "Signal Processing")

    def get_status(self) -> Dict:
        """Get bot status"""
        return {
            'running': self.is_running,
            'mode': CONFIG.mode.value,
            'last_analysis': self.last_analysis_time,
            'performance': self.risk_manager.get_performance_report(),
            'drawdown': self.risk_manager.get_drawdown(),
            'balance': self.risk_manager.get_current_balance(),
        }


async def main():
    """Main entry point"""
    bot = SMCICTBot()
    await bot.start()


if __name__ == "__main__":
    asyncio.run(main())
