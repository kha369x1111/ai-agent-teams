"""
Market Analysis Agent
=====================
Specialized agent for technical and quantitative analysis.

Analyzes:
- SMC/ICT concepts (Order Blocks, FVG, BOS, Liquidity Sweeps)
- Market structure
- Multi-timeframe confluence
- Volume analysis
- Order flow

Outputs structured analysis reports to Decision Agent.
"""

import asyncio
import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
from loguru import logger

from agents.shared.base.agent_base import (
    BaseAgent, AgentIdentity, AgentMessage, AgentPriority
)
from agents.shared.communication.message_bus import get_message_bus, Topics
from core.analysis.smc_detector import SMCDetector
from core.data.binance_connector import BinanceConnector


@dataclass
class AnalysisReport:
    """Comprehensive analysis report"""
    symbol: str
    timestamp: datetime
    primary_timeframe: str
    higher_timeframe: str

    # Market structure
    primary_trend: str
    higher_trend: str
    structure_strength: float  # 0-100

    # SMC components
    liquidity_sweeps: List[Dict]
    order_blocks: List[Dict]
    fair_value_gaps: List[Dict]
    bos_events: List[Dict]
    choch_events: List[Dict]

    # Key levels
    premium_zone: tuple
    discount_zone: tuple
    equilibrium: float
    nearest_resistance: float
    nearest_support: float

    # Technical indicators
    atr: float
    rsi: float
    volume_profile: str  # 'high', 'normal', 'low'

    # Confluence
    confluence_score: int  # 0-100
    trading_bias: str      # 'bullish', 'bearish', 'neutral'
    confidence: float      # 0.0-1.0

    # Recommendation
    setup_quality: str     # 'A+', 'A', 'B', 'C'
    should_trade: bool


class MarketAnalysisAgent(BaseAgent):
    """Specialized agent for market analysis"""

    def __init__(self, connector: BinanceConnector):
        identity = AgentIdentity(
            name="MarketAnalysis",
            role="Analyze market using SMC/ICT and technical indicators",
            capabilities=[
                "technical_analysis",
                "smc_detection",
                "multi_timeframe_analysis",
                "pattern_recognition",
                "confluence_scoring",
            ],
            dependencies=[],
            version="1.0.0",
        )
        super().__init__(identity)

        self.connector = connector
        self.detector = SMCDetector()
        self.analysis_cache: Dict[str, AnalysisReport] = {}
        self.cache_ttl = 300  # 5 minutes

        # Subscribe to topics
        self.subscribers = []

        logger.info(f"📊 Market Analysis Agent ready")

    async def start(self):
        """Start the agent"""
        await super().start()
        bus = get_message_bus()
        bus.subscribe(self.agent_id, Topics.MARKET_DATA_UPDATE)
        bus.subscribe(self.agent_id, Topics.NEW_CANDLE)

    async def _periodic_tasks(self):
        """Periodic analysis tasks"""
        # Could run scheduled analysis here
        pass

    async def _handle_message(self, message: AgentMessage):
        """Handle incoming messages"""
        self.health_metrics['messages_processed'] += 1

        if message.subject == "analyze_symbol":
            # Request to analyze a symbol
            symbol = message.payload.get('symbol', '')
            timeframes = message.payload.get('timeframes', ['4h', '1d'])

            logger.info(f"📊 Analyzing {symbol} on {timeframes}")

            report = await self.analyze_symbol(symbol, timeframes)

            if report:
                # Send response
                await self.send_message(
                    receiver=message.sender,
                    message_type="response",
                    subject="analysis_complete",
                    payload={'report': self._report_to_dict(report)},
                    correlation_id=message.id,
                )

                # Broadcast for other interested agents
                bus = get_message_bus()
                broadcast = AgentMessage(
                    sender=self.agent_id,
                    receiver="",
                    message_type="event",
                    priority=AgentPriority.MEDIUM,
                    subject="analysis_ready",
                    payload={
                        'symbol': symbol,
                        'bias': report.trading_bias,
                        'confluence': report.confluence_score,
                        'quality': report.setup_quality,
                    },
                )
                await bus.publish(broadcast, Topics.ANALYSIS_COMPLETE)

        elif message.subject == "analyze_multiple":
            # Batch analysis
            symbols = message.payload.get('symbols', [])

            tasks = [
                self.analyze_symbol(s, ['4h', '1d'])
                for s in symbols
            ]
            reports = await asyncio.gather(*tasks, return_exceptions=True)

            valid_reports = [r for r in reports if isinstance(r, AnalysisReport)]

            await self.send_message(
                receiver=message.sender,
                message_type="response",
                subject="batch_analysis_complete",
                payload={
                    'reports': [self._report_to_dict(r) for r in valid_reports]
                },
                correlation_id=message.id,
            )

    async def analyze_symbol(
        self,
        symbol: str,
        timeframes: List[str] = ['4h', '1d']
    ) -> Optional[AnalysisReport]:
        """Perform full analysis on a symbol"""
        try:
            self.status = AgentStatus.THINKING
            primary_tf = timeframes[0]
            higher_tf = timeframes[1] if len(timeframes) > 1 else timeframes[0]

            # Fetch data
            primary_df = self.connector.fetch_ohlcv(symbol, primary_tf, limit=500)
            higher_df = self.connector.fetch_ohlcv(symbol, higher_tf, limit=200)

            if primary_df.empty:
                logger.warning(f"No data for {symbol}")
                self.status = AgentStatus.RUNNING
                return None

            # Analyze market structure
            primary_structure = self.detector.analyze_market_structure(primary_df)
            higher_structure = self.detector.analyze_market_structure(higher_df)

            # Detect SMC components
            swing_highs, swing_lows = self.detector.find_swing_points(primary_df)
            sweeps = self.detector.detect_liquidity_sweeps(primary_df, swing_highs, swing_lows)
            order_blocks = self.detector.detect_order_blocks(primary_df)
            fvgs = self.detector.detect_fair_value_gaps(primary_df)

            # Calculate ATR
            atr = self.detector.calculate_atr(primary_df).iloc[-1]

            # Calculate simple RSI
            rsi = self._calculate_rsi(primary_df)

            # Volume analysis
            volume_profile = self._analyze_volume(primary_df)

            # Find key levels
            resistance, support = self._find_key_levels(primary_df, swing_highs, swing_lows)

            # Calculate confluence
            confluence = self._calculate_confluence_score(
                primary_structure, higher_structure, sweeps, order_blocks, fvgs
            )

            # Determine trading bias
            bias = self._determine_bias(
                primary_structure, higher_structure, sweeps
            )

            # Setup quality
            quality = self._grade_setup(confluence, bias, sweeps)

            report = AnalysisReport(
                symbol=symbol,
                timestamp=datetime.now(),
                primary_timeframe=primary_tf,
                higher_timeframe=higher_tf,
                primary_trend=primary_structure.trend,
                higher_trend=higher_structure.trend,
                structure_strength=self._calculate_structure_strength(primary_structure),
                liquidity_sweeps=[self._sweep_to_dict(s) for s in sweeps[-3:]],
                order_blocks=[self._ob_to_dict(o) for o in order_blocks[-5:] if not o.mitigated],
                fair_value_gaps=[self._fvg_to_dict(f) for f in fvgs[-5:] if not f.filled],
                bos_events=[self._structure_to_dict(primary_structure.last_bos)] if primary_structure.last_bos else [],
                choch_events=[self._structure_to_dict(primary_structure.last_choch)] if primary_structure.last_choch else [],
                premium_zone=primary_structure.premium_zone,
                discount_zone=primary_structure.discount_zone,
                equilibrium=primary_structure.equilibrium,
                nearest_resistance=resistance,
                nearest_support=support,
                atr=atr,
                rsi=rsi,
                volume_profile=volume_profile,
                confluence_score=confluence,
                trading_bias=bias,
                confidence=min(1.0, confluence / 100),
                setup_quality=quality,
                should_trade=confluence >= 60 and bias != 'neutral',
            )

            # Cache report
            self.analysis_cache[symbol] = report
            self.remember(f"analysis_{symbol}", report, ttl=self.cache_ttl)

            self.status = AgentStatus.RUNNING
            logger.success(
                f"✅ Analysis complete: {symbol} - "
                f"Bias: {bias}, Quality: {quality}, Confluence: {confluence}"
            )

            return report

        except Exception as e:
            logger.error(f"❌ Analysis failed for {symbol}: {e}")
            self.status = AgentStatus.RUNNING
            return None

    def _calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calculate RSI"""
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1] if not rsi.empty else 50.0

    def _analyze_volume(self, df: pd.DataFrame) -> str:
        """Analyze volume profile"""
        recent_volume = df['volume'].tail(5).mean()
        avg_volume = df['volume'].tail(50).mean()

        if recent_volume > avg_volume * 1.5:
            return 'high'
        elif recent_volume < avg_volume * 0.7:
            return 'low'
        else:
            return 'normal'

    def _find_key_levels(
        self,
        df: pd.DataFrame,
        swing_highs: list,
        swing_lows: list
    ) -> tuple:
        """Find nearest resistance and support"""
        current_price = df['close'].iloc[-1]

        # Find nearest resistance above current price
        resistances = [sh[1] for sh in swing_highs if sh[1] > current_price]
        nearest_resistance = min(resistances) if resistances else current_price * 1.05

        # Find nearest support below current price
        supports = [sl[1] for sl in swing_lows if sl[1] < current_price]
        nearest_support = max(supports) if supports else current_price * 0.95

        return nearest_resistance, nearest_support

    def _calculate_confluence_score(
        self,
        primary_structure,
        higher_structure,
        sweeps,
        order_blocks,
        fvgs,
    ) -> int:
        """Calculate confluence score"""
        score = 0

        # Trend alignment (25 points)
        if primary_structure.trend == higher_structure.trend and primary_structure.trend != 'ranging':
            score += 25

        # Liquidity sweeps (25 points)
        if sweeps:
            latest = sweeps[-1]
            if latest.rejection_pct > 50:
                score += 25
            elif latest.rejection_pct > 30:
                score += 15

        # Order blocks (20 points)
        active_obs = [ob for ob in order_blocks if not ob.mitigated]
        if active_obs:
            score += min(20, len(active_obs) * 7)

        # FVGs (15 points)
        active_fvgs = [fvg for fvg in fvgs if not fvg.filled]
        if active_fvgs:
            score += min(15, len(active_fvgs) * 5)

        # Structure strength (15 points)
        if primary_structure.last_bos:
            score += 15

        return min(100, score)

    def _determine_bias(self, primary_structure, higher_structure, sweeps) -> str:
        """Determine trading bias"""
        if not sweeps:
            return 'neutral'

        latest_sweep = sweeps[-1]

        # Bullish bias
        if (latest_sweep.is_bullish and higher_structure.trend == 'bullish'):
            return 'bullish'

        # Bearish bias
        if (not latest_sweep.is_bullish and higher_structure.trend == 'bearish'):
            return 'bearish'

        # Reversal signals
        if higher_structure.last_choch:
            if higher_structure.last_choch.direction == 'bullish':
                return 'bullish'
            else:
                return 'bearish'

        return 'neutral'

    def _grade_setup(self, confluence: int, bias: str, sweeps: list) -> str:
        """Grade the setup quality"""
        if confluence >= 85 and bias != 'neutral':
            return 'A+'
        elif confluence >= 75 and bias != 'neutral':
            return 'A'
        elif confluence >= 65 and bias != 'neutral':
            return 'B'
        elif confluence >= 50:
            return 'C'
        else:
            return 'D'

    def _calculate_structure_strength(self, structure) -> float:
        """Calculate market structure strength"""
        strength = 0
        if structure.last_bos:
            strength += 50
        if structure.last_choch:
            strength += 30
        if structure.trend != 'ranging':
            strength += 20
        return min(100, strength)

    # Serialization helpers
    def _sweep_to_dict(self, sweep) -> Dict:
        return {
            'timestamp': sweep.timestamp.isoformat(),
            'side': sweep.side,
            'level': sweep.sweep_level,
            'rejection_pct': sweep.rejection_pct,
            'is_bullish': sweep.is_bullish,
        }

    def _ob_to_dict(self, ob) -> Dict:
        return {
            'timestamp': ob.timestamp.isoformat(),
            'type': ob.type,
            'top': ob.top,
            'bottom': ob.bottom,
            'midpoint': ob.midpoint,
            'strength': ob.strength,
        }

    def _fvg_to_dict(self, fvg) -> Dict:
        return {
            'timestamp': fvg.timestamp.isoformat(),
            'type': fvg.type,
            'top': fvg.top,
            'bottom': fvg.bottom,
            'size_atr': fvg.size_atr,
        }

    def _structure_to_dict(self, structure_point) -> Dict:
        return {
            'type': structure_point.type,
            'direction': structure_point.direction,
            'level': structure_point.level,
            'timestamp': structure_point.timestamp.isoformat(),
        }

    def _report_to_dict(self, report: AnalysisReport) -> Dict:
        """Convert report to dict"""
        return asdict(report)
