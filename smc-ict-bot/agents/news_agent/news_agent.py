"""
News Intelligence Agent
=======================
Specialized agent for monitoring and analyzing news.
Monitors multiple sources, classifies impact, and broadcasts to other agents.

Sources monitored:
- Crypto news outlets (CoinDesk, CoinTelegraph, The Block)
- Social media (Twitter/X, Reddit)
- Official announcements (SEC, Binance, project blogs)
- Macroeconomic news (Fed, inflation, regulations)

Responsibilities:
- Real-time news monitoring
- Impact classification (low/medium/high/critical)
- Sentiment analysis
- Event correlation with market movements
- Alert on market-moving events
"""

import asyncio
import aiohttp
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass
from loguru import logger

from agents.shared.base.agent_base import (
    BaseAgent, AgentIdentity, AgentMessage, AgentPriority, AgentStatus
)
from agents.shared.communication.message_bus import get_message_bus, Topics


@dataclass
class NewsItem:
    """Single news item with metadata"""
    id: str
    title: str
    content: str
    source: str
    url: str
    timestamp: datetime
    category: str        # 'regulation', 'market', 'tech', 'adoption', 'security'
    sentiment: float     # -1.0 to 1.0
    impact_level: str    # 'low', 'medium', 'high', 'critical'
    affected_symbols: List[str]
    keywords: List[str]


@dataclass
class NewsEvent:
    """Aggregated news event"""
    event_id: str
    main_news: NewsItem
    related_news: List[NewsItem]
    aggregate_sentiment: float
    aggregate_impact: str
    timestamp: datetime
    affected_symbols: List[str]
    trading_recommendation: str  # 'avoid', 'cautious', 'normal', 'opportunity'


class NewsIntelligenceAgent(BaseAgent):
    """Specialized agent for news intelligence"""

    def __init__(self):
        identity = AgentIdentity(
            name="NewsIntelligence",
            role="Monitor and analyze cryptocurrency news from multiple sources",
            capabilities=[
                "news_monitoring",
                "sentiment_analysis",
                "impact_classification",
                "event_detection",
                "source_aggregation",
            ],
            dependencies=[],
            version="1.0.0",
        )
        super().__init__(identity)

        # State
        self.news_buffer: List[NewsItem] = []
        self.recent_events: List[NewsEvent] = []
        self.last_fetch: Dict[str, datetime] = {}
        self.source_status: Dict[str, str] = {}

        # Configuration
        self.fetch_interval = 60  # seconds
        self.buffer_size = 500
        self.impact_keywords = {
            'critical': ['sec', 'ban', 'hack', 'exploit', 'etf approval', 'crash', 'liquidation cascade'],
            'high': ['regulation', 'partnership', 'listing', 'delisting', 'fed', 'interest rate'],
            'medium': ['upgrade', 'announcement', 'conference', 'adoption', 'integration'],
        }

        logger.info(f"📰 News Intelligence Agent ready")

    async def start(self):
        """Start the agent"""
        await super().start()
        # Subscribe to relevant topics
        bus = get_message_bus()
        bus.subscribe(self.agent_id, Topics.NEWS_BREAKING)

    async def _periodic_tasks(self):
        """Periodic news fetching"""
        try:
            # Fetch news from all sources
            news_items = await self._fetch_all_sources()

            # Process each news item
            for item in news_items:
                await self._process_news_item(item)

            # Clean old buffer
            self._cleanup_buffer()

        except Exception as e:
            logger.error(f"News fetch error: {e}")

    async def _handle_message(self, message: AgentMessage):
        """Handle incoming messages"""
        self.health_metrics['messages_processed'] += 1

        if message.subject == "query_news":
            # Respond to news query
            symbol = message.payload.get('symbol', '')
            relevant_news = self._get_relevant_news(symbol)

            await self.send_message(
                receiver=message.sender,
                message_type="response",
                subject="news_response",
                payload={
                    'news': [self._news_to_dict(n) for n in relevant_news[:10]],
                    'count': len(relevant_news),
                },
                correlation_id=message.id,
            )

        elif message.subject == "analyze_event":
            # Analyze specific event
            event_id = message.payload.get('event_id', '')
            event = self._find_event(event_id)
            if event:
                await self.send_message(
                    receiver=message.sender,
                    message_type="response",
                    subject="event_analysis",
                    payload={
                        'event': self._event_to_dict(event),
                        'trading_recommendation': event.trading_recommendation,
                    },
                    correlation_id=message.id,
                )

    async def _fetch_all_sources(self) -> List[NewsItem]:
        """Fetch news from all configured sources"""
        all_news = []

        # Run sources in parallel
        tasks = [
            self._fetch_crypto_news(),
            self._fetch_reddit_posts(),
            self._fetch_twitter_trends(),
            self._fetch_official_announcements(),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, list):
                all_news.extend(result)
            elif isinstance(result, Exception):
                logger.warning(f"Source fetch failed: {result}")

        return all_news

    async def _fetch_crypto_news(self) -> List[NewsItem]:
        """Fetch from crypto news APIs"""
        # In production, use CryptoPanic, CoinDesk API, etc.
        # For demo, return sample data
        try:
            # Simulated API call
            await asyncio.sleep(0.1)
            return []  # Would contain real news items
        except Exception as e:
            logger.error(f"Crypto news fetch failed: {e}")
            return []

    async def _fetch_reddit_posts(self) -> List[NewsItem]:
        """Fetch trending Reddit posts"""
        # Monitor r/CryptoCurrency, r/Bitcoin, r/Ethereum, etc.
        return []

    async def _fetch_twitter_trends(self) -> List[NewsItem]:
        """Fetch Twitter trends and influencer tweets"""
        # Monitor crypto influencers, official accounts
        return []

    async def _fetch_official_announcements(self) -> List[NewsItem]:
        """Fetch official announcements"""
        # SEC, Binance, project official blogs
        return []

    async def _process_news_item(self, item: NewsItem):
        """Process a single news item"""
        try:
            # Classify impact
            item.impact_level = self._classify_impact(item)
            item.sentiment = self._analyze_sentiment(item)
            item.affected_symbols = self._extract_symbols(item)
            item.category = self._categorize(item)
            item.keywords = self._extract_keywords(item)

            # Add to buffer
            self.news_buffer.append(item)
            if len(self.news_buffer) > self.buffer_size:
                self.news_buffer.pop(0)

            # Check if this should trigger an alert
            if item.impact_level in ['high', 'critical']:
                await self._broadcast_high_impact_news(item)

        except Exception as e:
            logger.error(f"News processing error: {e}")

    def _classify_impact(self, item: NewsItem) -> str:
        """Classify news impact level"""
        text = (item.title + " " + item.content).lower()

        # Check for critical keywords
        for keyword in self.impact_keywords['critical']:
            if keyword in text:
                return 'critical'

        # Check for high impact
        for keyword in self.impact_keywords['high']:
            if keyword in text:
                return 'high'

        # Check for medium impact
        for keyword in self.impact_keywords['medium']:
            if keyword in text:
                return 'medium'

        return 'low'

    def _analyze_sentiment(self, item: NewsItem) -> float:
        """Analyze sentiment (simple keyword-based)"""
        positive_words = ['surge', 'rally', 'bullish', 'growth', 'adoption', 'approval', 'breakthrough']
        negative_words = ['crash', 'dump', 'bearish', 'hack', 'ban', 'fear', 'liquidation', 'concern']

        text = (item.title + " " + item.content).lower()

        pos_count = sum(1 for word in positive_words if word in text)
        neg_count = sum(1 for word in negative_words if word in text)

        total = pos_count + neg_count
        if total == 0:
            return 0.0

        sentiment = (pos_count - neg_count) / total
        return max(-1.0, min(1.0, sentiment))

    def _extract_symbols(self, item: NewsItem) -> List[str]:
        """Extract mentioned crypto symbols"""
        # Common patterns: BTC, ETH, $BTC, etc.
        text = item.title + " " + item.content
        pattern = r'\$?([A-Z]{2,5})\b'
        matches = re.findall(pattern, text)

        # Filter common false positives
        false_positives = {'USD', 'THE', 'AND', 'FOR', 'WITH', 'CEO', 'CTO', 'ETF', 'SEC'}
        symbols = [m for m in matches if m not in false_positives]

        return list(set(symbols))

    def _categorize(self, item: NewsItem) -> str:
        """Categorize news"""
        text = (item.title + " " + item.content).lower()

        if any(word in text for word in ['sec', 'regulation', 'law', 'ban']):
            return 'regulation'
        elif any(word in text for word in ['hack', 'exploit', 'security', 'breach']):
            return 'security'
        elif any(word in text for word in ['listing', 'partnership', 'adoption']):
            return 'adoption'
        elif any(word in text for word in ['upgrade', 'fork', 'protocol', 'blockchain']):
            return 'tech'
        else:
            return 'market'

    def _extract_keywords(self, item: NewsItem) -> List[str]:
        """Extract key keywords"""
        # Simple extraction - in production use NLP
        text = (item.title + " " + item.content).lower()
        words = re.findall(r'\b[a-z]{4,}\b', text)

        # Remove common stopwords
        stopwords = {'this', 'that', 'with', 'from', 'have', 'been', 'will', 'their'}
        keywords = [w for w in words if w not in stopwords]

        # Return top 10 most relevant
        return list(set(keywords))[:10]

    async def _broadcast_high_impact_news(self, item: NewsItem):
        """Broadcast high impact news to other agents"""
        bus = get_message_bus()

        message = AgentMessage(
            sender=self.agent_id,
            receiver="",  # Broadcast
            message_type="event",
            priority=AgentPriority.CRITICAL if item.impact_level == 'critical' else AgentPriority.HIGH,
            subject="high_impact_news",
            payload={
                'news_id': item.id,
                'title': item.title,
                'impact': item.impact_level,
                'sentiment': item.sentiment,
                'symbols': item.affected_symbols,
                'category': item.category,
                'url': item.url,
            },
        )

        topic = Topics.NEWS_CRITICAL if item.impact_level == 'critical' else Topics.NEWS_HIGH_IMPACT
        await bus.publish(message, topic)

        logger.warning(
            f"🚨 HIGH IMPACT NEWS: {item.title} "
            f"[{item.impact_level}] [symbols: {item.affected_symbols}]"
        )

    def _get_relevant_news(self, symbol: str, hours: int = 24) -> List[NewsItem]:
        """Get news relevant to a symbol"""
        cutoff = datetime.now() - timedelta(hours=hours)
        relevant = [
            n for n in self.news_buffer
            if n.timestamp > cutoff and (not symbol or symbol in n.affected_symbols)
        ]
        # Sort by impact and recency
        impact_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
        relevant.sort(key=lambda n: (impact_order.get(n.impact_level, 4), -n.timestamp.timestamp()))

        return relevant

    def _cleanup_buffer(self):
        """Remove old news from buffer"""
        cutoff = datetime.now() - timedelta(days=7)
        self.news_buffer = [n for n in self.news_buffer if n.timestamp > cutoff]

    def _find_event(self, event_id: str) -> Optional[NewsEvent]:
        """Find event by ID"""
        for event in self.recent_events:
            if event.event_id == event_id:
                return event
        return None

    def _news_to_dict(self, news: NewsItem) -> Dict:
        """Convert NewsItem to dict"""
        return {
            'id': news.id,
            'title': news.title,
            'source': news.source,
            'timestamp': news.timestamp.isoformat(),
            'sentiment': news.sentiment,
            'impact': news.impact_level,
            'symbols': news.affected_symbols,
            'category': news.category,
        }

    def _event_to_dict(self, event: NewsEvent) -> Dict:
        """Convert NewsEvent to dict"""
        return {
            'event_id': event.event_id,
            'timestamp': event.timestamp.isoformat(),
            'aggregate_sentiment': event.aggregate_sentiment,
            'aggregate_impact': event.aggregate_impact,
            'affected_symbols': event.affected_symbols,
            'recommendation': event.trading_recommendation,
            'news_count': len(event.related_news) + 1,
        }
