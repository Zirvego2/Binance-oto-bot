"""GPT ile piyasa arastirma — yalnizca analiz, emir karari vermez."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Any

from .ai_explanation import FORBIDDEN_PAYLOAD_KEYS, sanitize_payload

logger = logging.getLogger("shared.ai_market_research")

MARKET_RESEARCH_SYSTEM_PROMPT = (
    "Sen profesyonel bir kripto vadeli islemler (USDT-M Futures) piyasa analistisin.\n"
    "Gorevin: verilen BTC ve piyasa verilerini Turkce, nesnel ve profesyonel sekilde yorumlamak.\n\n"
    "KURALLAR:\n"
    "- ASLA al/sat emri, pozisyon ac/kapat veya kaldıraç degistirme talimati verme.\n"
    "- Yalnizca egitim ve bilgilendirme amacli analiz yap.\n"
    "- Belirsizlik varsa acikca belirt.\n"
    "- Yanitini YALNIZCA asagidaki JSON formatinda ver:\n"
    "{\n"
    '  "executive_summary": "2-3 cumle genel ozet",\n'
    '  "market_outlook": "BULLISH|BEARISH|NEUTRAL|UNCERTAIN",\n'
    '  "confidence_pct": 0-100,\n'
    '  "btc_analysis": "BTC teknik ve momentum analizi",\n'
    '  "altcoin_implications": "Altcoinler icin olasi etki",\n'
    '  "key_observations": ["gozlem1", "gozlem2"],\n'
    '  "risk_factors": ["risk1", "risk2"],\n'
    '  "opportunities": ["firsat1"],\n'
    '  "time_horizon": "SCALP|INTRADAY|SWING",\n'
    '  "analyst_note": "Ek profesyonel not",\n'
    '  "disclaimer": "Bu analiz yatirim tavsiyesi degildir."\n'
    "}"
)


@dataclass(frozen=True, slots=True)
class MarketAiResearchResult:
    executive_summary: str
    market_outlook: str
    confidence_pct: int
    btc_analysis: str
    altcoin_implications: str
    key_observations: list[str]
    risk_factors: list[str]
    opportunities: list[str]
    time_horizon: str
    analyst_note: str
    disclaimer: str
    status: str = "OK"
    model: str | None = None
    cached: bool = False


def market_research_cache_key(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str)
    digest = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return f"market:ai_research:{digest}"


def validate_market_research_response(data: dict[str, Any]) -> MarketAiResearchResult | None:
    try:
        outlook = str(data.get("market_outlook", "NEUTRAL")).upper()
        if outlook not in ("BULLISH", "BEARISH", "NEUTRAL", "UNCERTAIN"):
            outlook = "NEUTRAL"
        horizon = str(data.get("time_horizon", "INTRADAY")).upper()
        if horizon not in ("SCALP", "INTRADAY", "SWING"):
            horizon = "INTRADAY"
        conf = max(0, min(100, int(data.get("confidence_pct", 50))))
        return MarketAiResearchResult(
            executive_summary=str(data.get("executive_summary", ""))[:3000],
            market_outlook=outlook,
            confidence_pct=conf,
            btc_analysis=str(data.get("btc_analysis", ""))[:4000],
            altcoin_implications=str(data.get("altcoin_implications", ""))[:3000],
            key_observations=[str(x) for x in data.get("key_observations", [])][:15],
            risk_factors=[str(x) for x in data.get("risk_factors", [])][:15],
            opportunities=[str(x) for x in data.get("opportunities", [])][:10],
            time_horizon=horizon,
            analyst_note=str(data.get("analyst_note", ""))[:2000],
            disclaimer=str(data.get("disclaimer", "Bu analiz yatirim tavsiyesi degildir."))[:500],
        )
    except (TypeError, ValueError):
        return None


def _unavailable(reason: str) -> MarketAiResearchResult:
    return MarketAiResearchResult(
        executive_summary="Yapay zeka analizi su anda kullanilamiyor.",
        market_outlook="UNCERTAIN",
        confidence_pct=0,
        btc_analysis="",
        altcoin_implications="",
        key_observations=[],
        risk_factors=[reason],
        opportunities=[],
        time_horizon="INTRADAY",
        analyst_note="",
        disclaimer="Bu analiz yatirim tavsiyesi degildir.",
        status="UNAVAILABLE",
    )


async def generate_market_research(
    *,
    api_key: str,
    payload: dict[str, Any],
    model: str = "gpt-4o-mini",
    timeout_seconds: int = 30,
) -> MarketAiResearchResult:
    if not api_key:
        return _unavailable("OpenAI API anahtari tanimli degil (.env OPENAI_API_KEY)")

    safe = sanitize_payload(payload)
    for key in payload:
        if key.lower() in FORBIDDEN_PAYLOAD_KEYS:
            logger.error("Market AI payload yasak alan: %s", key)

    try:
        from openai import AsyncOpenAI  # noqa: PLC0415
    except ImportError:
        return _unavailable("openai paketi kurulu degil")

    user_prompt = (
        "Asagidaki guncel piyasa verilerini profesyonel bir arastirma raporu olarak analiz et:\n\n"
        + json.dumps(safe, ensure_ascii=False, indent=2, default=str)
    )

    try:
        client = AsyncOpenAI(api_key=api_key, timeout=timeout_seconds)
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": MARKET_RESEARCH_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            max_tokens=1200,
            temperature=0.3,
        )
        raw = response.choices[0].message.content or "{}"
        parsed = validate_market_research_response(json.loads(raw))
        if parsed is None:
            return _unavailable("GPT yaniti dogrulanamadi")
        return MarketAiResearchResult(
            executive_summary=parsed.executive_summary,
            market_outlook=parsed.market_outlook,
            confidence_pct=parsed.confidence_pct,
            btc_analysis=parsed.btc_analysis,
            altcoin_implications=parsed.altcoin_implications,
            key_observations=parsed.key_observations,
            risk_factors=parsed.risk_factors,
            opportunities=parsed.opportunities,
            time_horizon=parsed.time_horizon,
            analyst_note=parsed.analyst_note,
            disclaimer=parsed.disclaimer,
            status="OK",
            model=model,
        )
    except Exception:
        logger.warning("Market AI arastirma basarisiz", exc_info=True)
        return _unavailable("GPT servisi gecici olarak yanit vermiyor")
