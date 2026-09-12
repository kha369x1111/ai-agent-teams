"""
═══════════════════════════════════════════════════════════════════
🧠 AI Brain - ربط نماذج الذكاء الاصطناعي
═══════════════════════════════════════════════════════════════════
يدعم عدة نماذج AI:
- Google Gemini (مجاني) ⭐
- OpenAI GPT (مدفوع)
- Anthropic Claude (مدفوع)
- Ollama (محلي مجاني)
- OpenRouter (متعدد)

الاستخدام:
- تحليل الأخبار بعمق
- تقييم السياقات السوقية المعقدة
- شرح القرارات
- استراتيجيات متقدمة
- توليد رؤى ذكية
═══════════════════════════════════════════════════════════════════
"""

import os
import asyncio
import json
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
from loguru import logger

# مكتبات AI
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import anthropic
    CLAUDE_AVAILABLE = True
except ImportError:
    CLAUDE_AVAILABLE = False

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False


@dataclass
class AIAnalysis:
    """تحليل AI"""
    raw_response: str
    decision: str  # 'long', 'short', 'wait'
    confidence: float  # 0.0 - 1.0
    reasoning: str
    key_factors: List[str]
    warnings: List[str]
    suggested_entry: Optional[float] = None
    suggested_sl: Optional[float] = None
    suggested_tp: Optional[float] = None


class AIBrain:
    """دمج نماذج الذكاء الاصطناعي في النظام"""

    def __init__(self):
        self.provider = os.getenv('AI_PROVIDER', 'gemini')  # الافتراضي: Gemini
        self.model = None
        self.is_available = False

        logger.info(f"🧠 Initializing AI Brain with provider: {self.provider}")

        self._initialize_provider()

    def _initialize_provider(self):
        """تهيئة مزود AI"""
        try:
            if self.provider == 'gemini':
                self._init_gemini()
            elif self.provider == 'openai':
                self._init_openai()
            elif self.provider == 'claude':
                self._init_claude()
            elif self.provider == 'ollama':
                self._init_ollama()
            else:
                logger.warning(f"Unknown provider: {self.provider}")
        except Exception as e:
            logger.error(f"Failed to init {self.provider}: {e}")
            self.is_available = False

    def _init_gemini(self):
        """تهيئة Google Gemini (مجاني)"""
        if not GEMINI_AVAILABLE:
            logger.warning("google-generativeai not installed")
            return

        api_key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
        if not api_key:
            logger.warning("GEMINI_API_KEY not set")
            return

        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        self.is_available = True
        logger.success("✅ Gemini AI initialized")

    def _init_openai(self):
        """تهيئة OpenAI"""
        if not OPENAI_AVAILABLE:
            return

        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            return

        openai.api_key = api_key
        self.model = 'gpt-4' if os.getenv('USE_GPT4') else 'gpt-3.5-turbo'
        self.is_available = True
        logger.success("✅ OpenAI initialized")

    def _init_claude(self):
        """تهيئة Claude"""
        if not CLAUDE_AVAILABLE:
            return

        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            return

        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = 'claude-3-haiku-20240307'
        self.is_available = True
        logger.success("✅ Claude initialized")

    def _init_ollama(self):
        """تهيئة Ollama (محلي مجاني)"""
        if not OLLAMA_AVAILABLE:
            return

        self.model = os.getenv('OLLAMA_MODEL', 'llama3')
        self.is_available = True
        logger.success("✅ Ollama initialized (local)")

    async def analyze_market_context(
        self,
        symbol: str,
        technical_analysis: Dict,
        news_context: List[Dict],
        current_price: float,
        recent_trades: List[Dict] = None,
    ) -> Optional[AIAnalysis]:
        """
        تحليل ذكي للسوق باستخدام AI

        يجمع بين:
        - التحليل الفني
        - الأخبار
        - التاريخ الشخصي
        - السياق السوقي
        """
        if not self.is_available:
            return None

        # بناء الـ prompt
        prompt = self._build_analysis_prompt(
            symbol, technical_analysis, news_context,
            current_price, recent_trades
        )

        try:
            # استدعاء AI
            if self.provider == 'gemini':
                response = await self._call_gemini(prompt)
            elif self.provider == 'openai':
                response = await self._call_openai(prompt)
            elif self.provider == 'claude':
                response = await self._call_claude(prompt)
            elif self.provider == 'ollama':
                response = await self._call_ollama(prompt)
            else:
                return None

            # تحليل الاستجابة
            return self._parse_response(response)

        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
            return None

    def _build_analysis_prompt(
        self,
        symbol: str,
        technical: Dict,
        news: List[Dict],
        price: float,
        trades: List[Dict] = None,
    ) -> str:
        """بناء prompt احترافي للـ AI"""

        # ملخص الأخبار
        news_summary = "لا توجد أخبار مهمة"
        if news:
            high_impact = [n for n in news if n.get('impact') in ['high', 'critical']]
            if high_impact:
                news_summary = "\n".join([
                    f"- [{n.get('impact', 'unknown').upper()}] {n.get('title', '')} "
                    f"(sentiment: {n.get('sentiment', 0):.2f})"
                    for n in high_impact[:5]
                ])

        # ملخص التحليل الفني
        tech_summary = f"""
- HTF Trend: {technical.get('htf_trend', 'unknown')}
- Confluence Score: {technical.get('confluence_score', 0)}/100
- Liquidity Sweeps: {technical.get('liquidity_sweeps_count', 0)}
- Order Blocks: {technical.get('order_blocks_count', 0)}
- FVGs: {technical.get('fvgs_count', 0)}
- Trading Bias: {technical.get('trading_bias', 'neutral')}
- Setup Quality: {technical.get('setup_quality', 'C')}
"""

        # ملخص الأداء الشخصي
        perf_summary = "لا توجد صفقات سابقة"
        if trades:
            wins = sum(1 for t in trades if t.get('pnl', 0) > 0)
            total = len(trades)
            win_rate = (wins / total * 100) if total > 0 else 0
            avg_pnl = sum(t.get('pnl_pct', 0) for t in trades) / total if total > 0 else 0

            perf_summary = f"""
- Total Trades: {total}
- Win Rate: {win_rate:.1f}%
- Average PnL: {avg_pnl:.2f}%
- Recent Win Rate: {win_rate:.1f}%
"""

        prompt = f"""You are a professional cryptocurrency trader using Smart Money Concepts (SMC) and ICT methodology.

Analyze this trading opportunity and provide your expert opinion.

═══════════════════════════════════════════
📊 MARKET CONTEXT
═══════════════════════════════════════════
Symbol: {symbol}
Current Price: ${price}
Time: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}

═══════════════════════════════════════════
📈 TECHNICAL ANALYSIS (SMC/ICT)
═══════════════════════════════════════════
{tech_summary}

═══════════════════════════════════════════
📰 HIGH-IMPACT NEWS
═══════════════════════════════════════════
{news_summary}

═══════════════════════════════════════════
📊 HISTORICAL PERFORMANCE
═══════════════════════════════════════════
{perf_summary}

═══════════════════════════════════════════
🎯 YOUR TASK
═══════════════════════════════════════════

Based on ALL the above information, analyze this trading opportunity.

Provide your response in EXACTLY this JSON format:

{{
  "decision": "long" or "short" or "wait",
  "confidence": 0.0 to 1.0,
  "reasoning": "Brief explanation (2-3 sentences)",
  "key_factors": ["factor 1", "factor 2", "factor 3"],
  "warnings": ["warning 1", "warning 2"],
  "suggested_entry": price or null,
  "suggested_sl": price or null,
  "suggested_tp": price or null
}}

CRITICAL RULES:
1. Be honest - if setup is weak, say "wait"
2. Consider HTF trend alignment
3. Liquidity sweep + OB/FVG confluence is crucial
4. High-impact news can override technical signals
5. Don't trade if confidence < 0.65

Respond ONLY with the JSON, nothing else."""

        return prompt

    async def _call_gemini(self, prompt: str) -> str:
        """استدعاء Gemini"""
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.model.generate_content(prompt)
        )
        return response.text

    async def _call_openai(self, prompt: str) -> str:
        """استدعاء OpenAI"""
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: openai.ChatCompletion.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )
        )
        return response.choices[0].message.content

    async def _call_claude(self, prompt: str) -> str:
        """استدعاء Claude"""
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}]
            )
        )
        return response.content[0].text

    async def _call_ollama(self, prompt: str) -> str:
        """استدعاء Ollama محلي"""
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: ollama.chat(
                model=self.model,
                messages=[{'role': 'user', 'content': prompt}]
            )
        )
        return response['message']['content']

    def _parse_response(self, response: str) -> AIAnalysis:
        """تحليل استجابة AI"""
        try:
            # تنظيف الاستجابة
            response = response.strip()

            # البحث عن JSON
            if '```json' in response:
                response = response.split('```json')[1].split('```')[0]
            elif '```' in response:
                response = response.split('```')[1].split('```')[0]

            data = json.loads(response)

            return AIAnalysis(
                raw_response=response,
                decision=data.get('decision', 'wait'),
                confidence=float(data.get('confidence', 0.5)),
                reasoning=data.get('reasoning', ''),
                key_factors=data.get('key_factors', []),
                warnings=data.get('warnings', []),
                suggested_entry=data.get('suggested_entry'),
                suggested_sl=data.get('suggested_sl'),
                suggested_tp=data.get('suggested_tp'),
            )

        except Exception as e:
            logger.error(f"Failed to parse AI response: {e}")
            logger.debug(f"Response was: {response[:500]}")
            return None

    async def explain_decision(
        self,
        decision: Dict,
        market_data: Dict,
    ) -> str:
        """يشرح القرار بلغة بشرية"""
        if not self.is_available:
            return "AI explanation not available"

        prompt = f"""Explain this trading decision in 2-3 sentences in clear, simple language:

Decision: {decision.get('decision_type', 'unknown')}
Symbol: {decision.get('symbol', 'unknown')}
Reasoning: {', '.join(decision.get('reasons', []))}
Warnings: {', '.join(decision.get('warnings', []))}

Keep it under 100 words."""

        try:
            if self.provider == 'gemini':
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: self.model.generate_content(prompt)
                )
                return response.text
        except Exception as e:
            logger.error(f"AI explanation failed: {e}")

        return "Could not generate explanation"


# Singleton instance
_ai_brain = None

def get_ai_brain() -> AIBrain:
    """الحصول على instance من AI Brain"""
    global _ai_brain
    if _ai_brain is None:
        _ai_brain = AIBrain()
    return _ai_brain
