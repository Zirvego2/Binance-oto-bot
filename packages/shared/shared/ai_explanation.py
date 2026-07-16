"""Guvenli GPT aciklama modulu — emir karari vermez, yalnizca aciklama uretir."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("shared.ai_explanation")

FORBIDDEN_PAYLOAD_KEYS = frozenset({
    "api_key", "api_secret", "secret", "password", "token", "cookie", "authorization",
    "binance_api_key", "binance_api_secret",
})

AI_EXPLANATION_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "positive_factors": {"type": "array", "items": {"type": "string"}},
        "negative_factors": {"type": "array", "items": {"type": "string"}},
        "risk_level": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"]},
        "warnings": {"type": "array", "items": {"type": "string"}},
        "suggestion": {"type": "string"},
    },
    "required": ["summary", "positive_factors", "negative_factors", "risk_level", "warnings", "suggestion"],
    "additionalProperties": False,
}

_SYSTEM_PROMPT = (
    "Sen bir kripto vadeli islem aciklama asistanisin.\n"
    "Gorevin: teknik sinyali Turkce aciklamak, riskleri ozetlemek.\n"
    "ASLA islem ac/kapat onerisi verme, emir karari verme.\n"
    "Yanitini yalnizca JSON formatinda ver:\n"
    '{"summary":"...","positive_factors":[],"negative_factors":[],"risk_level":"LOW|MEDIUM|HIGH|CRITICAL","warnings":[],"suggestion":"..."}'
)


@dataclass(frozen=True, slots=True)
class AiExplanationResult:
    summary: str
    positive_factors: list[str]
    negative_factors: list[str]
    risk_level: str
    warnings: list[str]
    suggestion: str
    status: str = "OK"
    model: str | None = None


def sanitize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in payload.items() if k.lower() not in FORBIDDEN_PAYLOAD_KEYS}


def validate_ai_response(data: dict[str, Any]) -> AiExplanationResult | None:
    try:
        risk = str(data.get("risk_level", "MEDIUM")).upper()
        if risk not in ("LOW", "MEDIUM", "HIGH", "CRITICAL"):
            risk = "MEDIUM"
        return AiExplanationResult(
            summary=str(data.get("summary", ""))[:2000],
            positive_factors=[str(x) for x in data.get("positive_factors", [])][:20],
            negative_factors=[str(x) for x in data.get("negative_factors", [])][:20],
            risk_level=risk,
            warnings=[str(x) for x in data.get("warnings", [])][:20],
            suggestion=str(data.get("suggestion", ""))[:1000],
        )
    except (TypeError, ValueError):
        return None


async def generate_signal_explanation(
    *,
    api_key: str,
    payload: dict[str, Any],
    model: str = "gpt-4o-mini",
    timeout_seconds: int = 15,
) -> AiExplanationResult:
    """GPT hatasi durumunda deterministik motor etkilenmez — status UNAVAILABLE doner."""
    if not api_key:
        return AiExplanationResult(
            summary="Kullanilamiyor",
            positive_factors=[],
            negative_factors=[],
            risk_level="MEDIUM",
            warnings=["OpenAI API anahtari tanimli degil"],
            suggestion="",
            status="UNAVAILABLE",
        )

    safe = sanitize_payload(payload)
    for key in payload:
        if key.lower() in FORBIDDEN_PAYLOAD_KEYS:
            logger.error("GPT payload'a yasak alan gonderilmeye calisildi: %s", key)

    try:
        from openai import AsyncOpenAI  # noqa: PLC0415
    except ImportError:
        return AiExplanationResult(
            summary="Kullanilamiyor",
            positive_factors=[], negative_factors=[], risk_level="MEDIUM",
            warnings=["openai paketi kurulu degil"], suggestion="", status="UNAVAILABLE",
        )

    user_prompt = json.dumps(safe, ensure_ascii=False, default=str)
    try:
        client = AsyncOpenAI(api_key=api_key, timeout=timeout_seconds)
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            max_tokens=500,
            temperature=0.2,
        )
        raw = response.choices[0].message.content or "{}"
        parsed = validate_ai_response(json.loads(raw))
        if parsed is None:
            return AiExplanationResult(
                summary="Kullanilamiyor", positive_factors=[], negative_factors=[],
                risk_level="MEDIUM", warnings=["GPT yaniti schema dogrulamasindan gecemedi"],
                suggestion="", status="UNAVAILABLE",
            )
        return AiExplanationResult(
            summary=parsed.summary,
            positive_factors=parsed.positive_factors,
            negative_factors=parsed.negative_factors,
            risk_level=parsed.risk_level,
            warnings=parsed.warnings,
            suggestion=parsed.suggestion,
            status="OK",
            model=model,
        )
    except Exception:
        logger.warning("GPT aciklama uretilemedi", exc_info=True)
        return AiExplanationResult(
            summary="Kullanilamiyor", positive_factors=[], negative_factors=[],
            risk_level="MEDIUM", warnings=["GPT servisi gecici olarak kullanilamiyor"],
            suggestion="", status="UNAVAILABLE",
        )
