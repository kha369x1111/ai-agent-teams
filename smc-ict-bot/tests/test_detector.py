"""
Test SMC Detector
=================
Unit tests for the SMC/ICT detection engine.
"""

import sys
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.analysis.smc_detector import SMCDetector


def create_test_data(periods: int = 200) -> pd.DataFrame:
    """Create synthetic OHLCV data for testing"""
    np.random.seed(42)

    # Generate price data with trends
    base_price = 30000
    prices = [base_price]

    for i in range(periods):
        change = np.random.normal(0.001, 0.02)
        # Add some trends
        if i > 50 and i < 100:
            change += 0.005  # Uptrend
        elif i > 150 and i < 180:
            change -= 0.005  # Downtrend

        new_price = prices[-1] * (1 + change)
        prices.append(new_price)

    # Create OHLCV
    dates = pd.date_range(start='2024-01-01', periods=periods, freq='4H')
    df = pd.DataFrame({
        'timestamp': dates,
        'open': prices[:-1],
        'close': prices[1:],
        'high': [max(p1, p2) * (1 + abs(np.random.normal(0, 0.005)))
                 for p1, p2 in zip(prices[:-1], prices[1:])],
        'low': [min(p1, p2) * (1 - abs(np.random.normal(0, 0.005)))
                for p1, p2 in zip(prices[:-1], prices[1:])],
        'volume': np.random.uniform(100, 1000, periods),
    })

    df.set_index('timestamp', inplace=True)

    # Ensure OHLC validity
    df['high'] = df[['open', 'high', 'close']].max(axis=1)
    df['low'] = df[['open', 'low', 'close']].min(axis=1)

    return df


def test_swing_points():
    """Test swing point detection"""
    print("\n🧪 Testing Swing Point Detection...")
    df = create_test_data(200)
    detector = SMCDetector()

    swing_highs, swing_lows = detector.find_swing_points(df, lookback=20)

    print(f"   ✅ Found {len(swing_highs)} swing highs")
    print(f"   ✅ Found {len(swing_lows)} swing lows")

    assert len(swing_highs) > 0, "Should find swing highs"
    assert len(swing_lows) > 0, "Should find swing lows"

    return True


def test_atr():
    """Test ATR calculation"""
    print("\n🧪 Testing ATR Calculation...")
    df = create_test_data(200)
    detector = SMCDetector()

    atr = detector.calculate_atr(df)

    print(f"   ✅ ATR calculated: {len(atr)} periods")
    print(f"   ✅ Last ATR: {atr.iloc[-1]:.2f}")

    assert len(atr) == len(df), "ATR length should match dataframe"
    assert atr.iloc[-1] > 0, "ATR should be positive"

    return True


def test_order_blocks():
    """Test Order Block detection"""
    print("\n🧪 Testing Order Block Detection...")
    df = create_test_data(200)
    detector = SMCDetector()

    obs = detector.detect_order_blocks(df)

    print(f"   ✅ Found {len(obs)} Order Blocks")

    if obs:
        bullish = sum(1 for ob in obs if ob.type == 'bullish')
        bearish = sum(1 for ob in obs if ob.type == 'bearish')
        print(f"   ✅ Bullish: {bullish}, Bearish: {bearish}")

    return True


def test_fvg():
    """Test Fair Value Gap detection"""
    print("\n🧪 Testing Fair Value Gap Detection...")
    df = create_test_data(200)
    detector = SMCDetector()

    fvgs = detector.detect_fair_value_gaps(df)

    print(f"   ✅ Found {len(fvgs)} FVGs")

    if fvgs:
        bullish = sum(1 for fvg in fvgs if fvg.type == 'bullish')
        bearish = sum(1 for fvg in fvgs if fvg.type == 'bearish')
        print(f"   ✅ Bullish: {bullish}, Bearish: {bearish}")

    return True


def test_market_structure():
    """Test market structure analysis"""
    print("\n🧪 Testing Market Structure Analysis...")
    df = create_test_data(200)
    detector = SMCDetector()

    structure = detector.analyze_market_structure(df)

    print(f"   ✅ Trend: {structure.trend}")
    print(f"   ✅ Swing Highs: {len(structure.swing_highs)}")
    print(f"   ✅ Swing Lows: {len(structure.swing_lows)}")
    print(f"   ✅ Equilibrium: {structure.equilibrium:.2f}")

    assert structure.trend in ['bullish', 'bearish', 'ranging']

    return True


def test_liquidity_sweeps():
    """Test liquidity sweep detection"""
    print("\n🧪 Testing Liquidity Sweep Detection...")
    df = create_test_data(300)
    detector = SMCDetector()

    swing_highs, swing_lows = detector.find_swing_points(df)
    sweeps = detector.detect_liquidity_sweeps(df, swing_highs, swing_lows)

    print(f"   ✅ Found {len(sweeps)} liquidity sweeps")

    if sweeps:
        high_sweeps = sum(1 for s in sweeps if s.side == 'high')
        low_sweeps = sum(1 for s in sweeps if s.side == 'low')
        print(f"   ✅ High sweeps: {high_sweeps}, Low sweeps: {low_sweeps}")

        avg_rejection = np.mean([s.rejection_pct for s in sweeps])
        print(f"   ✅ Avg rejection: {avg_rejection:.1f}%")

    return True


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("🧪 SMC/ICT Detector - Unit Tests")
    print("=" * 60)

    tests = [
        test_swing_points,
        test_atr,
        test_order_blocks,
        test_fvg,
        test_market_structure,
        test_liquidity_sweeps,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"   ❌ Failed: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"📊 Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
