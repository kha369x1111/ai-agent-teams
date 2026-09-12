"""
Monitor Agent
=============
Watchdog agent that monitors all other agents and the system.

Responsibilities:
- Monitor agent health (heartbeats)
- Track system performance
- Generate reports
- Send alerts to user
- Detect anomalies
- Coordinate emergency responses
"""

import asyncio
from typing import Dict, List
from datetime import datetime, timedelta
from dataclasses import dataclass
from loguru import logger

from agents.shared.base.agent_base import (
    BaseAgent, AgentIdentity, AgentMessage, AgentPriority
)
from agents.shared.communication.message_bus import get_message_bus, Topics


@dataclass
class SystemReport:
    """Overall system report"""
    timestamp: datetime
    uptime_hours: float

    # Agent health
    total_agents: int
    healthy_agents: int
    degraded_agents: int
    failed_agents: int
    agent_details: Dict

    # Trading performance
    total_trades: int
    win_rate: float
    total_pnl: float
    current_drawdown: float

    # System metrics
    messages_processed: int
    errors_count: int
    avg_response_time: float

    # Status
    system_status: str  # 'healthy', 'degraded', 'critical'


class MonitorAgent(BaseAgent):
    """System-wide monitoring agent"""

    def __init__(self):
        identity = AgentIdentity(
            name="Monitor",
            role="Monitor all agents and system performance",
            capabilities=[
                "health_monitoring",
                "performance_tracking",
                "alert_generation",
                "report_generation",
            ],
            dependencies=[],
            version="1.0.0",
        )
        super().__init__(identity)

        self.system_start_time = datetime.now()
        self.last_alerts: List[Dict] = []
        self.performance_metrics: Dict = {}
        self.message_counter = 0

        logger.info(f"👁️ Monitor Agent ready")

    async def _periodic_tasks(self):
        """Generate periodic reports"""
        if self.health_metrics['messages_processed'] % 100 == 0:
            await self.generate_report()

    async def _handle_message(self, message: AgentMessage):
        """Handle incoming messages"""
        self.health_metrics['messages_processed'] += 1
        self.message_counter += 1

        if message.subject == "get_system_status":
            report = await self.generate_report()
            await self.send_message(
                receiver=message.sender,
                message_type="response",
                subject="system_status",
                payload={'report': self._report_to_dict(report)},
                correlation_id=message.id,
            )

    async def generate_report(self) -> SystemReport:
        """Generate comprehensive system report"""
        bus = get_message_bus()

        # Get all agent health
        agent_details = {}
        healthy = 0
        degraded = 0
        failed = 0

        for agent_id, agent in bus.agents.items():
            health = agent.get_health()
            agent_details[agent.identity.name] = health

            if health['status'] == 'running':
                healthy += 1
            elif health['status'] in ['error', 'stopped']:
                failed += 1
            else:
                degraded += 1

        # Determine system status
        if failed > 0:
            system_status = 'critical'
        elif degraded > 0:
            system_status = 'degraded'
        else:
            system_status = 'healthy'

        uptime = (datetime.now() - self.system_start_time).total_seconds() / 3600

        report = SystemReport(
            timestamp=datetime.now(),
            uptime_hours=uptime,
            total_agents=len(bus.agents),
            healthy_agents=healthy,
            degraded_agents=degraded,
            failed_agents=failed,
            agent_details=agent_details,
            total_trades=self.performance_metrics.get('total_trades', 0),
            win_rate=self.performance_metrics.get('win_rate', 0),
            total_pnl=self.performance_metrics.get('total_pnl', 0),
            current_drawdown=self.performance_metrics.get('current_drawdown', 0),
            messages_processed=self.message_counter,
            errors_count=sum(h.get('errors', 0) for h in agent_details.values()),
            avg_response_time=0,
            system_status=system_status,
        )

        # Log critical status
        if system_status == 'critical':
            logger.critical(f"🚨 SYSTEM CRITICAL: {failed} failed agents")

        return report

    def update_performance(self, metrics: Dict):
        """Update performance metrics"""
        self.performance_metrics.update(metrics)

    def _report_to_dict(self, report: SystemReport) -> Dict:
        return {
            'timestamp': report.timestamp.isoformat(),
            'uptime_hours': report.uptime_hours,
            'total_agents': report.total_agents,
            'healthy_agents': report.healthy_agents,
            'degraded_agents': report.degraded_agents,
            'failed_agents': report.failed_agents,
            'total_trades': report.total_trades,
            'win_rate': report.win_rate,
            'total_pnl': report.total_pnl,
            'current_drawdown': report.current_drawdown,
            'system_status': report.system_status,
        }
