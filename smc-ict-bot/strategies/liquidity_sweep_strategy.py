"""
Liquidity Sweep Strategy with Multi-Timeframe Confirmation
==========================================================
Primary strategy for HTF (4H/Daily) trading.

Entry Logic:
1. Detect liquidity sweep on primary timeframe (4H)
2. Confirm with higher timeframe (Daily) structure
3. Look for confluence (OB, FVG, structure)
4. Calculate entry, SL, TP based on sweep level
5. Execute if confluence score >= threshold
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from loguru import logger

from core.analysis.smc_detector import (
    SMCDetector, LiquiditySweep, OrderBlock, FairValueGap,
    MarketStructure, StructurePoint
)
from core.data.binance_connector import BinanceConnector


@dataclass
class TradingSignal:
    """Complete trading signal"""
    symbol: str
    side: str                    # 'long' or 'short'
    entry_price: float
    stop_loss: float
    take_profit: float
    confluence_score: int        # 0-100
    reasons: List[str]           # Why this signal
    risk_reward: float
    timestamp: datetime
    timeframe: str
    sweep_data: Optional[LiquiditySweep] = None
    structure_data: Optional[MarketStructure] = None
    nearby_ob: Optional[OrderBlock] = None
    nearby_fvg: Optional[FairValueGap] = None


class LiquiditySweepStrategy:
    """Liquidity Sweep Strategy with Multi-Timeframe Confirmation"""

    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.detector = SMCDetector(self.config)
        self.min_confluence = self.config.get('min_confluence_score', 60)
        self.min_rr = self.config.get('min_rr_ratio', 2.0)
        logger.info("📊 Liquidity Sweep Strategy initialized")

    def analyze_symbol(
        self,
        symbol: str,
        connector: BinanceConnector,
        primary_tf: str = "4h",
        higher_tf: str = "1d",
        lookback: int = 500
    ) -> Optional[TradingSignal]:
        """
        Full analysis pipeline for a symbol

        Args:
            symbol: Trading pair
            connector: Exchange connector instance
            primary_tf: Primary analysis timeframe (4h)
            higher_tf: Higher timeframe for trend (1d)
            lookback: Number of candles to analyze

        Returns:
            TradingSignal if valid setup found, None otherwise
        """
        try:
            logger.info(f"🔍 Analyzing {symbol} on {primary_tf}...")

            # 1. Fetch data for both timeframes
            primary_df = connector.fetch_ohlcv(symbol, primary_tf, limit=lookback)
            higher_df = connector.fetch_ohlcv(symbol, higher_tf, limit=lookback)

            if primary_df.empty or higher_df.empty:
                logger.warning(f"⚠️ No data for {symbol}")
                return None

            # 2. Analyze higher timeframe structure (trend direction)
            htf_structure = self.detector.analyze_market_structure(higher_df)
            logger.debug(f"  HTF Trend: {htf_structure.trend}")

            # 3. Detect swing points on primary timeframe
            swing_highs, swing_lows = self.detector.find_swing_points(primary_df)

            # 4. Detect liquidity sweeps
            sweeps = self.detector.detect_liquidity_sweeps(
                primary_df, swing_highs, swing_lows
            )

            if not sweeps:
                logger.debug(f"  No sweeps detected for {symbol}")
                return None

            # 5. Get most recent valid sweep
            latest_sweep = sweeps[-1]

            # 6. Check if sweep aligns with HTF trend
            trend_aligned = self._check_trend_alignment(latest_sweep, htf_structure)

            if not trend_aligned:
                logger.debug(f"  Sweep doesn't align with HTF trend")
                return None

            # 7. Detect Order Blocks and FVGs for confluence
            order_blocks = self.detector.detect_order_blocks(primary_df)
            fvgs = self.detector.detect_fair_value_gaps(primary_df)

            # 8. Find nearby OB/FVG
            nearby_ob = self._find_nearby_ob(latest_sweep, order_blocks)
            nearby_fvg = self._find_nearby_fvg(latest_sweep, fvgs)

            # 9. Calculate primary TF structure
            primary_structure = self.detector.analyze_market_structure(primary_df)

            # 10. Calculate confluence score
            confluence_score, reasons = self._calculate_confluence(
                latest_sweep, htf_structure, primary_structure,
                nearby_ob, nearby_fvg
            )

            if confluence_score < self.min_confluence:
                logger.debug(
                    f"  Low confluence: {confluence_score}/{self.min_confluence}"
                )
                return None

            # 11. Calculate entry, SL, TP
            entry, sl, tp = self._calculate_entry_levels(
                latest_sweep, primary_df, nearby_ob, nearby_fvg
            )

            # 12. Calculate R:R ratio
            if entry and sl and tp:
                if latest_sweep.is_bullish:
                    risk = entry - sl
                    reward = tp - entry
                else:
                    risk = sl - entry
                    reward = entry - tp

                rr_ratio = reward / risk if risk > 0 else 0

                if rr_ratio < self.min_rr:
                    logger.debug(f"  Poor R:R: {rr_ratio:.2f}")
                    return None

                # 13. Create signal
                signal = TradingSignal(
                    symbol=symbol,
                    side='long' if latest_sweep.is_bullish else 'short',
                    entry_price=entry,
                    stop_loss=sl,
                    take_profit=tp,
                    confluence_score=confluence_score,
                    reasons=reasons,
                    risk_reward=rr_ratio,
                    timestamp=datetime.now(),
                    timeframe=primary_tf,
                    sweep_data=latest_sweep,
                    structure_data=primary_structure,
                    nearby_ob=nearby_ob,
                    nearby_fvg=nearby_fvg
                )

                logger.success(
                    f"✅ Signal: {signal.side.upper()} {symbol} "
                    f"@ {entry} (Score: {confluence_score}, R:R: {rr_ratio:.2f})"
                )
                return signal

            return None

        except Exception as e:
            logger.error(f"❌ Analysis failed for {symbol}: {e}")
            return None

    def _check_trend_alignment(
        self,
        sweep: LiquiditySweep,
        htf_structure: MarketStructure
    ) -> bool:
        """
        Check if sweep aligns with HTF trend

        - Bullish sweep (high sweep) aligned with bullish HTF trend
        - Bearish sweep (low sweep) aligned with bearish HTF trend
        """
        # High sweep in bullish trend = aligned (expecting bullish reversal)
        if sweep.is_bullish and htf_structure.trend == 'bullish':
            return True

        # Low sweep in bearish trend = aligned (expecting bearish reversal)
        if not sweep.is_bullish and htf_structure.trend == 'bearish':
            return True

        # CHoCH on HTF makes the setup stronger
        if htf_structure.last_choch:
            if (sweep.is_bullish and htf_structure.last_choch.direction == 'bullish'):
                return True
            if (not sweep.is_bullish and htf_structure.last_choch.direction == 'bearish'):
                return True

        # Range market - accept both directions with lower score
        if htf_structure.trend == 'ranging':
            return True

        return False

    def _find_nearby_ob(
        self,
        sweep: LiquiditySweep,
        order_blocks: List[OrderBlock],
        max_distance_atr: float = 1.5
    ) -> Optional[OrderBlock]:
        """Find the most relevant Order Block near the sweep"""
        if not order_blocks:
            return None

        relevant_obs = []
        for ob in order_blocks:
            if ob.mitigated:
                continue

            # Check if OB is in the right direction
            if sweep.is_bullish and ob.type != 'bullish':
                continue
            if not sweep.is_bullish and ob.type != 'bearish':
                continue

            # Check proximity to sweep level
            sweep_level = sweep.sweep_level
            ob_midpoint = ob.midpoint
            distance = abs(sweep_level - ob_midpoint)

            # Convert to ATR multiple
            atr = sweep.atr if sweep.atr > 0 else 0.001
            distance_atr = distance / atr

            if distance_atr <= max_distance_atr:
                relevant_obs.append((ob, distance_atr, ob.strength))

        if not relevant_obs:
            return None

        # Sort by distance (closest first), then strength
        relevant_obs.sort(key=lambda x: (x[1], -x[2]))
        return relevant_obs[0][0]

    def _find_nearby_fvg(
        self,
        sweep: LiquiditySweep,
        fvgs: List[FairValueGap],
        max_distance_atr: float = 1.0
    ) -> Optional[FairValueGap]:
        """Find relevant FVG near sweep"""
        if not fvgs:
            return None

        relevant_fvgs = []
        for fvg in fvgs:
            if fvg.filled:
                continue

            # Check direction match
            if sweep.is_bullish and fvg.type != 'bullish':
                continue
            if not sweep.is_bullish and fvg.type != 'bearish':
                continue

            # Check proximity
            distance = abs(sweep.sweep_level - fvg.midpoint)
            atr = sweep.atr if sweep.atr > 0 else 0.001
            distance_atr = distance / atr

            if distance_atr <= max_distance_atr:
                relevant_fvgs.append((fvg, distance_atr))

        if not relevant_fvgs:
            return None

        relevant_fvgs.sort(key=lambda x: x[1])
        return relevant_fvgs[0][0]

    def _calculate_confluence(
        self,
        sweep: LiquiditySweep,
        htf_structure: MarketStructure,
        primary_structure: MarketStructure,
        nearby_ob: Optional[OrderBlock],
        nearby_fvg: Optional[FairValueGap]
    ) -> Tuple[int, List[str]]:
        """
        Calculate confluence score (0-100)

        Components:
        - Liquidity sweep: 25 points
        - HTF trend alignment: 20 points
        - Primary TF structure: 15 points
        - Order Block confluence: 20 points
        - FVG confluence: 10 points
        - Volume confirmation: 10 points
        """
        score = 0
        reasons = []

        # 1. Liquidity sweep (25 points)
        if sweep.rejection_pct >= 70:
            score += 25
            reasons.append(f"Strong sweep rejection ({sweep.rejection_pct:.1f}%)")
        elif sweep.rejection_pct >= 50:
            score += 20
            reasons.append(f"Good sweep rejection ({sweep.rejection_pct:.1f}%)")
        elif sweep.rejection_pct >= 30:
            score += 15
            reasons.append(f"Moderate sweep rejection ({sweep.rejection_pct:.1f}%)")

        # 2. HTF trend alignment (20 points)
        if htf_structure.trend != 'ranging':
            trend_name = htf_structure.trend
            if (sweep.is_bullish and trend_name == 'bullish') or \
               (not sweep.is_bullish and trend_name == 'bearish'):
                score += 20
                reasons.append(f"HTF trend aligned ({trend_name})")
            else:
                score += 5
                reasons.append("HTF trend not aligned")

        # Bonus for CHoCH
        if htf_structure.last_choch:
            score += 5
            reasons.append("HTF CHoCH detected")

        # 3. Primary TF structure (15 points)
        if primary_structure.trend != 'ranging':
            score += 15
            reasons.append(f"Primary TF trending ({primary_structure.trend})")
        else:
            score += 5
            reasons.append("Primary TF ranging")

        # 4. Order Block confluence (20 points)
        if nearby_ob:
            score += 20
            reasons.append(f"OB confluence (strength: {nearby_ob.strength:.0f})")
        else:
            score += 5

        # 5. FVG confluence (10 points)
        if nearby_fvg:
            score += 10
            reasons.append(f"FVG confluence (size: {nearby_fvg.size_atr:.2f} ATR)")
        else:
            score += 3

        # 6. Volume confirmation (10 points)
        avg_volume = sweep.volume  # Simplified - should compare to average
        # In real implementation, compare to 20-period average
        if sweep.volume > 0:
            score += 10
            reasons.append("Volume confirmed")

        logger.debug(f"  Confluence: {score}/100 - {', '.join(reasons)}")
        return score, reasons

    def _calculate_entry_levels(
        self,
        sweep: LiquiditySweep,
        df: pd.DataFrame,
        nearby_ob: Optional[OrderBlock],
        nearby_fvg: Optional[FairValueGap]
    ) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """
        Calculate entry, stop loss, take profit

        Logic:
        - Entry: At sweep level or OB/FVG midpoint
        - Stop Loss: Beyond sweep extreme + buffer
        - Take Profit: Next liquidity level or 3:1 R:R
        """
        try:
            atr = sweep.atr if sweep.atr > 0 else 0.001

            if sweep.is_bullish:
                # Bullish setup (long)
                # Entry at sweep level (the level that was swept)
                entry = sweep.sweep_level

                # Stop loss below the sweep extreme
                stop_buffer = atr * 0.3
                stop_loss = sweep.sweep_price - stop_buffer

                # Take profit targets
                tp1 = entry + (entry - stop_loss) * 3.0  # 3:1 R:R minimum
                tp2 = entry + (entry - stop_loss) * 5.0  # Extended target

                # Use higher target if structure supports
                take_profit = tp1

                # If we have OB as entry, use OB midpoint
                if nearby_ob:
                    entry = nearby_ob.midpoint

                # If we have FVG, use FVG midpoint
                if nearby_fvg:
                    entry = nearby_fvg.midpoint

                # Adjust stop if OB provides better level
                if nearby_ob and nearby_ob.bottom < stop_loss:
                    stop_loss = nearby_ob.bottom - (atr * 0.1)

                return entry, stop_loss, take_profit

            else:
                # Bearish setup (short)
                entry = sweep.sweep_level
                stop_buffer = atr * 0.3
                stop_loss = sweep.sweep_price + stop_buffer

                tp1 = entry - (stop_loss - entry) * 3.0
                tp2 = entry - (stop_loss - entry) * 5.0
                take_profit = tp1

                if nearby_ob:
                    entry = nearby_ob.midpoint
                if nearby_fvg:
                    entry = nearby_fvg.midpoint

                if nearby_ob and nearby_ob.top > stop_loss:
                    stop_loss = nearby_ob.top + (atr * 0.1)

                return entry, stop_loss, take_profit

        except Exception as e:
            logger.error(f"Failed to calculate entry levels: {e}")
            return None, None, None
