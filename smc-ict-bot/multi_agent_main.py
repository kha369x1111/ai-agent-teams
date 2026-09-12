"""
Multi-Agent SMC/ICT Trading System - Main Entry Point
======================================================
Starts the complete multi-agent trading system.
"""

import asyncio
import sys
import os
import signal
from pathlib import Path
from dotenv import load_dotenv
from loguru import logger

# Add project to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Load environment
load_dotenv()

from agents.orchestrator.orchestrator import TradingOrchestrator


def print_banner():
    banner = """
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║         🧠 MULTI-AGENT SMC/ICT TRADING SYSTEM 🧠           ║
║                                                              ║
║   6 Specialized Agents Working Together:                    ║
║   📰 News Intelligence                                       ║
║   📊 Market Analysis                                         ║
║   🧠 Decision Maker                                          ║
║   🛡️ Risk Manager (with VETO power)                        ║
║   ⚡ Execution                                                ║
║   👁️ Monitor                                                  ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)


async def run():
    """Main entry point"""
    print_banner()

    # Configuration
    config = {
        'symbols': ['BTC/USDT', 'ETH/USDT', 'SOL/USDT'],
        'analysis_interval': 3600,  # 1 hour

        # Risk configuration
        'risk': {
            'max_risk_per_trade_pct': 1.0,
            'max_daily_loss_pct': 3.0,
            'max_drawdown_pct': 10.0,
            'max_open_positions': 3,
            'max_correlated_positions': 2,
        }
    }

    # Create and start orchestrator
    orchestrator = TradingOrchestrator(config)

    # Setup signal handlers
    def shutdown_handler(sig, frame):
        logger.info("🛑 Shutdown signal received")
        asyncio.create_task(orchestrator.stop())

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    try:
        await orchestrator.start()
    except KeyboardInterrupt:
        await orchestrator.stop()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        await orchestrator.stop()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run())
