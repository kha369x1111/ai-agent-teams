"""
Orchestrator - The Master Coordinator
=====================================
Central coordinator that manages all agents and orchestrates
the complete trading workflow.

Workflow:
1. NewsAgent gathers market intelligence
2. AnalysisAgent performs technical analysis
3. DecisionAgent combines all inputs
4. RiskAgent validates the decision
5. ExecutionAgent executes if approved
6. MonitorAgent tracks everything

The Orchestrator ensures all agents work together harmoniously.
"""

import asyncio
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass
from loguru import logger

from agents.shared.base.agent_base import (
    BaseAgent, AgentIdentity, AgentMessage, AgentPriority
)
from agents.shared.communication.message_bus import get_message_bus, Topics
from agents.news_agent.news_agent import NewsIntelligenceAgent
from agents.analysis_agent.analysis_agent import MarketAnalysisAgent
from agents.decision_agent.decision_agent import DecisionMakingAgent
from agents.risk_agent.risk_agent import RiskManagementAgent
from agents.execution_agent.execution_agent import ExecutionAgent
from agents.monitor_agent.monitor_agent import MonitorAgent
from core.data.binance_connector import BinanceConnector


class TradingOrchestrator:
    """Master orchestrator coordinating all agents"""

    def __init__(self, config: Dict):
        self.config = config

        # Initialize connector
        self.connector = BinanceConnector()

        # Create all agents
        logger.info("🎭 Creating agents...")

        self.news_agent = NewsIntelligenceAgent()
        self.analysis_agent = MarketAnalysisAgent(self.connector)
        self.decision_agent = DecisionMakingAgent()
        self.risk_agent = RiskManagementAgent(self.connector, config.get('risk', {}))
        self.execution_agent = ExecutionAgent(self.connector)
        self.monitor_agent = MonitorAgent()

        self.agents = [
            self.news_agent,
            self.analysis_agent,
            self.decision_agent,
            self.risk_agent,
            self.execution_agent,
            self.monitor_agent,
        ]

        self.is_running = False

        logger.success(f"✅ {len(self.agents)} agents created")

    async def start(self):
        """Start all agents and orchestrator"""
        logger.info("=" * 60)
        logger.info("🚀 STARTING MULTI-AGENT TRADING SYSTEM")
        logger.info("=" * 60)

        # Start message bus
        bus = get_message_bus()
        await bus.start()

        # Register all agents
        for agent in self.agents:
            bus.register_agent(agent)

        # Start all agents
        for agent in self.agents:
            await agent.start()

        # Setup subscriptions
        await self._setup_subscriptions()

        self.is_running = True
        logger.success("✅ All agents started")

        # Start coordination loop
        await self._coordination_loop()

    async def _setup_subscriptions(self):
        """Setup agent subscriptions"""
        bus = get_message_bus()

        # Decision agent subscribes to analysis and news
        bus.subscribe(self.decision_agent.agent_id, Topics.ANALYSIS_COMPLETE)
        bus.subscribe(self.decision_agent.agent_id, Topics.NEWS_HIGH_IMPACT)
        bus.subscribe(self.decision_agent.agent_id, Topics.NEWS_CRITICAL)

        # Execution agent subscribes to approved trades
        bus.subscribe(self.execution_agent.agent_id, Topics.TRADE_APPROVED)

        # Monitor subscribes to everything
        bus.subscribe(self.monitor_agent.agent_id, Topics.RISK_ALERT)
        bus.subscribe(self.monitor_agent.agent_id, Topics.ORDER_FILLED)
        bus.subscribe(self.monitor_agent.agent_id, Topics.SYSTEM_ERROR)

    async def _coordination_loop(self):
        """Main coordination loop"""
        symbols = self.config.get('symbols', ['BTC/USDT', 'ETH/USDT'])
        analysis_interval = self.config.get('analysis_interval', 3600)  # 1 hour

        while self.is_running:
            try:
                logger.info("🔄 Starting analysis cycle...")

                # Process each symbol
                for symbol in symbols:
                    await self._process_symbol(symbol)

                # Sleep until next cycle
                logger.info(f"⏳ Next cycle in {analysis_interval}s")
                await asyncio.sleep(analysis_interval)

            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Coordination error: {e}")
                await asyncio.sleep(60)

    async def _process_symbol(self, symbol: str):
        """
        Complete processing pipeline for a symbol

        Flow:
        News → Analysis → Decision → Risk → Execution
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"📊 Processing {symbol}")
        logger.info(f"{'='*60}")

        try:
            # Step 1: Get news context
            logger.info("Step 1: Gathering news...")
            news_context = await self._get_news_context(symbol)

            # Step 2: Technical analysis
            logger.info("Step 2: Technical analysis...")
            analysis = await self.analysis_agent.analyze_symbol(
                symbol,
                timeframes=['4h', '1d']
            )

            if not analysis:
                logger.warning(f"No analysis for {symbol}")
                return

            # Step 3: Decision making
            logger.info("Step 3: Decision making...")
            decision = await self.decision_agent.make_decision({
                'symbol': symbol,
                'analysis': analysis,
                'news': news_context,
                'risk_state': self.risk_agent.risk_state.__dict__ if self.risk_agent.risk_state else {},
                'market_context': {},
            })

            if not decision:
                logger.info(f"No decision made for {symbol}")
                return

            # Step 4: Risk validation
            logger.info("Step 4: Risk validation...")
            if decision.decision_type.value in ['enter_long', 'enter_short']:
                risk_proposal = {
                    'symbol': symbol,
                    'position_size_pct': decision.position_size_pct,
                    'risk_pct': 1.0,
                }

                approved, reason, modified = await self.risk_agent.validate_trade(risk_proposal)

                if not approved:
                    logger.warning(f"🚫 Trade rejected by Risk Agent: {reason}")
                    return

                # Step 5: Execution
                logger.info("Step 5: Execution...")
                if modified.get('position_size_pct', 0) > 0:
                    decision.position_size_pct = modified['position_size_pct']

                result = await self.execution_agent.execute_decision(
                    self.decision_agent._decision_to_dict(decision)
                )

                logger.success(f"✅ Trade executed: {result.status.value}")

                # Update performance
                self.monitor_agent.update_performance({
                    'total_trades': len(self.execution_agent.execution_history),
                })

        except Exception as e:
            logger.error(f"❌ Symbol processing failed: {e}")

    async def _get_news_context(self, symbol: str) -> List:
        """Get news context for symbol"""
        # Get recent news from news agent's buffer
        recent_news = self.news_agent.news_buffer[-20:]  # Last 20 items

        # Filter for symbol
        relevant = [
            n for n in recent_news
            if symbol.split('/')[0] in n.affected_symbols
        ]

        return relevant

    async def stop(self):
        """Stop all agents gracefully"""
        logger.info("🛑 Stopping orchestrator...")

        self.is_running = False

        # Stop all agents in reverse order
        for agent in reversed(self.agents):
            await agent.stop()

        # Stop message bus
        bus = get_message_bus()
        await bus.stop()

        logger.info("✅ Orchestrator stopped")

    def get_status(self) -> Dict:
        """Get system status"""
        bus = get_message_bus()
        return {
            'running': self.is_running,
            'agents': {
                agent.identity.name: agent.get_health()
                for agent in self.agents
            },
            'bus_stats': bus.get_stats(),
        }
