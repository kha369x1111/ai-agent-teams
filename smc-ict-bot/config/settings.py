"""
SMC/ICT Trading Bot - Configuration Module
==========================================
Central configuration for all system components.
"""

import os
from dataclasses import dataclass, field
from typing import List, Dict
from enum import Enum


class TradingMode(Enum):
    """Trading execution modes"""
    LIVE = "live"           # Real money trading
    TESTNET = "testnet"     # Binance Testnet
    PAPER = "paper"         # Paper trading (simulated)
    BACKTEST = "backtest"   # Historical backtesting


class TimeFrame(Enum):
    """Supported timeframes"""
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"
    W1 = "1w"


@dataclass
class ExchangeConfig:
    """Binance exchange configuration"""
    api_key: str = os.getenv("BINANCE_API_KEY", "")
    api_secret: str = os.getenv("BINANCE_API_SECRET", "")
    testnet: bool = True
    recv_window: int = 5000
    enable_rate_limit: bool = True


@dataclass
class StrategyConfig:
    """SMC/ICT strategy parameters - Liquidity Sweep focus on HTF"""
    # Primary timeframe for analysis (HTF - 4H/Daily)
    primary_timeframe: str = "4h"

    # Higher timeframe for trend confirmation
    higher_timeframe: str = "1d"

    # Liquidity Sweep detection parameters
    swing_lookback: int = 20          # Bars to identify swing highs/lows
    sweep_threshold_pct: float = 0.5  # % beyond swing to confirm sweep
    min_sweep_rejection: float = 0.3  # Minimum wick rejection %

    # Order Block detection
    ob_lookback: int = 10
    ob_min_displacement: float = 0.7  # ATR multiplier

    # FVG detection
    fvg_min_size: float = 0.5  # Minimum FVG size in ATR

    # BOS/CHoCH confirmation
    structure_lookback: int = 50

    # Confluence requirements
    min_confluence_score: int = 60    # 0-100 score required

    # Entry parameters
    min_rr_ratio: float = 2.0         # Minimum Risk:Reward
    max_stop_atr: float = 2.5         # Stop loss in ATR multiples
    min_target_atr: float = 3.0       # Take profit in ATR multiples


@dataclass
class RiskConfig:
    """Risk management parameters"""
    # Position sizing
    risk_per_trade_pct: float = 1.0   # Risk 1% per trade
    max_position_size_pct: float = 5.0  # Max 5% of capital per position

    # Daily limits
    max_daily_loss_pct: float = 3.0
    max_daily_trades: int = 5

    # Drawdown protection
    max_drawdown_pct: float = 10.0    # Stop bot at 10% drawdown
    max_consecutive_losses: int = 3

    # Correlation
    max_correlated_positions: int = 2
    correlation_threshold: float = 0.7


@dataclass
class ExecutionConfig:
    """Trade execution parameters"""
    # Order settings
    order_type: str = "LIMIT"
    time_in_force: str = "GTC"
    post_only: bool = False

    # Slippage protection
    max_slippage_pct: float = 0.1

    # Retry logic
    max_retries: int = 3
    retry_delay_sec: int = 2

    # Async settings
    order_timeout_sec: int = 60


@dataclass
class MonitoringConfig:
    """Monitoring and alerting config"""
    # Telegram alerts
    telegram_enabled: bool = True
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")

    # Dashboard
    dashboard_enabled: bool = True
    dashboard_host: str = "0.0.0.0"
    dashboard_port: int = 8080

    # Logging
    log_level: str = "INFO"
    log_to_file: bool = True
    log_file: str = "logs/bot.log"


@dataclass
class TradingPairs:
    """Trading pairs configuration - HTF focus"""
    # Major pairs (high liquidity)
    primary_pairs: List[str] = field(default_factory=lambda: [
        "BTC/USDT",
        "ETH/USDT",
        "SOL/USDT",
        "BNB/USDT",
    ])

    # Watchlist for expansion
    watchlist: List[str] = field(default_factory=lambda: [
        "XRP/USDT",
        "ADA/USDT",
        "AVAX/USDT",
        "MATIC/USDT",
        "DOT/USDT",
        "LINK/USDT",
    ])


@dataclass
class BotConfig:
    """Master configuration"""
    mode: TradingMode = TradingMode.TESTNET
    exchange: ExchangeConfig = field(default_factory=ExchangeConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    pairs: TradingPairs = field(default_factory=TradingPairs)

    # Bot identity
    bot_name: str = "SMC-ICT Liquidity Bot"
    version: str = "1.0.0"


# Global config instance
CONFIG = BotConfig()


# Validation
def validate_config(config: BotConfig) -> bool:
    """Validate configuration before bot starts"""
    errors = []

    if config.mode == TradingMode.LIVE:
        if not config.exchange.api_key or not config.exchange.api_secret:
            errors.append("API keys required for live trading")

    if config.strategy.min_rr_ratio < 1.5:
        errors.append("Minimum R:R should be at least 1.5")

    if config.risk.risk_per_trade_pct > 5.0:
        errors.append("Risk per trade should not exceed 5%")

    if config.risk.max_drawdown_pct < 5.0:
        errors.append("Max drawdown should be at least 5%")

    if errors:
        for error in errors:
            print(f"❌ Config Error: {error}")
        return False

    return True
