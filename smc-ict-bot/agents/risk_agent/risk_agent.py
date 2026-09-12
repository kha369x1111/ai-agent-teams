"""
Risk Management Agent
=====================
Dedicated agent for risk assessment and enforcement.

Responsibilities:
- Real-time portfolio risk monitoring
- Position size validation
- Drawdown protection
- Correlation analysis
- Emergency stop authority
- Risk reporting to other agents
"""

import asyncio
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
from loguru import logger

from agents.shared.base.agent_base import (
    BaseAgent, AgentIdentity, AgentMessage, AgentPriority
)
from agents.shared.communication.message_bus import get_message_bus, Topics
from core.data.binance_connector import BinanceConnector


class RiskLevel(Enum):
    """Overall risk level"""
    SAFE = "safe"               # Normal operation
    CAUTIOUS = "cautious"       # Reduce sizes
    ELEVATED = "elevated"       # New positions need approval
    HIGH = "high"               # No new positions
    CRITICAL = "critical"       # Close all positions
    EMERGENCY = "emergency"     # Immediate shutdown


@dataclass
class RiskState:
    """Current risk state"""
    timestamp: datetime
    risk_level: RiskLevel

    # Account metrics
    current_balance: float
    initial_balance: float
    peak_balance: float
    current_drawdown: float

    # Daily stats
    daily_pnl: float
    daily_pnl_pct: float
    daily_trades: int
    daily_wins: int
    daily_losses: int

    # Open positions
    open_positions: int
    total_exposure: float
    largest_position_pct: float

    # Trade stats
    consecutive_losses: int
    win_rate: float
    profit_factor: float

    # Limits status
    can_open_long: bool
    can_open_short: bool
    max_allowed_size: float  # % of capital

    warnings: List[str]
    violations: List[str]


class RiskManagementAgent(BaseAgent):
    """Dedicated risk management agent with veto power"""

    def __init__(self, connector: BinanceConnector, config: Dict):
        identity = AgentIdentity(
            name="RiskManager",
            role="Monitor and enforce risk limits, has veto power over trades",
            capabilities=[
                "risk_monitoring",
                "position_sizing",
                "drawdown_protection",
                "correlation_analysis",
                "emergency_stop",
            ],
            dependencies=[],
            version="1.0.0",
        )
        super().__init__(identity)

        self.connector = connector
        self.config = config

        # Risk state
        self.risk_state: Optional[RiskState] = None
        self.initial_balance = 0
        self.peak_balance = 0

        # Tracking
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.consecutive_losses = 0
        self.trade_history: List[Dict] = []

        # Risk limits
        self.max_risk_per_trade = config.get('max_risk_per_trade_pct', 1.0)
        self.max_daily_loss_pct = config.get('max_daily_loss_pct', 3.0)
        self.max_drawdown_pct = config.get('max_drawdown_pct', 10.0)
        self.max_open_positions = config.get('max_open_positions', 3)
        self.max_correlated = config.get('max_correlated_positions', 2)

        # Emergency flags
        self.emergency_stop = False
        self.trading_halted = False

        logger.info(f"🛡️ Risk Management Agent ready")

    async def start(self):
        """Start the agent"""
        await super().start()
        self._initialize_balance()

    async def _periodic_tasks(self):
        """Periodic risk monitoring"""
        await self.monitor_risk()

    async def _handle_message(self, message: AgentMessage):
        """Handle incoming messages"""
        self.health_metrics['messages_processed'] += 1

        if message.subject == "validate_trade":
            # Validate a proposed trade
            trade_proposal = message.payload
            approved, reason, modified = await self.validate_trade(trade_proposal)

            await self.send_message(
                receiver=message.sender,
                message_type="response",
                subject="trade_validation",
                payload={
                    'approved': approved,
                    'reason': reason,
                    'modified_proposal': modified,
                },
                correlation_id=message.id,
            )

            # If critical risk, broadcast alert
            if not approved and self.risk_state.risk_level in [RiskLevel.CRITICAL, RiskLevel.EMERGENCY]:
                await self._broadcast_risk_alert(reason)

        elif message.subject == "get_risk_state":
            # Send current risk state
            if self.risk_state:
                await self.send_message(
                    receiver=message.sender,
                    message_type="response",
                    subject="risk_state",
                    payload={'state': self._state_to_dict(self.risk_state)},
                    correlation_id=message.id,
                )

        elif message.subject == "emergency_stop":
            # Activate emergency stop
            await self._activate_emergency_stop(message.payload.get('reason', ''))

        elif message.subject == "resume_trading":
            # Resume after emergency stop
            await self._resume_trading()

    def _initialize_balance(self):
        """Initialize balance tracking"""
        try:
            balance = self.connector.get_balance()
            self.initial_balance = balance.get('total', {}).get('USDT', 0)
            self.peak_balance = self.initial_balance
            logger.info(f"💰 Initial balance: {self.initial_balance:.2f} USDT")
        except Exception as e:
            logger.error(f"Failed to initialize balance: {e}")

    async def monitor_risk(self):
        """Monitor and update risk state"""
        try:
            current_balance = self.connector.get_balance().get('total', {}).get('USDT', 0)

            # Update peak
            if current_balance > self.peak_balance:
                self.peak_balance = current_balance

            # Calculate drawdown
            drawdown = 0
            if self.peak_balance > 0:
                drawdown = ((self.peak_balance - current_balance) / self.peak_balance) * 100

            # Get open positions
            positions = self.connector.get_positions()
            open_count = len(positions)
            total_exposure = sum(
                abs(float(p.get('notional', 0))) for p in positions
            )

            # Determine risk level
            risk_level = self._determine_risk_level(drawdown)

            # Check violations
            violations = []
            if drawdown > self.max_drawdown_pct:
                violations.append(f"Max drawdown exceeded: {drawdown:.2f}%")

            if self.daily_pnl < -self.max_daily_loss_pct:
                violations.append(f"Daily loss limit exceeded: {self.daily_pnl:.2f}%")

            if self.consecutive_losses >= 3:
                violations.append(f"Consecutive losses: {self.consecutive_losses}")

            # Warnings
            warnings = []
            if drawdown > 5:
                warnings.append(f"⚠️ Drawdown: {drawdown:.2f}%")
            if self.consecutive_losses >= 2:
                warnings.append(f"⚠️ {self.consecutive_losses} consecutive losses")

            # Update state
            self.risk_state = RiskState(
                timestamp=datetime.now(),
                risk_level=risk_level,
                current_balance=current_balance,
                initial_balance=self.initial_balance,
                peak_balance=self.peak_balance,
                current_drawdown=drawdown,
                daily_pnl=self.daily_pnl,
                daily_pnl_pct=(self.daily_pnl / self.initial_balance * 100) if self.initial_balance > 0 else 0,
                daily_trades=self.daily_trades,
                daily_wins=self.trade_history.count(lambda t: t.get('pnl', 0) > 0) if hasattr(self.trade_history, 'count') else sum(1 for t in self.trade_history if t.get('pnl', 0) > 0),
                daily_losses=sum(1 for t in self.trade_history if t.get('pnl', 0) < 0),
                open_positions=open_count,
                total_exposure=total_exposure,
                largest_position_pct=(total_exposure / current_balance * 100) if current_balance > 0 else 0,
                consecutive_losses=self.consecutive_losses,
                win_rate=self._calculate_win_rate(),
                profit_factor=self._calculate_profit_factor(),
                can_open_long=risk_level not in [RiskLevel.HIGH, RiskLevel.CRITICAL, RiskLevel.EMERGENCY],
                can_open_short=risk_level not in [RiskLevel.HIGH, RiskLevel.CRITICAL, RiskLevel.EMERGENCY],
                max_allowed_size=self._max_allowed_size(drawdown),
                warnings=warnings,
                violations=violations,
            )

            # Check for emergency conditions
            if risk_level == RiskLevel.EMERGENCY and not self.emergency_stop:
                await self._activate_emergency_stop("Emergency risk level reached")

        except Exception as e:
            logger.error(f"Risk monitoring error: {e}")

    def _determine_risk_level(self, drawdown: float) -> RiskLevel:
        """Determine current risk level"""
        if self.emergency_stop:
            return RiskLevel.EMERGENCY

        if drawdown >= self.max_drawdown_pct * 0.9:
            return RiskLevel.CRITICAL
        elif drawdown >= self.max_drawdown_pct * 0.7:
            return RiskLevel.HIGH
        elif drawdown >= 5:
            return RiskLevel.ELEVATED
        elif drawdown >= 3:
            return RiskLevel.CAUTIOUS
        else:
            return RiskLevel.SAFE

    def _max_allowed_size(self, drawdown: float) -> float:
        """Calculate max allowed position size based on drawdown"""
        if drawdown >= 8:
            return 0
        elif drawdown >= 5:
            return 0.25
        elif drawdown >= 3:
            return 0.5
        else:
            return 1.0

    async def validate_trade(self, proposal: Dict) -> tuple:
        """
        Validate a trade proposal (has VETO POWER)

        Returns:
            (approved, reason, modified_proposal)
        """
        if not self.risk_state:
            await self.monitor_risk()

        # Emergency stop check
        if self.emergency_stop:
            return False, "Emergency stop active", {}

        # Critical risk
        if self.risk_state.risk_level in [RiskLevel.CRITICAL, RiskLevel.EMERGENCY]:
            return False, f"Risk level too high: {self.risk_state.risk_level.value}", {}

        # Daily loss limit
        if self.risk_state.daily_pnl_pct < -self.max_daily_loss_pct:
            return False, "Daily loss limit reached", {}

        # Max open positions
        if self.risk_state.open_positions >= self.max_open_positions:
            return False, f"Max open positions reached: {self.max_open_positions}", {}

        # Position size limit
        proposed_size = proposal.get('position_size_pct', 1.0)
        if proposed_size > self.risk_state.max_allowed_size:
            # Reduce size instead of rejecting
            proposal['position_size_pct'] = self.risk_state.max_allowed_size
            logger.warning(
                f"⚠️ Position size reduced from {proposed_size}% "
                f"to {self.risk_state.max_allowed_size}%"
            )

        # Risk per trade
        risk_pct = proposal.get('risk_pct', 1.0)
        if risk_pct > self.max_risk_per_trade:
            return False, f"Risk per trade too high: {risk_pct}%", {}

        # Correlation check
        if not self._check_correlation(proposal.get('symbol', '')):
            return False, "Too many correlated positions", {}

        # Consecutive losses
        if self.consecutive_losses >= 3:
            return False, "Too many consecutive losses - cooling off", {}

        # Drawdown check
        if self.risk_state.current_drawdown >= self.max_drawdown_pct:
            return False, "Max drawdown reached", {}

        return True, "Trade approved", proposal

    def _check_correlation(self, symbol: str) -> bool:
        """Check if adding this position would exceed correlation limits"""
        # Simplified - in production, calculate actual correlation
        positions = self.connector.get_positions()
        # Count positions in same category (BTC + ETH are correlated)
        crypto_majors = ['BTC', 'ETH']

        if any(symbol.startswith(c) for c in crypto_majors):
            correlated_count = sum(
                1 for p in positions
                if any(p['symbol'].startswith(c) for c in crypto_majors)
            )
            return correlated_count < self.max_correlated

        return True

    def _calculate_win_rate(self) -> float:
        """Calculate win rate"""
        closed = [t for t in self.trade_history if 'pnl' in t]
        if not closed:
            return 0
        wins = sum(1 for t in closed if t['pnl'] > 0)
        return (wins / len(closed)) * 100

    def _calculate_profit_factor(self) -> float:
        """Calculate profit factor"""
        closed = [t for t in self.trade_history if 'pnl' in t]
        if not closed:
            return 0

        gross_profit = sum(t['pnl'] for t in closed if t['pnl'] > 0)
        gross_loss = abs(sum(t['pnl'] for t in closed if t['pnl'] < 0))

        if gross_loss == 0:
            return float('inf')

        return gross_profit / gross_loss

    async def _activate_emergency_stop(self, reason: str):
        """Activate emergency stop"""
        self.emergency_stop = True
        self.trading_halted = True

        logger.critical(f"🚨 EMERGENCY STOP ACTIVATED: {reason}")

        bus = get_message_bus()
        alert = AgentMessage(
            sender=self.agent_id,
            receiver="",
            message_type="event",
            priority=AgentPriority.CRITICAL,
            subject="emergency_stop",
            payload={
                'reason': reason,
                'timestamp': datetime.now().isoformat(),
            },
        )
        await bus.publish(alert, Topics.RISK_ALERT)

    async def _resume_trading(self):
        """Resume trading after emergency stop"""
        self.emergency_stop = False
        self.trading_halted = False
        logger.info("✅ Trading resumed")

    async def _broadcast_risk_alert(self, message: str):
        """Broadcast risk alert to all agents"""
        bus = get_message_bus()
        alert = AgentMessage(
            sender=self.agent_id,
            receiver="",
            message_type="event",
            priority=AgentPriority.HIGH,
            subject="risk_warning",
            payload={
                'message': message,
                'risk_state': self._state_to_dict(self.risk_state) if self.risk_state else {},
            },
        )
        await bus.publish(alert, Topics.RISK_ALERT)

    def _state_to_dict(self, state: RiskState) -> Dict:
        """Convert risk state to dict"""
        return {
            'timestamp': state.timestamp.isoformat(),
            'risk_level': state.risk_level.value,
            'current_balance': state.current_balance,
            'current_drawdown': state.current_drawdown,
            'daily_pnl_pct': state.daily_pnl_pct,
            'open_positions': state.open_positions,
            'consecutive_losses': state.consecutive_losses,
            'win_rate': state.win_rate,
            'profit_factor': state.profit_factor,
            'can_open_long': state.can_open_long,
            'can_open_short': state.can_open_short,
            'max_allowed_size': state.max_allowed_size,
            'warnings': state.warnings,
            'violations': state.violations,
        }
