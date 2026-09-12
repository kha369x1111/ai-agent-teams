"""
Message Bus - Inter-Agent Communication System
===============================================
Central nervous system for agent communication.
Uses publish-subscribe pattern with priority routing.
"""

import asyncio
from typing import Dict, List, Optional, Callable, Set
from collections import defaultdict
from datetime import datetime
from loguru import logger

from agents.shared.base.agent_base import AgentMessage, AgentPriority, BaseAgent


class MessageBus:
    """Central message broker for inter-agent communication"""

    def __init__(self):
        self.agents: Dict[str, BaseAgent] = {}
        self.routes: Dict[str, List[str]] = defaultdict(list)  # topic -> subscribers
        self.message_history: List[AgentMessage] = []
        self.history_limit = 1000
        self._running = False
        self._lock = asyncio.Lock()

        logger.info("🚌 Message Bus initialized")

    def register_agent(self, agent: BaseAgent):
        """Register an agent with the bus"""
        self.agents[agent.agent_id] = agent
        logger.debug(f"Agent registered: {agent.identity.name} ({agent.agent_id})")

    def subscribe(self, agent_id: str, topic: str):
        """Subscribe agent to a topic"""
        if agent_id not in self.routes[topic]:
            self.routes[topic].append(agent_id)
            logger.debug(f"Agent {agent_id} subscribed to '{topic}'")

    def unsubscribe(self, agent_id: str, topic: str):
        """Unsubscribe agent from topic"""
        if agent_id in self.routes[topic]:
            self.routes[topic].remove(agent_id)

    async def publish(self, message: AgentMessage, topic: Optional[str] = None):
        """Publish message to topic subscribers or specific agent"""
        async with self._lock:
            # Store in history
            self.message_history.append(message)
            if len(self.message_history) > self.history_limit:
                self.message_history.pop(0)

        # Direct message
        if message.receiver and message.receiver in self.agents:
            await self.agents[message.receiver].receive_message(message)
            return

        # Topic-based routing
        if topic:
            subscribers = self.routes.get(topic, [])
            for agent_id in subscribers:
                if agent_id in self.agents:
                    # Create copy for each subscriber
                    msg_copy = AgentMessage(**message.__dict__)
                    msg_copy.receiver = agent_id
                    await self.agents[agent_id].receive_message(msg_copy)

    async def start(self):
        """Start the message bus"""
        self._running = True
        logger.success("✅ Message Bus started")

    async def stop(self):
        """Stop the message bus"""
        self._running = False
        logger.info("🛑 Message Bus stopped")

    def get_stats(self) -> Dict:
        """Get bus statistics"""
        return {
            'registered_agents': len(self.agents),
            'topics': len(self.routes),
            'messages_in_history': len(self.message_history),
            'total_subscriptions': sum(len(subs) for subs in self.routes.values()),
        }


# Topics for different event types
class Topics:
    """Standard topic names"""
    # Market data topics
    MARKET_DATA_UPDATE = "market.data.update"
    NEW_CANDLE = "market.candle.new"

    # News topics
    NEWS_BREAKING = "news.breaking"
    NEWS_HIGH_IMPACT = "news.high_impact"

    # Analysis topics
    ANALYSIS_COMPLETE = "analysis.complete"
    SIGNAL_DETECTED = "analysis.signal"

    # Decision topics
    DECISION_MADE = "decision.made"
    TRADE_APPROVED = "decision.approved"
    TRADE_REJECTED = "decision.rejected"

    # Risk topics
    RISK_ALERT = "risk.alert"
    DRAWDOWN_WARNING = "risk.drawdown"
    POSITION_LIMIT_HIT = "risk.limit"

    # Execution topics
    ORDER_PLACED = "execution.placed"
    ORDER_FILLED = "execution.filled"
    ORDER_CANCELLED = "execution.cancelled"

    # Monitoring topics
    SYSTEM_STATUS = "system.status"
    PERFORMANCE_UPDATE = "performance.update"
    ERROR_REPORT = "system.error"


# Global message bus instance
_message_bus = None

def get_message_bus() -> MessageBus:
    """Get singleton message bus"""
    global _message_bus
    if _message_bus is None:
        _message_bus = MessageBus()
    return _message_bus
