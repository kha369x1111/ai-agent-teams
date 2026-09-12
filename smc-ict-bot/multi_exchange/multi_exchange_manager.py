"""
═══════════════════════════════════════════════════════════════════
🔌 Multi-Exchange Manager
═══════════════════════════════════════════════════════════════════
يدعم عدة منصات: Binance, Bybit, OKX
يوفر واجهة موحدة للتداول عبر كل المنصات
═══════════════════════════════════════════════════════════════════
"""

import ccxt.async_support as ccxt
import asyncio
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum
from loguru import logger


class ExchangeType(Enum):
    """المنصات المدعومة"""
    BINANCE = "binance"
    BYBIT = "bybit"
    OKX = "okx"
    KUCOIN = "kucoin"


@dataclass
class ExchangeCredentials:
    """مفاتيح المنصة"""
    exchange_type: ExchangeType
    api_key: str
    api_secret: str
    testnet: bool = True
    passphrase: Optional[str] = None  # for OKX


class MultiExchangeManager:
    """مدير متعدد المنصات"""

    def __init__(self):
        self.exchanges: Dict[ExchangeType, ccxt.Exchange] = {}
        self.initialized = False

        logger.info("🔌 Multi-Exchange Manager initialized")

    async def add_exchange(self, credentials: ExchangeCredentials):
        """إضافة منصة"""
        try:
            exchange_class = getattr(ccxt, credentials.exchange_type.value)
            config = {
                'apiKey': credentials.api_key,
                'secret': credentials.api_secret,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'future',
                    'adjustForTimeDifference': True,
                }
            }

            # OKX يحتاج passphrase
            if credentials.exchange_type == ExchangeType.OKX:
                config['password'] = credentials.passphrase

            exchange = exchange_class(config)

            # Testnet mode
            if credentials.testnet:
                if credentials.exchange_type == ExchangeType.BINANCE:
                    exchange.set_sandbox_mode(True)
                elif credentials.exchange_type == ExchangeType.BYBIT:
                    exchange.urls['api'] = 'https://api-testnet.bybit.com'
                elif credentials.exchange_type == ExchangeType.OKX:
                    exchange.set_sandbox_mode(True)

            # Test connection
            await exchange.fetch_balance()

            self.exchanges[credentials.exchange_type] = exchange
            logger.success(f"✅ {credentials.exchange_type.value} connected")

        except Exception as e:
            logger.error(f"❌ Failed to connect to {credentials.exchange_type.value}: {e}")

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "4h",
        limit: int = 500,
        exchange_type: ExchangeType = ExchangeType.BINANCE,
    ) -> Optional[Dict]:
        """جلب البيانات من منصة محددة"""
        try:
            if exchange_type not in self.exchanges:
                logger.error(f"{exchange_type.value} not initialized")
                return None

            exchange = self.exchanges[exchange_type]
            ohlcv = await exchange.fetch_ohlcv(symbol, timeframe, limit=limit)

            return {'symbol': symbol, 'timeframe': timeframe, 'data': ohlcv}

        except Exception as e:
            logger.error(f"Failed to fetch OHLCV from {exchange_type.value}: {e}")
            return None

    async def get_best_price(self, symbol: str) -> Dict:
        """الحصول على أفضل سعر من كل المنصات"""
        prices = {}

        for ex_type, exchange in self.exchanges.items():
            try:
                ticker = await exchange.fetch_ticker(symbol)
                prices[ex_type.value] = {
                    'bid': ticker.get('bid'),
                    'ask': ticker.get('ask'),
                    'last': ticker.get('last'),
                    'volume': ticker.get('quoteVolume'),
                }
            except Exception as e:
                logger.warning(f"Failed to fetch from {ex_type.value}: {e}")

        return prices

    async def execute_on_best_exchange(
        self,
        symbol: str,
        side: str,
        amount: float,
        order_type: str = 'limit',
        price: Optional[float] = None,
    ) -> Optional[Dict]:
        """تنفيذ على المنصة بأفضل سعر"""
        best_exchange = None
        best_price = float('inf') if side == 'buy' else 0

        # البحث عن أفضل سعر
        for ex_type, exchange in self.exchanges.items():
            try:
                ticker = await exchange.fetch_ticker(symbol)
                current_price = ticker.get('ask') if side == 'buy' else ticker.get('bid')

                if (side == 'buy' and current_price < best_price) or \
                   (side == 'sell' and current_price > best_price):
                    best_price = current_price
                    best_exchange = ex_type

            except Exception as e:
                logger.warning(f"Price check failed on {ex_type.value}: {e}")

        # التنفيذ
        if best_exchange:
            try:
                exchange = self.exchanges[best_exchange]

                if order_type == 'market':
                    order = await exchange.create_market_order(symbol, side, amount)
                else:
                    order = await exchange.create_limit_order(symbol, side, amount, price)

                logger.success(
                    f"✅ Order executed on {best_exchange.value}: "
                    f"{side} {amount} {symbol} @ {order.get('average', price)}"
                )

                return order

            except Exception as e:
                logger.error(f"Execution failed on {best_exchange.value}: {e}")

        return None

    async def get_arbitrage_opportunities(self, symbol: str) -> List[Dict]:
        """اكتشاف فرص Arbitrage"""
        prices = await self.get_best_price(symbol)
        opportunities = []

        exchange_names = list(prices.keys())

        for i in range(len(exchange_names)):
            for j in range(i+1, len(exchange_names)):
                ex1, ex2 = exchange_names[i], exchange_names[j]
                p1 = prices[ex1].get('ask', 0)
                p2 = prices[ex2].get('bid', 0)

                if p1 > 0 and p2 > 0:
                    spread = ((p2 - p1) / p1) * 100

                    if spread > 0.1:  # أكثر من 0.1%
                        opportunities.append({
                            'buy_from': ex1,
                            'sell_to': ex2,
                            'spread_pct': spread,
                            'buy_price': p1,
                            'sell_price': p2,
                        })

        return opportunities

    async def close_all(self):
        """إغلاق كل الاتصالات"""
        for exchange in self.exchanges.values():
            await exchange.close()

        self.exchanges.clear()
        logger.info("All exchange connections closed")
