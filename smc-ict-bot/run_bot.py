"""
Quick Start Script - SMC/ICT Bot
=================================
Simplified entry point for quick testing and deployment.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from loguru import logger

# Load environment
load_dotenv()

from main import SMCICTBot


def print_banner():
    """Print startup banner"""
    banner = """
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║      🚀  SMC/ICT TRADING BOT  📈                        ║
║                                                          ║
║      Smart Money Concepts + Inner Circle Trader          ║
║      Liquidity Sweep Strategy (HTF)                      ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
    """
    print(banner)


def check_prerequisites():
    """Check if everything is set up correctly"""
    errors = []

    # Check Python version
    if sys.version_info < (3, 11):
        errors.append("Python 3.11+ required")

    # Check environment variables
    if not os.getenv('BINANCE_API_KEY'):
        errors.append("BINANCE_API_KEY not set in .env")

    if not os.getenv('BINANCE_API_SECRET'):
        errors.append("BINANCE_API_SECRET not set in .env")

    # Check if .env exists
    if not Path('.env').exists():
        errors.append(".env file not found. Run: cp .env.example .env")

    if errors:
        logger.error("❌ Prerequisites check failed:")
        for error in errors:
            logger.error(f"   - {error}")
        sys.exit(1)

    logger.success("✅ All prerequisites met")


async def run():
    """Main entry point"""
    print_banner()
    check_prerequisites()

    logger.info("🎯 Initializing SMC/ICT Bot...")

    # Create and start bot
    bot = SMCICTBot()

    try:
        await bot.start()
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run())
