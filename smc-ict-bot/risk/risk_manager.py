"""
Risk Management System
======================
Comprehensive risk management with:
- Position sizing
- Daily loss limits
- Drawdown protection
- Correlation management
- Trade tracking
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from loguru import logger
import json
import os

from core.data.binance_connector import BinanceConnector
from strategies.liquidity_sweep_strategy import TradingSignal


@dataclass
class Trade:
    """Individual trade record"""
    id: str
    symbol: str
    side: str
    entry_price: float
    exit_price: Optional[float] = None
    stop_loss: float = 0
    take_profit: float = 0
    amount: float = 0
    entry_time: datetime = None
    exit_time: Optional[datetime] = None
    pnl: float = 0
    pnl_pct: float = 0
    status: str = 'open'    # 'open', 'closed', 'stopped', 'target'
    reason: str = ''


@dataclass
class DailyStats:
    """Daily trading statistics"""
    date: str
    trades: int = 0
    wins: int = 0
    losses: int = 0
    pnl: float = 0
    pnl_pct: float = 0


class RiskManager:
    """Professional Risk Management System"""

    def __init__(self, config: Dict, connector: BinanceConnector):
        self.config = config
        self.connector = connector
        self.trades: List[Trade] = []
        self.daily_stats: Dict[str, DailyStats] = {}
        self.initial_balance = 0
        self.peak_balance = 0
        self.trades_file = "data/trades_history.json"
        self._load_history()

        logger.info("🛡️ Risk Manager initialized")

    def _load_history(self):
        """Load trade history from file"""
        if os.path.exists(self.trades_file):
            try:
                with open(self.trades_file, 'r') as f:
                    data = json.load(f)
                self.trades = [Trade(**t) for t in data.get('trades', [])]
                logger.info(f"📚 Loaded {len(self.trades)} historical trades")
            except Exception as e:
                logger.error(f"Failed to load trade history: {e}")

    def _save_history(self):
        """Save trade history to file"""
        os.makedirs(os.path.dirname(self.trades_file), exist_ok=True)
        try:
            data = {
                'trades': [self._trade_to_dict(t) for t in self.trades]
            }
            with open(self.trades_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save trade history: {e}")

    def _trade_to_dict(self, trade: Trade) -> Dict:
        """Convert trade to dict for JSON"""
        return {
            'id': trade.id,
            'symbol': trade.symbol,
            'side': trade.side,
            'entry_price': trade.entry_price,
            'exit_price': trade.exit_price,
            'stop_loss': trade.stop_loss,
            'take_profit': trade.take_profit,
            'amount': trade.amount,
            'entry_time': trade.entry_time.isoformat() if trade.entry_time else None,
            'exit_time': trade.exit_time.isoformat() if trade.exit_time else None,
            'pnl': trade.pnl,
            'pnl_pct': trade.pnl_pct,
            'status': trade.status,
            'reason': trade.reason,
        }

    def initialize(self):
        """Initialize balance tracking"""
        balance = self.connector.get_balance()
        usdt_balance = balance.get('total', {}).get('USDT', 0)
        self.initial_balance = usdt_balance
        self.peak_balance = usdt_balance
        logger.info(f"💰 Initial balance: {usdt_balance:.2f} USDT")

    def get_current_balance(self) -> float:
        """Get current USDT balance"""
        balance = self.connector.get_balance()
        return balance.get('total', {}).get('USDT', 0)

    def get_drawdown(self) -> float:
        """Calculate current drawdown percentage"""
        current = self.get_current_balance()
        if current > self.peak_balance:
            self.peak_balance = current

        if self.peak_balance == 0:
            return 0

        drawdown = ((self.peak_balance - current) / self.peak_balance) * 100
        return drawdown

    def can_take_trade(self, signal: TradingSignal) -> Tuple[bool, str]:
        """
        Check if a new trade can be taken

        Returns:
            (allowed, reason)
        """
        # 1. Check max drawdown
        drawdown = self.get_drawdown()
        if drawdown >= self.config.get('max_drawdown_pct', 10.0):
            return False, f"Max drawdown reached: {drawdown:.2f}%"

        # 2. Check daily loss limit
        daily_pnl = self.get_daily_pnl()
        daily_loss_limit = self.config.get('max_daily_loss_pct', 3.0)
        if daily_pnl <= -daily_loss_limit:
            return False, f"Daily loss limit reached: {daily_pnl:.2f}%"

        # 3. Check max daily trades
        today = datetime.now().strftime('%Y-%m-%d')
        today_stats = self.daily_stats.get(today, DailyStats(date=today))
        if today_stats.trades >= self.config.get('max_daily_trades', 5):
            return False, f"Max daily trades reached: {today_stats.trades}"

        # 4. Check consecutive losses
        consecutive_losses = self._get_consecutive_losses()
        if consecutive_losses >= self.config.get('max_consecutive_losses', 3):
            return False, f"Consecutive losses: {consecutive_losses}"

        # 5. Check existing position on same symbol
        if self._has_position(signal.symbol):
            return False, f"Already have position on {signal.symbol}"

        # 6. Check correlation (basic check)
        open_count = self._count_open_positions()
        if open_count >= 3:
            return False, f"Max open positions: {open_count}"

        return True, "Trade allowed"

    def calculate_position_size(self, signal: TradingSignal) -> float:
        """
        Calculate optimal position size

        Args:
            signal: Trading signal

        Returns:
            Position size in base currency
        """
        try:
            balance = self.get_current_balance()
            if balance <= 0:
                logger.error("No balance available")
                return 0

            # Risk amount based on risk percentage
            risk_pct = self.config.get('risk_per_trade_pct', 1.0)
            risk_amount = balance * (risk_pct / 100)

            # Calculate price distance to stop
            price_diff = abs(signal.entry_price - signal.stop_loss)

            if price_diff <= 0:
                logger.error("Invalid stop loss")
                return 0

            # Basic position size
            position_size = risk_amount / price_diff

            # Apply max position size limit
            max_position_value = balance * (self.config.get('max_position_size_pct', 5.0) / 100)
            max_size_by_capital = max_position_value / signal.entry_price

            position_size = min(position_size, max_size_by_capital)

            # Apply leverage consideration (for futures)
            leverage = signal.__dict__.get('leverage', 1)
            position_size *= leverage

            # Round to exchange precision
            market = self.connector.exchange.market(signal.symbol)
            precision = market.get('precision', {}).get('amount', 8)
            position_size = round(position_size, precision)

            # Check minimum
            min_amount = market.get('limits', {}).get('amount', {}).get('min', 0)
            if position_size < min_amount:
                logger.warning(f"Position size {position_size} below minimum {min_amount}")
                return 0

            logger.info(
                f"💰 Position size: {position_size} {signal.symbol.split('/')[0]} "
                f"(Risk: {risk_amount:.2f} USDT)"
            )

            return position_size

        except Exception as e:
            logger.error(f"Position sizing failed: {e}")
            return 0

    def record_trade(self, trade: Trade):
        """Record a new trade"""
        self.trades.append(trade)
        self._save_history()
        logger.info(f"📝 Trade recorded: {trade.symbol} {trade.side}")

    def close_trade(self, trade_id: str, exit_price: float, reason: str):
        """Close a trade and calculate PnL"""
        for trade in self.trades:
            if trade.id == trade_id and trade.status == 'open':
                trade.exit_price = exit_price
                trade.exit_time = datetime.now()

                # Calculate PnL
                if trade.side == 'long':
                    pnl_pct = ((exit_price - trade.entry_price) / trade.entry_price) * 100
                else:
                    pnl_pct = ((trade.entry_price - exit_price) / trade.entry_price) * 100

                trade.pnl_pct = pnl_pct
                trade.pnl = trade.amount * trade.entry_price * (pnl_pct / 100)
                trade.status = 'closed'
                trade.reason = reason

                # Update daily stats
                today = datetime.now().strftime('%Y-%m-%d')
                if today not in self.daily_stats:
                    self.daily_stats[today] = DailyStats(date=today)

                stats = self.daily_stats[today]
                stats.trades += 1
                stats.pnl += trade.pnl
                stats.pnl_pct += pnl_pct

                if pnl_pct > 0:
                    stats.wins += 1
                    logger.success(f"✅ Trade WIN: +{pnl_pct:.2f}% (+{trade.pnl:.2f} USDT)")
                else:
                    stats.losses += 1
                    logger.warning(f"❌ Trade LOSS: {pnl_pct:.2f}% ({trade.pnl:.2f} USDT)")

                self._save_history()
                return trade

        return None

    def update_open_trades(self):
        """Update open trades - check SL/TP"""
        positions = self.connector.get_positions()

        for position in positions:
            symbol = position['symbol']
            current_price = float(position.get('markPrice', 0))

            # Find corresponding trade
            for trade in self.trades:
                if trade.symbol == symbol and trade.status == 'open':
                    # Check stop loss
                    if trade.side == 'long' and current_price <= trade.stop_loss:
                        self.close_trade(
                            trade.id,
                            current_price,
                            'Stop Loss Hit'
                        )
                    elif trade.side == 'short' and current_price >= trade.stop_loss:
                        self.close_trade(
                            trade.id,
                            current_price,
                            'Stop Loss Hit'
                        )

                    # Check take profit
                    elif trade.side == 'long' and current_price >= trade.take_profit:
                        self.close_trade(
                            trade.id,
                            current_price,
                            'Take Profit Hit'
                        )
                    elif trade.side == 'short' and current_price <= trade.take_profit:
                        self.close_trade(
                            trade.id,
                            current_price,
                            'Take Profit Hit'
                        )

    def get_daily_pnl(self) -> float:
        """Get today's PnL percentage"""
        today = datetime.now().strftime('%Y-%m-%d')
        stats = self.daily_stats.get(today, DailyStats(date=today))

        # Also include unrealized PnL from open positions
        unrealized = 0
        balance = self.get_current_balance()
        if balance > 0:
            unrealized = (stats.pnl / balance) * 100

        return unrealized

    def _get_consecutive_losses(self) -> int:
        """Count consecutive losses"""
        count = 0
        for trade in reversed(self.trades):
            if trade.status != 'closed':
                continue
            if trade.pnl_pct < 0:
                count += 1
            else:
                break
        return count

    def _has_position(self, symbol: str) -> bool:
        """Check if position exists for symbol"""
        return any(t.symbol == symbol and t.status == 'open' for t in self.trades)

    def _count_open_positions(self) -> int:
        """Count total open positions"""
        return sum(1 for t in self.trades if t.status == 'open')

    def get_performance_report(self) -> Dict:
        """Generate performance report"""
        closed_trades = [t for t in self.trades if t.status == 'closed']

        if not closed_trades:
            return {
                'total_trades': 0,
                'message': 'No closed trades yet'
            }

        wins = [t for t in closed_trades if t.pnl_pct > 0]
        losses = [t for t in closed_trades if t.pnl_pct <= 0]

        total_pnl = sum(t.pnl for t in closed_trades)
        win_rate = (len(wins) / len(closed_trades)) * 100

        avg_win = np.mean([t.pnl_pct for t in wins]) if wins else 0
        avg_loss = np.mean([t.pnl_pct for t in losses]) if losses else 0

        profit_factor = (
            abs(sum(t.pnl for t in wins)) / abs(sum(t.pnl for t in losses))
            if losses and sum(t.pnl for t in losses) != 0
            else float('inf')
        )

        return {
            'total_trades': len(closed_trades),
            'open_trades': self._count_open_positions(),
            'wins': len(wins),
            'losses': len(losses),
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'max_drawdown': self.get_drawdown(),
            'consecutive_losses': self._get_consecutive_losses(),
            'sharpe_ratio': self._calculate_sharpe(closed_trades),
        }

    def _calculate_sharpe(self, trades: List[Trade]) -> float:
        """Calculate Sharpe ratio"""
        if len(trades) < 2:
            return 0

        returns = [t.pnl_pct for t in trades]
        if np.std(returns) == 0:
            return 0

        sharpe = (np.mean(returns) / np.std(returns)) * np.sqrt(252)
        return sharpe
