"""
═══════════════════════════════════════════════════════════════════
📡 WebSocket Real-Time Manager
═══════════════════════════════════════════════════════════════════
اتصال حقيقي بالـ WebSocket لتلقي:
- تحديثات الأسعار لحظياً
- تغيرات Order Book
- تنفيذ الصفقات الكبيرة
- الأخبار العاجلة
═══════════════════════════════════════════════════════════════════
"""

import asyncio
import websockets
import json
from typing import Callable, Dict, List
from datetime import datetime
from dataclasses import dataclass
from loguru import logger


@dataclass
class RealtimeTick:
    """Tick لحظي"""
    symbol: str
    timestamp: datetime
    price: float
    volume: float
    side: str  # 'buy' or 'sell'


class WebSocketManager:
    """مدير اتصالات WebSocket الحقيقية"""

    def __init__(self):
        self.connections: Dict = {}
        self.subscribers: Dict[str, List[Callable]] = {}
        self.is_running = False

        logger.info("📡 WebSocket Manager initialized")

    async def connect_binance(self, symbols: List[str]):
        """اتصال بـ Binance WebSocket"""
        try:
            # Binance WebSocket streams
            streams = []
            for symbol in symbols:
                clean_symbol = symbol.replace('/', '').lower()
                streams.extend([
                    f"{clean_symbol}@kline_4h",
                    f"{clean_symbol}@kline_1h",
                    f"{clean_symbol}@trade",
                    f"{clean_symbol}@depth20@100ms",
                ])

            url = f"wss://stream.binance.com:9443/stream?streams={'/'.join(streams)}"

            self.connections['binance'] = url
            self.is_running = True

            asyncio.create_task(self._binance_listener(url, symbols))
            logger.success(f"✅ Binance WebSocket connected: {len(symbols)} symbols")

        except Exception as e:
            logger.error(f"Binance WebSocket failed: {e}")

    async def _binance_listener(self, url: str, symbols: List[str]):
        """مستمع Binance"""
        while self.is_running:
            try:
                async with websockets.connect(url) as ws:
                    logger.info("🔌 Binance WebSocket connection established")

                    while self.is_running:
                        msg = await ws.recv()
                        data = json.loads(msg)

                        # معالجة البيانات
                        await self._process_binance_message(data, symbols)

            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                await asyncio.sleep(5)  # إعادة الاتصال بعد 5 ثواني

    async def _process_binance_message(self, data: Dict, symbols: List[str]):
        """معالجة رسائل Binance"""
        try:
            if 'stream' in data:
                stream = data['stream']
                payload = data['data']

                # Kline update
                if 'kline' in stream:
                    kline = payload['k']
                    tick = RealtimeTick(
                        symbol=payload['s'],
                        timestamp=datetime.fromtimestamp(kline['t'] / 1000),
                        price=float(kline['c']),
                        volume=float(kline['v']),
                        side='buy' if kline['c'] > kline['o'] else 'sell',
                    )
                    await self._notify_subscribers(f"kline_{payload['s']}", tick)

                # Trade update
                elif 'trade' in stream:
                    tick = RealtimeTick(
                        symbol=payload['s'],
                        timestamp=datetime.fromtimestamp(payload['T'] / 1000),
                        price=float(payload['p']),
                        volume=float(payload['q']),
                        side='buy' if payload['m'] else 'sell',
                    )
                    await self._notify_subscribers(f"trade_{payload['s']}", tick)

                # Depth update
                elif 'depth' in stream:
                    await self._notify_subscribers(f"depth_{payload['s']}", payload)

        except Exception as e:
            logger.error(f"Message processing failed: {e}")

    async def _notify_subscribers(self, event: str, data):
        """إعلام المشتركين"""
        if event in self.subscribers:
            for callback in self.subscribers[event]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(data)
                    else:
                        callback(data)
                except Exception as e:
                    logger.error(f"Subscriber callback failed: {e}")

    def subscribe(self, event: str, callback: Callable):
        """اشترك في حدث"""
        if event not in self.subscribers:
            self.subscribers[event] = []
        self.subscribers[event].append(callback)

    def unsubscribe(self, event: str, callback: Callable):
        """إلغاء الاشتراك"""
        if event in self.subscribers:
            self.subscribers[event].remove(callback)

    async def stop(self):
        """إيقاف كل الاتصالات"""
        self.is_running = False
        self.connections.clear()
        self.subscribers.clear()
        logger.info("WebSocket Manager stopped")
