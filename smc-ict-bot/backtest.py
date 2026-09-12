"""
Backtesting Engine
==================
Test strategy on historical data before going live.
"""

import pandas as pd
import numpy as np
from typing import Dict, List
from datetime import datetime, timedelta
from loguru import logger
import matplotlib.pyplot as plt
from dataclasses import dataclass

from core.analysis.smc_detector import SMCDetector


@dataclass
class BacktestResult:
    """Backtest results"""
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    total_pnl_pct: float
    max_drawdown: float
    sharpe_ratio: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    avg_rr: float
    equity_curve: pd.Series
    trades: List[Dict]


class Backtester:
    """Professional backtesting engine"""

    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.detector = SMCDetector(self.config)
        self.initial_capital = self.config.get('initial_capital', 10000)
        self.commission = self.config.get('commission', 0.04)  # 0.04% Binance futures

        logger.info(f"📊 Backtester initialized with {self.initial_capital} USDT")

    def run(
        self,
        df: pd.DataFrame,
        signals: List[Dict],
        symbol: str = "BTC/USDT"
    ) -> BacktestResult:
        """
        Run backtest with signals

        Args:
            df: OHLCV dataframe
            signals: List of signal dicts with entry/SL/TP
            symbol: Trading pair
        """
        capital = self.initial_capital
        equity = []
        trades = []
        peak = capital
        max_dd = 0

        for signal in signals:
            entry = signal['entry_price']
            sl = signal['stop_loss']
            tp = signal['take_profit']
            side = signal['side']

            # Calculate position size (risk 1% per trade)
            risk_pct = self.config.get('risk_per_trade_pct', 1.0)
            risk_amount = capital * (risk_pct / 100)
            position_size = risk_amount / abs(entry - sl)

            # Find exit in future data
            exit_price, exit_idx, result = self._find_exit(
                df, signal, entry, sl, tp
            )

            if exit_price is None:
                continue

            # Calculate PnL
            if side == 'long':
                pnl_pct = ((exit_price - entry) / entry) * 100
            else:
                pnl_pct = ((entry - exit_price) / entry) * 100

            # Apply commission
            pnl_pct -= self.commission * 2  # Entry + Exit
            pnl = position_size * entry * (pnl_pct / 100)

            capital += pnl

            # Track equity
            equity.append({
                'time': df.index[exit_idx],
                'capital': capital,
            })

            # Update peak and drawdown
            if capital > peak:
                peak = capital
            dd = ((peak - capital) / peak) * 100
            if dd > max_dd:
                max_dd = dd

            # Record trade
            trades.append({
                'entry_time': signal['timestamp'],
                'exit_time': df.index[exit_idx],
                'side': side,
                'entry_price': entry,
                'exit_price': exit_price,
                'pnl': pnl,
                'pnl_pct': pnl_pct,
                'result': result,
                'duration': df.index[exit_idx] - signal['timestamp'],
            })

        # Calculate results
        result = self._calculate_results(trades, equity, max_dd)

        logger.info("=" * 50)
        logger.info(f"📊 Backtest Results for {symbol}")
        logger.info(f"Total Trades: {result.total_trades}")
        logger.info(f"Win Rate: {result.win_rate:.2f}%")
        logger.info(f"Total PnL: {result.total_pnl:.2f} USDT ({result.total_pnl_pct:.2f}%)")
        logger.info(f"Max Drawdown: {result.max_drawdown:.2f}%")
        logger.info(f"Sharpe Ratio: {result.sharpe_ratio:.2f}")
        logger.info(f"Profit Factor: {result.profit_factor:.2f}")
        logger.info("=" * 50)

        return result

    def _find_exit(
        self,
        df: pd.DataFrame,
        signal: Dict,
        entry: float,
        sl: float,
        tp: float
    ) -> tuple:
        """Find exit point by iterating through future candles"""
        entry_idx = signal.get('candle_index', 0)
        side = signal['side']

        for i in range(entry_idx + 1, len(df)):
            candle = df.iloc[i]

            if side == 'long':
                if candle['low'] <= sl:
                    return sl, i, 'stop_loss'
                if candle['high'] >= tp:
                    return tp, i, 'take_profit'
            else:
                if candle['high'] >= sl:
                    return sl, i, 'stop_loss'
                if candle['low'] <= tp:
                    return tp, i, 'take_profit'

        # If still open at end
        last_close = df.iloc[-1]['close']
        return last_close, len(df) - 1, 'end_of_data'

    def _calculate_results(
        self,
        trades: List[Dict],
        equity: List[Dict],
        max_dd: float
    ) -> BacktestResult:
        """Calculate backtest metrics"""
        if not trades:
            return BacktestResult(
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate=0,
                total_pnl=0,
                total_pnl_pct=0,
                max_drawdown=0,
                sharpe_ratio=0,
                profit_factor=0,
                avg_win=0,
                avg_loss=0,
                avg_rr=0,
                equity_curve=pd.Series(),
                trades=[],
            )

        wins = [t for t in trades if t['pnl'] > 0]
        losses = [t for t in trades if t['pnl'] <= 0]

        total_pnl = sum(t['pnl'] for t in trades)
        total_pnl_pct = (total_pnl / self.initial_capital) * 100
        win_rate = (len(wins) / len(trades)) * 100

        avg_win = np.mean([t['pnl_pct'] for t in wins]) if wins else 0
        avg_loss = np.mean([t['pnl_pct'] for t in losses]) if losses else 0

        # Profit factor
        gross_profit = sum(t['pnl'] for t in wins)
        gross_loss = abs(sum(t['pnl'] for t in losses))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

        # Sharpe ratio
        returns = [t['pnl_pct'] for t in trades]
        if len(returns) > 1 and np.std(returns) > 0:
            sharpe = (np.mean(returns) / np.std(returns)) * np.sqrt(252)
        else:
            sharpe = 0

        # Equity curve
        equity_df = pd.DataFrame(equity).set_index('time')
        equity_curve = equity_df['capital'] if not equity_df.empty else pd.Series([self.initial_capital])

        # Average R:R
        rr_ratios = []
        for t in trades:
            if t.get('result') == 'take_profit':
                rr_ratios.append(2.0)  # Or actual R:R
            elif t.get('result') == 'stop_loss':
                rr_ratios.append(1.0)
        avg_rr = np.mean(rr_ratios) if rr_ratios else 0

        return BacktestResult(
            total_trades=len(trades),
            winning_trades=len(wins),
            losing_trades=len(losses),
            win_rate=win_rate,
            total_pnl=total_pnl,
            total_pnl_pct=total_pnl_pct,
            max_drawdown=max_dd,
            sharpe_ratio=sharpe,
            profit_factor=profit_factor,
            avg_win=avg_win,
            avg_loss=avg_loss,
            avg_rr=avg_rr,
            equity_curve=equity_curve,
            trades=trades,
        )

    def plot_results(self, result: BacktestResult, save_path: str = "backtest_results.png"):
        """Plot equity curve and drawdown"""
        fig, axes = plt.subplots(3, 1, figsize=(15, 10))

        # Equity curve
        axes[0].plot(result.equity_curve.index, result.equity_curve.values)
        axes[0].axhline(y=self.initial_capital, color='r', linestyle='--', alpha=0.5)
        axes[0].set_title('Equity Curve')
        axes[0].set_ylabel('Capital (USDT)')
        axes[0].grid(True, alpha=0.3)

        # Drawdown
        if not result.equity_curve.empty:
            running_max = result.equity_curve.cummax()
            drawdown = ((running_max - result.equity_curve) / running_max) * 100
            axes[1].fill_between(drawdown.index, 0, drawdown.values, color='red', alpha=0.3)
            axes[1].set_title('Drawdown %')
            axes[1].set_ylabel('Drawdown %')
            axes[1].grid(True, alpha=0.3)

        # Trade PnL
        if result.trades:
            pnls = [t['pnl'] for t in result.trades]
            colors = ['green' if p > 0 else 'red' for p in pnls]
            axes[2].bar(range(len(pnls)), pnls, color=colors, alpha=0.6)
            axes[2].set_title('Trade PnL')
            axes[2].set_xlabel('Trade #')
            axes[2].set_ylabel('PnL (USDT)')
            axes[2].grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig(save_path, dpi=100, bbox_inches='tight')
        logger.info(f"📊 Results plotted to {save_path}")
