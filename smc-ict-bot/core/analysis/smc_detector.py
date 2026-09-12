"""
SMC/ICT Technical Analysis Engine
==================================
Core detection algorithms for:
- Liquidity Sweeps (Primary focus)
- Order Blocks
- Fair Value Gaps
- Break of Structure / Change of Character
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from loguru import logger


@dataclass
class LiquiditySweep:
    """Represents a liquidity sweep event"""
    timestamp: datetime
    side: str                    # 'high' or 'low' (what was swept)
    sweep_level: float           # The level that was swept
    sweep_price: float           # The extreme price reached
    close_price: float           # Candle close price
    rejection_pct: float         # How strong the rejection was
    volume: float                # Volume at sweep
    atr: float                   # ATR at time of sweep
    is_bullish: bool             # Result of the sweep (reversal direction)
    candle_index: int            # Index in dataframe


@dataclass
class OrderBlock:
    """Represents an Order Block zone"""
    timestamp: datetime
    type: str                    # 'bullish' or 'bearish'
    top: float                   # Top of OB zone
    bottom: float                # Bottom of OB zone
    midpoint: float              # Midpoint for entry
    mitigated: bool              # Whether OB has been mitigated
    strength: float              # OB strength score (0-100)
    cause: str                   # What caused this OB
    candle_index: int


@dataclass
class FairValueGap:
    """Represents a Fair Value Gap"""
    timestamp: datetime
    type: str                    # 'bullish' or 'bearish'
    top: float
    bottom: float
    midpoint: float
    size: float                  # Size in price
    size_atr: float              # Size in ATR
    filled: bool                 # Whether FVG has been filled
    candle_index: int


@dataclass
class StructurePoint:
    """Market structure point"""
    timestamp: datetime
    type: str                    # 'BOS' or 'CHoCH'
    direction: str               # 'bullish' or 'bearish'
    level: float                 # The structural level
    candle_index: int
    confirmed: bool


@dataclass
class MarketStructure:
    """Overall market structure"""
    trend: str                   # 'bullish', 'bearish', 'ranging'
    last_bos: Optional[StructurePoint] = None
    last_choch: Optional[StructurePoint] = None
    swing_highs: List[Tuple[int, float]] = field(default_factory=list)
    swing_lows: List[Tuple[int, float]] = field(default_factory=list)
    premium_zone: Tuple[float, float] = (0, 0)
    discount_zone: Tuple[float, float] = (0, 0)
    equilibrium: float = 0


class SMCDetector:
    """SMC/ICT Pattern Detection Engine"""

    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.swing_lookback = self.config.get('swing_lookback', 20)
        self.sweep_threshold_pct = self.config.get('sweep_threshold_pct', 0.5)
        self.ob_lookback = self.config.get('ob_lookback', 10)
        self.fvg_min_size = self.config.get('fvg_min_size', 0.5)
        logger.info("🔍 SMC Detector initialized")

    # ==================== Utility Functions ====================

    def calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Average True Range"""
        high = df['high']
        low = df['low']
        close = df['close']

        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()

        return atr

    def find_swing_points(
        self,
        df: pd.DataFrame,
        lookback: int = None
    ) -> Tuple[List[Tuple[int, float]], List[Tuple[int, float]]]:
        """
        Identify swing highs and lows

        Returns:
            (swing_highs, swing_lows) as lists of (index, price) tuples
        """
        lookback = lookback or self.swing_lookback
        highs = df['high'].values
        lows = df['low'].values

        swing_highs = []
        swing_lows = []

        for i in range(lookback, len(df) - lookback):
            # Check swing high
            if highs[i] == max(highs[i - lookback:i + lookback + 1]):
                swing_highs.append((i, highs[i]))

            # Check swing low
            if lows[i] == min(lows[i - lookback:i + lookback + 1]):
                swing_lows.append((i, lows[i]))

        return swing_highs, swing_lows

    def get_premium_discount_zones(
        self,
        df: pd.DataFrame,
        lookback: int = 50
    ) -> Tuple[Tuple[float, float], Tuple[float, float], float]:
        """
        Calculate premium/discount zones based on recent range

        Returns:
            (premium_zone, discount_zone, equilibrium)
        """
        recent_high = df['high'].tail(lookback).max()
        recent_low = df['low'].tail(lookback).min()
        range_size = recent_high - recent_low
        equilibrium = recent_low + (range_size * 0.5)

        # 50% premium zone (equilibrium to high)
        premium = (equilibrium, recent_high)
        # 50% discount zone (low to equilibrium)
        discount = (recent_low, equilibrium)

        return premium, discount, equilibrium

    # ==================== Liquidity Sweep Detection ====================

    def detect_liquidity_sweeps(
        self,
        df: pd.DataFrame,
        swing_highs: List[Tuple[int, float]],
        swing_lows: List[Tuple[int, float]]
    ) -> List[LiquiditySweep]:
        """
        Detect liquidity sweeps (the primary strategy focus)

        A liquidity sweep occurs when:
        - Price breaks above/below a key swing high/low
        - Then quickly reverses (rejection)
        - Often traps retail traders

        Args:
            df: OHLCV dataframe
            swing_highs: List of (index, price) for swing highs
            swing_lows: List of (index, price) for swing lows

        Returns:
            List of LiquiditySweep objects
        """
        sweeps = []
        atr = self.calculate_atr(df)

        # Track which swing levels have been swept
        for idx in range(self.swing_lookback, len(df)):
            current_candle = df.iloc[idx]
            current_atr = atr.iloc[idx] if not pd.isna(atr.iloc[idx]) else 0.001

            # Check for sweep of swing highs (bearish sweep - price goes above then reverses down)
            for sh_idx, sh_price in swing_highs:
                if sh_idx >= idx:
                    continue

                # Price pierces above swing high
                if current_candle['high'] > sh_price:
                    threshold = current_atr * (self.sweep_threshold_pct / 100)
                    if current_candle['high'] - sh_price >= threshold:
                        # Check for rejection (close back below)
                        if current_candle['close'] < sh_price:
                            # Calculate rejection strength
                            total_range = current_candle['high'] - current_candle['low']
                            if total_range > 0:
                                rejection = (current_candle['high'] - current_candle['close']) / total_range

                                if rejection >= self.config.get('min_sweep_rejection', 0.3):
                                    sweep = LiquiditySweep(
                                        timestamp=df.index[idx],
                                        side='high',
                                        sweep_level=sh_price,
                                        sweep_price=current_candle['high'],
                                        close_price=current_candle['close'],
                                        rejection_pct=rejection * 100,
                                        volume=current_candle['volume'],
                                        atr=current_atr,
                                        is_bullish=True,  # High sweep = bullish reversal expected
                                        candle_index=idx
                                    )
                                    sweeps.append(sweep)
                                    logger.debug(f"📈 High Sweep detected at {df.index[idx]}: {sh_price}")

            # Check for sweep of swing lows (bullish sweep - price goes below then reverses up)
            for sl_idx, sl_price in swing_lows:
                if sl_idx >= idx:
                    continue

                # Price pierces below swing low
                if current_candle['low'] < sl_price:
                    threshold = current_atr * (self.sweep_threshold_pct / 100)
                    if sl_price - current_candle['low'] >= threshold:
                        # Check for rejection (close back above)
                        if current_candle['close'] > sl_price:
                            total_range = current_candle['high'] - current_candle['low']
                            if total_range > 0:
                                rejection = (current_candle['close'] - current_candle['low']) / total_range

                                if rejection >= self.config.get('min_sweep_rejection', 0.3):
                                    sweep = LiquiditySweep(
                                        timestamp=df.index[idx],
                                        side='low',
                                        sweep_level=sl_price,
                                        sweep_price=current_candle['low'],
                                        close_price=current_candle['close'],
                                        rejection_pct=rejection * 100,
                                        volume=current_candle['volume'],
                                        atr=current_atr,
                                        is_bullish=False,  # Low sweep = bearish reversal expected
                                        candle_index=idx
                                    )
                                    sweeps.append(sweep)
                                    logger.debug(f"📉 Low Sweep detected at {df.index[idx]}: {sl_price}")

        logger.info(f"🔍 Found {len(sweeps)} liquidity sweeps")
        return sweeps

    # ==================== Order Block Detection ====================

    def detect_order_blocks(self, df: pd.DataFrame) -> List[OrderBlock]:
        """
        Detect Order Blocks

        Bullish OB: Last bearish candle before strong bullish move
        Bearish OB: Last bullish candle before strong bearish move
        """
        order_blocks = []
        atr = self.calculate_atr(df)

        for i in range(self.ob_lookback, len(df) - 1):
            current_atr = atr.iloc[i] if not pd.isna(atr.iloc[i]) else 0.001

            # Look for displacement (strong move)
            next_candle = df.iloc[i + 1]
            current_candle = df.iloc[i]

            # Bullish displacement: strong upward move
            bullish_move = (next_candle['close'] - next_candle['low']) / current_atr
            if bullish_move >= self.config.get('ob_min_displacement', 0.7):
                # Find last bearish candle before this
                for j in range(i - 1, max(0, i - self.ob_lookback), -1):
                    if df.iloc[j]['close'] < df.iloc[j]['open']:  # Bearish candle
                        ob = OrderBlock(
                            timestamp=df.index[j],
                            type='bullish',
                            top=df.iloc[j]['high'],
                            bottom=df.iloc[j]['low'],
                            midpoint=(df.iloc[j]['high'] + df.iloc[j]['low']) / 2,
                            mitigated=False,
                            strength=min(100, bullish_move * 50),
                            cause='bullish_displacement',
                            candle_index=j
                        )
                        order_blocks.append(ob)
                        break

            # Bearish displacement: strong downward move
            bearish_move = (next_candle['high'] - next_candle['close']) / current_atr
            if bearish_move >= self.config.get('ob_min_displacement', 0.7):
                # Find last bullish candle before this
                for j in range(i - 1, max(0, i - self.ob_lookback), -1):
                    if df.iloc[j]['close'] > df.iloc[j]['open']:  # Bullish candle
                        ob = OrderBlock(
                            timestamp=df.index[j],
                            type='bearish',
                            top=df.iloc[j]['high'],
                            bottom=df.iloc[j]['low'],
                            midpoint=(df.iloc[j]['high'] + df.iloc[j]['low']) / 2,
                            mitigated=False,
                            strength=min(100, bearish_move * 50),
                            cause='bearish_displacement',
                            candle_index=j
                        )
                        order_blocks.append(ob)
                        break

        # Check mitigation status
        order_blocks = self._check_ob_mitigation(df, order_blocks)

        logger.info(f"🔍 Found {len(order_blocks)} order blocks")
        return order_blocks

    def _check_ob_mitigation(
        self,
        df: pd.DataFrame,
        order_blocks: List[OrderBlock]
    ) -> List[OrderBlock]:
        """Check if order blocks have been mitigated (filled)"""
        for ob in order_blocks:
            for idx in range(ob.candle_index + 1, len(df)):
                candle = df.iloc[idx]

                # Bullish OB is mitigated when price closes below it
                if ob.type == 'bullish':
                    if candle['close'] < ob.bottom:
                        ob.mitigated = True
                        break

                # Bearish OB is mitigated when price closes above it
                elif ob.type == 'bearish':
                    if candle['close'] > ob.top:
                        ob.mitigated = True
                        break

        return [ob for ob in order_blocks]  # Return all, marked with mitigation status

    # ==================== Fair Value Gap Detection ====================

    def detect_fair_value_gaps(self, df: pd.DataFrame) -> List[FairValueGap]:
        """
        Detect Fair Value Gaps (FVG / Imbalance)

        Bullish FVG: Low[i] > High[i-2] (gap between candles)
        Bearish FVG: High[i] < Low[i-2]
        """
        fvgs = []
        atr = self.calculate_atr(df)

        for i in range(2, len(df)):
            current_atr = atr.iloc[i] if not pd.isna(atr.iloc[i]) else 0.001

            candle_2_ago = df.iloc[i - 2]
            current = df.iloc[i]

            # Bullish FVG
            if current['low'] > candle_2_ago['high']:
                gap_size = current['low'] - candle_2_ago['high']
                if gap_size / current_atr >= self.fvg_min_size:
                    fvg = FairValueGap(
                        timestamp=df.index[i],
                        type='bullish',
                        top=current['low'],
                        bottom=candle_2_ago['high'],
                        midpoint=(current['low'] + candle_2_ago['high']) / 2,
                        size=gap_size,
                        size_atr=gap_size / current_atr,
                        filled=False,
                        candle_index=i
                    )
                    fvgs.append(fvg)

            # Bearish FVG
            if current['high'] < candle_2_ago['low']:
                gap_size = candle_2_ago['low'] - current['high']
                if gap_size / current_atr >= self.fvg_min_size:
                    fvg = FairValueGap(
                        timestamp=df.index[i],
                        type='bearish',
                        top=candle_2_ago['low'],
                        bottom=current['high'],
                        midpoint=(candle_2_ago['low'] + current['high']) / 2,
                        size=gap_size,
                        size_atr=gap_size / current_atr,
                        filled=False,
                        candle_index=i
                    )
                    fvgs.append(fvg)

        # Check fill status
        fvgs = self._check_fvg_fill(df, fvgs)

        logger.info(f"🔍 Found {len(fvgs)} Fair Value Gaps")
        return fvgs

    def _check_fvg_fill(
        self,
        df: pd.DataFrame,
        fvgs: List[FairValueGap]
    ) -> List[FairValueGap]:
        """Check if FVGs have been filled"""
        for fvg in fvgs:
            for idx in range(fvg.candle_index + 1, len(df)):
                candle = df.iloc[idx]

                if fvg.type == 'bullish':
                    if candle['low'] <= fvg.midpoint:
                        fvg.filled = True
                        break
                else:
                    if candle['high'] >= fvg.midpoint:
                        fvg.filled = True
                        break

        return fvgs

    # ==================== Market Structure Analysis ====================

    def analyze_market_structure(
        self,
        df: pd.DataFrame
    ) -> MarketStructure:
        """
        Determine overall market structure (BOS/CHoCH)

        - BOS (Break of Structure): Continuation in trend direction
        - CHoCH (Change of Character): Potential reversal
        """
        swing_highs, swing_lows = self.find_swing_points(df)

        structure = MarketStructure(
            trend='ranging',
            swing_highs=swing_highs,
            swing_lows=swing_lows
        )

        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return structure

        # Analyze recent structure
        recent_highs = swing_highs[-5:]
        recent_lows = swing_lows[-5:]

        # Determine trend by comparing recent highs and lows
        if len(recent_highs) >= 2 and len(recent_lows) >= 2:
            higher_highs = recent_highs[-1][1] > recent_highs[-2][1]
            higher_lows = recent_lows[-1][1] > recent_lows[-2][1]

            if higher_highs and higher_lows:
                structure.trend = 'bullish'
            elif not higher_highs and not higher_lows:
                structure.trend = 'bearish'

        # Premium/Discount zones
        structure.premium_zone, structure.discount_zone, structure.equilibrium = \
            self.get_premium_discount_zones(df)

        # Detect last BOS/CHoCH
        structure = self._detect_bos_choch(df, structure)

        logger.info(f"📊 Market structure: {structure.trend}")
        return structure

    def _detect_bos_choch(
        self,
        df: pd.DataFrame,
        structure: MarketStructure
    ) -> MarketStructure:
        """Detect recent BOS/CHoCH events"""
        swing_highs = structure.swing_highs
        swing_lows = structure.swing_lows

        # Look for BOS in last 50 candles
        for i in range(len(df) - 1, max(0, len(df) - 50), -1):
            candle = df.iloc[i]

            # Bullish BOS: Close breaks above previous swing high
            for sh_idx, sh_price in swing_highs:
                if sh_idx < i and candle['close'] > sh_price:
                    # Check if it's BOS (continuation) or CHoCH (reversal)
                    if structure.trend == 'bullish':
                        structure.last_bos = StructurePoint(
                            timestamp=df.index[i],
                            type='BOS',
                            direction='bullish',
                            level=sh_price,
                            candle_index=i,
                            confirmed=True
                        )
                        return structure
                    else:
                        structure.last_choch = StructurePoint(
                            timestamp=df.index[i],
                            type='CHoCH',
                            direction='bullish',
                            level=sh_price,
                            candle_index=i,
                            confirmed=True
                        )
                        structure.trend = 'bullish'
                        return structure

            # Bearish BOS: Close breaks below previous swing low
            for sl_idx, sl_price in swing_lows:
                if sl_idx < i and candle['close'] < sl_price:
                    if structure.trend == 'bearish':
                        structure.last_bos = StructurePoint(
                            timestamp=df.index[i],
                            type='BOS',
                            direction='bearish',
                            level=sl_price,
                            candle_index=i,
                            confirmed=True
                        )
                        return structure
                    else:
                        structure.last_choch = StructurePoint(
                            timestamp=df.index[i],
                            type='CHoCH',
                            direction='bearish',
                            level=sl_price,
                            candle_index=i,
                            confirmed=True
                        )
                        structure.trend = 'bearish'
                        return structure

        return structure
