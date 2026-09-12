"""
Base Agent Class
================
Foundation for all specialized agents in the system.
Each agent has:
- Unique identity
- Specialized role
- Communication interface
- Memory system
- Health monitoring
"""

import asyncio
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
from loguru import logger


class AgentStatus(Enum):
    """Agent operational status"""
    IDLE = "idle"               # Waiting for tasks
    RUNNING = "running"         # Active
    THINKING = "thinking"       # Processing
    WAITING = "waiting"         # Waiting for data/input
    ERROR = "error"             # Error state
    STOPPED = "stopped"         # Stopped
    DEGRADED = "degraded"       # Partial functionality


class AgentPriority(Enum):
    """Message/Task priority levels"""
    CRITICAL = 1    # Must be processed immediately
    HIGH = 2        # Important, process soon
    MEDIUM = 3      # Normal priority
    LOW = 4         # Process when available


@dataclass
class AgentMessage:
    """Standard message format between agents"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sender: str = ""
    receiver: str = ""
    message_type: str = ""      # 'request', 'response', 'event', 'alert'
    priority: AgentPriority = AgentPriority.MEDIUM
    subject: str = ""
    payload: Dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    requires_response: bool = False
    correlation_id: Optional[str] = None  # For tracking conversations
    ttl: Optional[int] = None  # Time to live in seconds


@dataclass
class AgentIdentity:
    """Agent's unique identity and capabilities"""
    name: str
    role: str
    capabilities: List[str]
    dependencies: List[str] = field(default_factory=list)  # Other agents it needs
    version: str = "1.0.0"


class BaseAgent(ABC):
    """Abstract base class for all agents"""

    def __init__(self, identity: AgentIdentity):
        self.identity = identity
        self.agent_id = f"{identity.name}_{str(uuid.uuid4())[:8]}"
        self.status = AgentStatus.IDLE
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self.outbox: asyncio.Queue = asyncio.Queue()
        self.memory: Dict[str, Any] = {}  # Simple in-memory store
        self.subscribers: List[str] = []  # Agent IDs subscribed to events
        self.health_metrics: Dict = {
            'messages_processed': 0,
            'errors': 0,
            'uptime_start': datetime.now(),
            'last_heartbeat': datetime.now(),
        }
        self._running = False
        self._task: Optional[asyncio.Task] = None

        logger.info(f"🤖 Agent created: {self.identity.name} ({self.identity.role})")

    # ==================== Lifecycle ====================

    async def start(self):
        """Start the agent"""
        if self._running:
            logger.warning(f"Agent {self.identity.name} already running")
            return

        self._running = True
        self.status = AgentStatus.RUNNING
        self._task = asyncio.create_task(self._main_loop())
        logger.success(f"✅ Agent started: {self.identity.name}")

    async def stop(self):
        """Stop the agent gracefully"""
        logger.info(f"🛑 Stopping agent: {self.identity.name}")
        self._running = False
        self.status = AgentStatus.STOPPED
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info(f"Agent stopped: {self.identity.name}")

    async def _main_loop(self):
        """Main processing loop"""
        while self._running:
            try:
                # Update heartbeat
                self.health_metrics['last_heartbeat'] = datetime.now()

                # Process messages
                try:
                    message = await asyncio.wait_for(
                        self.message_queue.get(),
                        timeout=1.0
                    )
                    await self._handle_message(message)
                except asyncio.TimeoutError:
                    # No messages, do periodic tasks
                    await self._periodic_tasks()

            except Exception as e:
                logger.error(f"❌ Error in {self.identity.name}: {e}")
                self.health_metrics['errors'] += 1
                self.status = AgentStatus.ERROR
                await asyncio.sleep(5)
                self.status = AgentStatus.RUNNING

    async def _periodic_tasks(self):
        """Tasks to run periodically (override in subclasses)"""
        pass

    @abstractmethod
    async def _handle_message(self, message: AgentMessage):
        """Handle incoming message (must be implemented)"""
        pass

    # ==================== Communication ====================

    async def send_message(
        self,
        receiver: str,
        message_type: str,
        subject: str,
        payload: Dict,
        priority: AgentPriority = AgentPriority.MEDIUM,
        requires_response: bool = False,
        correlation_id: Optional[str] = None
    ) -> AgentMessage:
        """Send message to another agent"""
        message = AgentMessage(
            sender=self.agent_id,
            receiver=receiver,
            message_type=message_type,
            priority=priority,
            subject=subject,
            payload=payload,
            requires_response=requires_response,
            correlation_id=correlation_id,
        )

        await self.outbox.put(message)
        logger.debug(
            f"📤 [{self.identity.name}] → [{receiver}]: {subject}"
        )
        return message

    async def receive_message(self, message: AgentMessage):
        """Receive message from another agent"""
        await self.message_queue.put(message)
        logger.debug(
            f"📥 [{self.identity.name}] ← [{message.sender}]: {message.subject}"
        )

    async def broadcast(
        self,
        subject: str,
        payload: Dict,
        message_type: str = "event"
    ):
        """Broadcast message to all subscribers"""
        for subscriber in self.subscribers:
            await self.send_message(
                receiver=subscriber,
                message_type=message_type,
                subject=subject,
                payload=payload,
            )

    # ==================== Memory ====================

    def remember(self, key: str, value: Any, ttl: Optional[int] = None):
        """Store value in memory"""
        self.memory[key] = {
            'value': value,
            'timestamp': datetime.now(),
            'ttl': ttl,
        }

    def recall(self, key: str) -> Optional[Any]:
        """Retrieve value from memory"""
        if key not in self.memory:
            return None

        entry = self.memory[key]
        if entry['ttl']:
            age = (datetime.now() - entry['timestamp']).total_seconds()
            if age > entry['ttl']:
                del self.memory[key]
                return None

        return entry['value']

    def forget(self, key: str):
        """Remove from memory"""
        if key in self.memory:
            del self.memory[key]

    # ==================== Health & Monitoring ====================

    def get_health(self) -> Dict:
        """Get agent health status"""
        uptime = (datetime.now() - self.health_metrics['uptime_start']).total_seconds()
        return {
            'agent_id': self.agent_id,
            'name': self.identity.name,
            'role': self.identity.role,
            'status': self.status.value,
            'uptime_seconds': uptime,
            'messages_processed': self.health_metrics['messages_processed'],
            'errors': self.health_metrics['errors'],
            'queue_size': self.message_queue.qsize(),
            'memory_entries': len(self.memory),
            'last_heartbeat': self.health_metrics['last_heartbeat'].isoformat(),
        }

    def update_heartbeat(self):
        """Update last heartbeat"""
        self.health_metrics['last_heartbeat'] = datetime.now()

    def __repr__(self):
        return f"<Agent {self.identity.name} [{self.status.value}]>"
