"""
Decision Making Agent
=====================
Central decision-making brain that combines:
- Technical analysis (from Analysis Agent)
- News intelligence (from News Agent)
- Market sentiment
- Risk constraints (from Risk Agent)
- Historical patterns

Outputs: Final trading decisions with reasoning.
"""

import asyncio
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger

from agents.shared.base.agent_base import (
    BaseAgent, AgentIdentity, AgentMessage, AgentPriority
)
from agents.shared.communication.message_bus import get_message_bus, Topics
from agents.decision_agent.ai_brain import get_ai_brain


class DecisionType(Enum):
    """Decision types"""
    ENTER_LONG = "enter_long"
    ENTER_SHORT = "enter_short"
    EXIT_POSITION = "exit_position"
    HOLD = "hold"
    WAIT = "wait"
    REDUCE_SIZE = "reduce_size"


class DecisionConfidence(Enum):
    """Decision confidence levels"""
    VERY_HIGH = "very_high"  # 90%+
    HIGH = "high"            # 75-90%
    MEDIUM = "medium"        # 60-75%
    LOW = "low"              # 45-60%
    VERY_LOW = "very_low"    # <45%


@dataclass
class TradingDecision:
    """Final trading decision"""
    decision_id: str
    symbol: str
    decision_type: DecisionType
    confidence: DecisionConfidence
    confidence_score: float  # 0-100

    # Entry details (if entering)
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    position_size_pct: float = 0  # % of capital

    # Reasoning
    technical_score: float = 0
    news_score: float = 0
    sentiment_score: float = 0
    risk_score: float = 0

    reasoning: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    timestamp: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None  # Decision validity period


class DecisionMakingAgent(BaseAgent):
    """Central decision-making agent"""

    def __init__(self):
        identity = AgentIdentity(
            name="DecisionMaker",
            role="Make final trading decisions by combining multiple inputs",
            capabilities=[
                "decision_synthesis",
                "multi_factor_analysis",
                "risk_reward_calculation",
                "pattern_recognition",
                "priority_management",
                "ai_augmented_decision",  # 🆕 جديد
            ],
            dependencies=["MarketAnalysis", "NewsIntelligence", "RiskManager"],
            version="1.0.0",
        )
        super().__init__(identity)

        # Decision state
        self.pending_decisions: Dict[str, TradingDecision] = {}
        self.decision_history: List[TradingDecision] = []
        self.active_context: Dict = {}

        # 🆕 AI Brain
        self.ai_brain = get_ai_brain()
        self.use_ai = True  # تفعيل/تعطيل AI

        # Decision weights
        self.weights = {
            'technical': 0.40,   # 40% from technical analysis
            'news': 0.25,        # 25% from news
            'sentiment': 0.15,   # 15% from market sentiment
            'risk': 0.20,        # 20% from risk assessment
        }

        logger.info(f"🧠 Decision Making Agent ready")

    async def start(self):
        """Start the agent"""
        await super().start()
        bus = get_message_bus()
        bus.subscribe(self.agent_id, Topics.ANALYSIS_COMPLETE)
        bus.subscribe(self.agent_id, Topics.NEWS_BREAKING)
        bus.subscribe(self.agent_id, Topics.RISK_ALERT)

    async def _handle_message(self, message: AgentMessage):
        """Handle incoming messages"""
        self.health_metrics['messages_processed'] += 1

        if message.subject == "make_decision":
            # Request to make a decision
            context = message.payload
            decision = await self.make_decision(context)

            if decision:
                await self.send_message(
                    receiver=message.sender,
                    message_type="response",
                    subject="decision_made",
                    payload={'decision': self._decision_to_dict(decision)},
                    correlation_id=message.id,
                )

                # Broadcast decision
                bus = get_message_bus()
                topic = (
                    Topics.TRADE_APPROVED
                    if decision.decision_type in [DecisionType.ENTER_LONG, DecisionType.ENTER_SHORT]
                    else Topics.DECISION_MADE
                )
                broadcast = AgentMessage(
                    sender=self.agent_id,
                    receiver="",
                    message_type="event",
                    priority=AgentPriority.HIGH,
                    subject="trading_decision",
                    payload=self._decision_to_dict(decision),
                )
                await bus.publish(broadcast, topic)

        elif message.subject == "exit_decision":
            # Request to decide on exit
            position = message.payload
            decision = await self._evaluate_exit(position)
            await self.send_message(
                receiver=message.sender,
                message_type="response",
                subject="exit_decision_made",
                payload={'decision': self._decision_to_dict(decision)},
                correlation_id=message.id,
            )

    async def make_decision(self, context: Dict) -> Optional[TradingDecision]:
        """
        Make a trading decision based on multiple inputs

        Args:
            context: {
                'symbol': str,
                'analysis': AnalysisReport,
                'news': List[NewsItem],
                'risk_state': RiskState,
                'market_context': Dict
            }
        """
        try:
            self.status = AgentStatus.THINKING
            symbol = context.get('symbol', '')

            logger.info(f"🧠 Making decision for {symbol}")

            # Extract inputs
            analysis = context.get('analysis')
            news = context.get('news', [])
            risk_state = context.get('risk_state', {})
            market_context = context.get('market_context', {})

            if not analysis:
                logger.warning("No analysis provided")
                self.status = AgentStatus.RUNNING
                return None

            # Calculate component scores
            technical_score = self._score_technical(analysis)
            news_score = self._score_news(news, symbol)
            sentiment_score = self._score_sentiment(market_context)
            risk_score = self._score_risk(risk_state)

            # 🆕 استشارة AI (إذا كان متاحاً)
            ai_analysis = None
            ai_score = 0
            if self.use_ai and self.ai_brain.is_available:
                try:
                    ai_analysis = await self.ai_brain.analyze_market_context(
                        symbol=symbol,
                        technical_analysis=self._format_tech_for_ai(analysis),
                        news_context=[self._news_to_dict(n) for n in news[:10]],
                        current_price=getattr(analysis, 'current_price', 0),
                    )

                    if ai_analysis:
                        # AI score (0-100)
                        ai_confidence = ai_analysis.confidence * 100
                        if ai_analysis.decision == 'wait':
                            ai_score = ai_confidence * 0.3  # خصم كبير للانتظار
                        else:
                            ai_score = ai_confidence

                        # إضافة عوامل AI
                        reasoning.append(f"🧠 AI Decision: {ai_analysis.decision} (confidence: {ai_analysis.confidence:.0%})")
                        reasoning.append(f"   AI Reasoning: {ai_analysis.reasoning}")

                        # إضافة تحذيرات AI
                        warnings.extend([f"🤖 AI: {w}" for w in ai_analysis.warnings])

                        logger.info(
                            f"🧠 AI says: {ai_analysis.decision.upper()} "
                            f"with {ai_analysis.confidence:.0%} confidence"
                        )

                except Exception as e:
                    logger.warning(f"AI analysis failed: {e}")

            # دمج AI في الـ score النهائي (إذا كان متاحاً)
            if ai_analysis and ai_analysis.decision != 'wait':
                # أعد حساب final_score مع AI
                if ai_analysis.decision in ['long', 'short']:
                    # AI متفق مع التحليل الفني = تعزيز
                    if (ai_analysis.decision == 'long' and analysis.trading_bias == 'bullish') or \
                       (ai_analysis.decision == 'short' and analysis.trading_bias == 'bearish'):
                        # تعزيز إيجابي
                        logger.info("✅ AI agrees with technical analysis - boosting confidence")

            # Combine scores
            final_score = (
                technical_score * self.weights['technical'] +
                news_score * self.weights['news'] +
                sentiment_score * self.weights['sentiment'] +
                risk_score * self.weights['risk']
            )

            # 🆕 إضافة AI Score (وزن 15%)
            if ai_analysis:
                final_score = (final_score * 0.85) + (ai_score * 0.15)

            # Determine decision type
            decision_type = self._determine_action(
                final_score, analysis, risk_state
            )

            # Calculate confidence
            confidence_score = final_score
            confidence = self._grade_confidence(confidence_score)

            # Build reasoning
            reasoning = self._build_reasoning(
                technical_score, news_score, sentiment_score, risk_score,
                analysis, news, decision_type
            )

            # Add warnings
            warnings = self._build_warnings(analysis, news, risk_state)

            # Calculate position details
            entry_price = None
            stop_loss = None
            take_profit = None
            position_size_pct = 0

            if decision_type in [DecisionType.ENTER_LONG, DecisionType.ENTER_SHORT]:
                entry_price, stop_loss, take_profit, position_size_pct = \
                    self._calculate_entry_details(analysis, decision_type, risk_state)

            # Create decision
            decision = TradingDecision(
                decision_id=f"DEC_{symbol}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                symbol=symbol,
                decision_type=decision_type,
                confidence=confidence,
                confidence_score=confidence_score,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                position_size_pct=position_size_pct,
                technical_score=technical_score,
                news_score=news_score,
                sentiment_score=sentiment_score,
                risk_score=risk_score,
                reasoning=reasoning,
                warnings=warnings,
                expires_at=datetime.now() + timedelta(hours=4) if decision_type != DecisionType.HOLD else None,
            )

            # Store decision
            self.decision_history.append(decision)
            self.pending_decisions[symbol] = decision

            self.status = AgentStatus.RUNNING

            logger.success(
                f"✅ Decision: {decision_type.value} {symbol} "
                f"[Confidence: {confidence.value} ({confidence_score:.1f})]"
            )

            return decision

        except Exception as e:
            logger.error(f"❌ Decision making failed: {e}")
            self.status = AgentStatus.RUNNING
            return None

    def _score_technical(self, analysis) -> float:
        """Score technical analysis (0-100)"""
        score = 0

        # Base on confluence
        score += analysis.confluence_score * 0.6  # 60% from confluence

        # Bonus for setup quality
        quality_bonus = {
            'A+': 40,
            'A': 30,
            'B': 20,
            'C': 10,
            'D': 0,
        }
        score += quality_bonus.get(analysis.setup_quality, 0) * 0.2  # 20% from quality

        # Volume confirmation
        if analysis.volume_profile == 'high':
            score += 10
        elif analysis.volume_profile == 'low':
            score -= 5

        # Multi-timeframe alignment
        if analysis.primary_trend == analysis.higher_trend:
            score += 10

        return min(100, max(0, score))

    def _score_news(self, news: List, symbol: str) -> float:
        """Score news impact (0-100, where 50 is neutral)"""
        if not news:
            return 50  # Neutral

        relevant_news = [n for n in news if symbol in n.affected_symbols]
        if not relevant_news:
            return 50

        # Calculate weighted sentiment
        impact_weights = {'critical': 5, 'high': 3, 'medium': 1.5, 'low': 0.5}
        weighted_sentiment = 0
        total_weight = 0

        for n in relevant_news:
            weight = impact_weights.get(n.impact_level, 1)
            weighted_sentiment += n.sentiment * weight
            total_weight += weight

        if total_weight == 0:
            return 50

        avg_sentiment = weighted_sentiment / total_weight

        # Convert -1 to 1 sentiment to 0-100 score
        score = 50 + (avg_sentiment * 50)

        # Penalty for critical negative news
        for n in relevant_news:
            if n.impact_level == 'critical' and n.sentiment < -0.5:
                score = min(score, 30)

        return score

    def _score_sentiment(self, market_context: Dict) -> float:
        """Score overall market sentiment (0-100)"""
        # From funding rate, OI, etc.
        funding_rate = market_context.get('funding_rate', 0)
        long_short_ratio = market_context.get('long_short_ratio', 1.0)

        score = 50  # Start neutral

        # Funding rate analysis
        if funding_rate > 0.01:  # Overheated longs
            score -= 15
        elif funding_rate < -0.01:  # Overheated shorts
            score += 15

        # Long/short ratio
        if long_short_ratio > 1.5:
            score -= 10  # Too many longs = contrarian bearish
        elif long_short_ratio < 0.7:
            score += 10

        return max(0, min(100, score))

    def _score_risk(self, risk_state: Dict) -> float:
        """Score risk environment (0-100, higher = safer to trade)"""
        score = 100

        # Drawdown penalty
        drawdown = risk_state.get('current_drawdown', 0)
        score -= drawdown * 5  # Each 1% drawdown = -5 score

        # Daily loss penalty
        daily_loss = abs(risk_state.get('daily_pnl_pct', 0))
        if daily_loss > 0:
            score -= daily_loss * 10

        # Open positions
        open_positions = risk_state.get('open_positions', 0)
        if open_positions >= 3:
            score -= 20

        return max(0, min(100, score))

    def _determine_action(
        self,
        final_score: float,
        analysis,
        risk_state: Dict
    ) -> DecisionType:
        """Determine what action to take"""
        # Not safe to trade
        if risk_state.get('current_drawdown', 0) > 8:
            return DecisionType.WAIT

        # Not enough confluence
        if analysis.confluence_score < 60:
            return DecisionType.WAIT

        # Determine direction
        if analysis.trading_bias == 'bullish' and final_score >= 65:
            return DecisionType.ENTER_LONG
        elif analysis.trading_bias == 'bearish' and final_score >= 65:
            return DecisionType.ENTER_SHORT

        # Neutral but high confluence = hold and wait
        if final_score >= 50:
            return DecisionType.HOLD

        return DecisionType.WAIT

    def _grade_confidence(self, score: float) -> DecisionConfidence:
        """Grade confidence based on score"""
        if score >= 85:
            return DecisionConfidence.VERY_HIGH
        elif score >= 75:
            return DecisionConfidence.HIGH
        elif score >= 60:
            return DecisionConfidence.MEDIUM
        elif score >= 45:
            return DecisionConfidence.LOW
        else:
            return DecisionConfidence.VERY_LOW

    def _build_reasoning(
        self,
        technical: float,
        news: float,
        sentiment: float,
        risk: float,
        analysis,
        news_items,
        decision_type
    ) -> List[str]:
        """Build human-readable reasoning"""
        reasoning = []

        reasoning.append(f"📊 Technical Analysis: {technical:.1f}/100")
        if analysis.confluence_score >= 75:
            reasoning.append(f"   Strong setup with {analysis.confluence_score} confluence")
        elif analysis.confluence_score >= 60:
            reasoning.append(f"   Decent setup ({analysis.confluence_score} confluence)")
        else:
            reasoning.append(f"   Weak setup ({analysis.confluence_score} confluence)")

        if analysis.trading_bias != 'neutral':
            reasoning.append(f"   Trading bias: {analysis.trading_bias}")

        reasoning.append(f"📰 News Sentiment: {news:.1f}/100")
        high_impact = [n for n in news_items if n.impact_level in ['high', 'critical']]
        if high_impact:
            reasoning.append(f"   {len(high_impact)} high-impact news items")

        reasoning.append(f"💭 Market Sentiment: {sentiment:.1f}/100")
        reasoning.append(f"🛡️ Risk Environment: {risk:.1f}/100")

        if analysis.liquidity_sweeps:
            latest = analysis.liquidity_sweeps[-1]
            reasoning.append(
                f"💧 Liquidity sweep detected: {latest['side']} "
                f"@ {latest['level']} ({latest['rejection_pct']:.1f}% rejection)"
            )

        reasoning.append(f"🎯 Final Decision: {decision_type.value}")

        return reasoning

    def _build_warnings(self, analysis, news, risk_state) -> List[str]:
        """Build list of warnings"""
        warnings = []

        # Drawdown warning
        drawdown = risk_state.get('current_drawdown', 0)
        if drawdown > 5:
            warnings.append(f"⚠️ Current drawdown: {drawdown:.2f}%")

        # News warnings
        critical_news = [n for n in news if n.impact_level == 'critical']
        if critical_news:
            warnings.append(f"🚨 {len(critical_news)} critical news events detected")

        # Volatility warning
        if hasattr(analysis, 'atr') and analysis.atr > 0:
            # Would need price to calculate volatility %
            pass

        # Counter-trend warning
        if hasattr(analysis, 'primary_trend') and hasattr(analysis, 'higher_trend'):
            if analysis.primary_trend != analysis.higher_trend and analysis.primary_trend != 'ranging':
                warnings.append("⚠️ Counter-timeframe trend detected")

        return warnings

    def _calculate_entry_details(
        self,
        analysis,
        decision_type: DecisionType,
        risk_state: Dict
    ) -> tuple:
        """Calculate entry, SL, TP, and position size"""
        if not analysis.liquidity_sweeps:
            return None, None, None, 0

        latest_sweep = analysis.liquidity_sweeps[-1]
        atr = analysis.atr if hasattr(analysis, 'atr') else 0

        is_long = decision_type == DecisionType.ENTER_LONG

        if is_long:
            entry = latest_sweep['level']
            stop_loss = entry - (atr * 1.5)
            take_profit = entry + (atr * 4.0)
        else:
            entry = latest_sweep['level']
            stop_loss = entry + (atr * 1.5)
            take_profit = entry - (atr * 4.0)

        # Position size based on risk
        base_risk = 1.0  # 1% base risk

        # Reduce size if risk environment is poor
        if risk_state.get('current_drawdown', 0) > 3:
            base_risk = 0.5
        elif risk_state.get('current_drawdown', 0) > 5:
            base_risk = 0.25

        return entry, stop_loss, take_profit, base_risk

    async def _evaluate_exit(self, position: Dict) -> TradingDecision:
        """Evaluate whether to exit a position"""
        # Simplified exit logic
        pnl_pct = position.get('unrealized_pnl_pct', 0)

        if pnl_pct > 5:  # Take profit
            decision_type = DecisionType.EXIT_POSITION
        elif pnl_pct < -2:  # Stop loss
            decision_type = DecisionType.EXIT_POSITION
        else:
            decision_type = DecisionType.HOLD

        return TradingDecision(
            decision_id=f"EXIT_{position.get('symbol', '')}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            symbol=position.get('symbol', ''),
            decision_type=decision_type,
            confidence=DecisionConfidence.HIGH,
            confidence_score=80.0,
            reasoning=[f"Position PnL: {pnl_pct:.2f}%"],
        )

    def _format_tech_for_ai(self, analysis) -> Dict:
        """تحضير التحليل الفني للـ AI"""
        return {
            'htf_trend': analysis.higher_trend if hasattr(analysis, 'higher_trend') else 'unknown',
            'confluence_score': analysis.confluence_score,
            'liquidity_sweeps_count': len(analysis.liquidity_sweeps),
            'order_blocks_count': len(analysis.order_blocks),
            'fvgs_count': len(analysis.fair_value_gaps),
            'trading_bias': analysis.trading_bias,
            'setup_quality': analysis.setup_quality,
        }

    def _news_to_dict(self, news_item) -> Dict:
        """تحويل خبر لـ dict"""
        if isinstance(news_item, dict):
            return news_item
        return {
            'title': getattr(news_item, 'title', ''),
            'impact': getattr(news_item, 'impact_level', 'low'),
            'sentiment': getattr(news_item, 'sentiment', 0),
        }

    def _decision_to_dict(self, decision: TradingDecision) -> Dict:
        """Convert decision to dict"""
        return {
            'decision_id': decision.decision_id,
            'symbol': decision.symbol,
            'decision_type': decision.decision_type.value,
            'confidence': decision.confidence.value,
            'confidence_score': decision.confidence_score,
            'entry_price': decision.entry_price,
            'stop_loss': decision.stop_loss,
            'take_profit': decision.take_profit,
            'position_size_pct': decision.position_size_pct,
            'reasoning': decision.reasoning,
            'warnings': decision.warnings,
            'timestamp': decision.timestamp.isoformat(),
        }

from datetime import timedelta
