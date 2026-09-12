"""
Execution Agent
===============
Specialized agent for order execution.

Responsibilities:
- Execute approved trading decisions
- Smart order routing
- Slippage management
- Order monitoring
- Position management
- Execution reporting
"""

import asyncio
import uuid
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
from loguru import logger

from agents.shared.base.agent_base import (
    BaseAgent, AgentIdentity, AgentMessage, AgentPriority
)
from agents.shared.communication.message_bus import get_message_bus, Topics
from core.data.binance_connector import BinanceConnector


class ExecutionStatus(Enum):
    """Execution status"""
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    FAILED = "failed"


@dataclass
class ExecutionResult:
    """Result of an execution"""
    execution_id: str
    decision_id: str
    symbol: str
    side: str
    status: ExecutionStatus
    filled_amount: float
    average_price: float
    fees: float
    slippage: float
    error: Optional[str]
    timestamp: datetime
    order_id: Optional[str] = None


class ExecutionAgent(BaseAgent):
    """Specialized execution agent"""

    def __init__(self, connector: BinanceConnector):
        identity = AgentIdentity(
            name="Execution",
            role="Execute approved trades with smart routing and slippage protection",
            capabilities=[
                "order_execution",
                "smart_routing",
                "slippage_management",
                "position_management",
                "order_monitoring",
            ],
            dependencies=["DecisionMaker", "RiskManager"],
            version="1.0.0",
        )
        super().__init__(identity)

        self.connector = connector
        self.active_orders: Dict[str, Dict] = {}
        self.execution_history: List[ExecutionResult] = []

        # Execution config
        self.max_slippage_pct = 0.1
        self.use_limit_orders = True
        self.order_timeout = 60  # seconds
        self.retry_count = 3

        logger.info(f"⚡ Execution Agent ready")

    async def start(self):
        """Start the agent"""
        await super().start()
        bus = get_message_bus()
        bus.subscribe(self.agent_id, Topics.TRADE_APPROVED)
        bus.subscribe(self.agent_id, Topics.DECISION_MADE)

    async def _periodic_tasks(self):
        """Monitor active orders"""
        await self._monitor_orders()

    async def _handle_message(self, message: AgentMessage):
        """Handle incoming messages"""
        self.health_metrics['messages_processed'] += 1

        if message.subject == "execute_decision":
            # Execute a trading decision
            decision = message.payload.get('decision', {})

            # Risk check
            if message.payload.get('risk_approved', False):
                result = await self.execute_decision(decision)

                await self.send_message(
                    receiver=message.sender,
                    message_type="response",
                    subject="execution_result",
                    payload={'result': self._result_to_dict(result)},
                    correlation_id=message.id,
                )

                # Broadcast execution event
                bus = get_message_bus()
                event = AgentMessage(
                    sender=self.agent_id,
                    receiver="",
                    message_type="event",
                    priority=AgentPriority.HIGH,
                    subject="order_executed",
                    payload=self._result_to_dict(result),
                )
                await bus.publish(event, Topics.ORDER_FILLED)

        elif message.subject == "close_position":
            # Close a specific position
            symbol = message.payload.get('symbol', '')
            reason = message.payload.get('reason', 'manual')

            result = await self.close_position(symbol, reason)

            await self.send_message(
                receiver=message.sender,
                message_type="response",
                subject="position_closed",
                payload={'result': self._result_to_dict(result)},
                correlation_id=message.id,
            )

        elif message.subject == "cancel_order":
            # Cancel an order
            order_id = message.payload.get('order_id', '')
            symbol = message.payload.get('symbol', '')

            success = self.connector.cancel_order(order_id, symbol)

            await self.send_message(
                receiver=message.sender,
                message_type="response",
                subject="order_cancelled",
                payload={'success': success, 'order_id': order_id},
                correlation_id=message.id,
            )

    async def execute_decision(self, decision: Dict) -> ExecutionResult:
        """Execute a trading decision"""
        execution_id = f"EXE_{uuid.uuid4().hex[:8]}"

        try:
            self.status = AgentStatus.THINKING

            symbol = decision.get('symbol', '')
            side = decision.get('decision_type', '')

            if 'enter_long' in side:
                order_side = 'buy'
            elif 'enter_short' in side:
                order_side = 'sell'
            else:
                return self._create_failed_result(
                    execution_id, decision, "Invalid decision type"
                )

            entry_price = decision.get('entry_price')
            stop_loss = decision.get('stop_loss')
            take_profit = decision.get('take_profit')
            size_pct = decision.get('position_size_pct', 1.0)

            if not all([symbol, entry_price, stop_loss, take_profit]):
                return self._create_failed_result(
                    execution_id, decision, "Missing required fields"
                )

            # Calculate position size
            position_size = self._calculate_position_size(
                symbol, entry_price, stop_loss, size_pct
            )

            if position_size <= 0:
                return self._create_failed_result(
                    execution_id, decision, "Invalid position size"
                )

            logger.info(f"⚡ Executing: {order_side.upper()} {position_size} {symbol} @ {entry_price}")

            # Smart execution
            order = await self._smart_execute(
                symbol=symbol,
                side=order_side,
                amount=position_size,
                price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
            )

            if order:
                result = ExecutionResult(
                    execution_id=execution_id,
                    decision_id=decision.get('decision_id', ''),
                    symbol=symbol,
                    side=order_side,
                    status=ExecutionStatus.FILLED,
                    filled_amount=position_size,
                    average_price=float(order.get('average', entry_price)),
                    fees=float(order.get('fee', {}).get('cost', 0)),
                    slippage=self._calculate_slippage(entry_price, float(order.get('average', entry_price))),
                    error=None,
                    timestamp=datetime.now(),
                    order_id=order.get('id', ''),
                )

                self.execution_history.append(result)
                self.status = AgentStatus.RUNNING

                logger.success(f"✅ Executed: {symbol} @ {result.average_price}")

                return result
            else:
                return self._create_failed_result(
                    execution_id, decision, "Order placement failed"
                )

        except Exception as e:
            logger.error(f"❌ Execution failed: {e}")
            self.status = AgentStatus.RUNNING
            return self._create_failed_result(execution_id, decision, str(e))

    async def _smart_execute(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: float,
        stop_loss: float,
        take_profit: float,
    ) -> Optional[Dict]:
        """Smart order execution with retries"""
        for attempt in range(self.retry_count):
            try:
                # Check current market price
                ticker = self.connector.exchange.fetch_ticker(symbol)
                current_price = ticker.get('last', price)

                # Adjust price based on side
                if side == 'buy':
                    limit_price = price * 1.001  # Slightly above target
                else:
                    limit_price = price * 0.999  # Slightly below target

                # Check slippage
                slippage = abs(limit_price - current_price) / current_price * 100

                if slippage > self.max_slippage_pct:
                    logger.warning(
                        f"⚠️ High slippage detected: {slippage:.2f}% "
                        f"(limit: {self.max_slippage_pct}%)"
                    )
                    # Use market order if slippage too high
                    order = self.connector.create_order(
                        symbol=symbol,
                        side=side,
                        order_type='market',
                        amount=amount,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                    )
                else:
                    # Use limit order
                    order = self.connector.create_order(
                        symbol=symbol,
                        side=side,
                        order_type='limit',
                        amount=amount,
                        price=limit_price,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                    )

                return order

            except Exception as e:
                logger.warning(f"Execution attempt {attempt + 1} failed: {e}")
                if attempt < self.retry_count - 1:
                    await asyncio.sleep(2)

        return None

    async def close_position(self, symbol: str, reason: str) -> ExecutionResult:
        """Close an existing position"""
        execution_id = f"CLOSE_{uuid.uuid4().hex[:8]}"

        try:
            order = self.connector.close_position(symbol)

            if order:
                result = ExecutionResult(
                    execution_id=execution_id,
                    decision_id="",
                    symbol=symbol,
                    side=order.get('side', ''),
                    status=ExecutionStatus.FILLED,
                    filled_amount=float(order.get('filled', 0)),
                    average_price=float(order.get('average', 0)),
                    fees=float(order.get('fee', {}).get('cost', 0)),
                    slippage=0,
                    error=None,
                    timestamp=datetime.now(),
                    order_id=order.get('id', ''),
                )

                self.execution_history.append(result)
                logger.info(f"✅ Position closed: {symbol} (reason: {reason})")
                return result

            return self._create_failed_result(execution_id, {'symbol': symbol}, "Close failed")

        except Exception as e:
            logger.error(f"❌ Close position failed: {e}")
            return self._create_failed_result(execution_id, {'symbol': symbol}, str(e))

    def _calculate_position_size(
        self,
        symbol: str,
        entry_price: float,
        stop_loss: float,
        size_pct: float
    ) -> float:
        """Calculate position size"""
        try:
            balance = self.connector.get_balance().get('free', {}).get('USDT', 0)

            if balance <= 0:
                return 0

            # Risk amount
            risk_pct = self.max_risk_per_trade_pct * size_pct
            risk_amount = balance * (risk_pct / 100)

            # Position size based on stop distance
            price_diff = abs(entry_price - stop_loss)
            if price_diff <= 0:
                return 0

            position_size = risk_amount / price_diff

            # Round to precision
            market = self.connector.exchange.market(symbol)
            precision = market.get('precision', {}).get('amount', 8)
            position_size = round(position_size, precision)

            return position_size

        except Exception as e:
            logger.error(f"Position size calculation failed: {e}")
            return 0

    def _calculate_slippage(self, expected: float, actual: float) -> float:
        """Calculate slippage percentage"""
        if expected <= 0:
            return 0
        return abs(actual - expected) / expected * 100

    async def _monitor_orders(self):
        """Monitor active orders"""
        # Check for filled orders, cancellations, etc.
        pass

    def _create_failed_result(
        self,
        execution_id: str,
        decision: Dict,
        error: str
    ) -> ExecutionResult:
        """Create a failed execution result"""
        return ExecutionResult(
            execution_id=execution_id,
            decision_id=decision.get('decision_id', ''),
            symbol=decision.get('symbol', ''),
            side='',
            status=ExecutionStatus.FAILED,
            filled_amount=0,
            average_price=0,
            fees=0,
            slippage=0,
            error=error,
            timestamp=datetime.now(),
        )

    def _result_to_dict(self, result: ExecutionResult) -> Dict:
        """Convert result to dict"""
        return {
            'execution_id': result.execution_id,
            'decision_id': result.decision_id,
            'symbol': result.symbol,
            'side': result.side,
            'status': result.status.value,
            'filled_amount': result.filled_amount,
            'average_price': result.average_price,
            'fees': result.fees,
            'slippage': result.slippage,
            'error': result.error,
            'timestamp': result.timestamp.isoformat(),
            'order_id': result.order_id,
        }
