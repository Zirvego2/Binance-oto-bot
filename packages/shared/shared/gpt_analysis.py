"""GPT destekli sinyal dogrulama: teknik sinyali yapay zeka ile ikinci kez filtreler.

Kullanim:
  - Sadece LONG / SHORT sinyal uretildiginde cagrilir (WAIT / SKIPPED icin degil).
  - GPT hata verirse ya da API key tanimlanmamissa None dondurulur → orijinal sinyal gecer.
  - Model: gpt-4o-mini (ucuz, hizli, JSON modu destekler)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

logger = logging.getLogger("shared.gpt_analysis")

_SYSTEM_PROMPT = (
    "Sen bir kripto vadeli islemler (USDM Futures) analiz asistanisin.\n"
    "Sana bir sembol icin teknik analiz verileri verilecek.\n"
    "Gorven: Bu teknik sinyali degerlendirip islem acilib acilmamasi gerektigine karar vermek.\n\n"
    "Yanitini YALNIZCA asagidaki JSON formatinda ver, baska hicbir sey ekleme:\n"
    '{"verdict":"CONFIRM|REJECT|CAUTION","confidence":0-100,"reason":"maks 80 karakter"}\n\n'
    "CONFIRM : Sinyal guclu, islem acilabilir.\n"
    "CAUTION : Sinyal var ama riskli; dikkatli olunmali.\n"
    "REJECT  : Sinyal zayif veya yaniltici; islem acilmamali."
)


@dataclass
class GPTVerdict:
    verdict: str      # CONFIRM | REJECT | CAUTION
    confidence: int   # 0-100
    reason: str


async def evaluate_signal_with_gpt(
    api_key: str,
    symbol: str,
    suggested_side: str,
    total_score: float,
    rsi: float,
    ema_trend: str,
    volume_ratio: float,
    funding_rate_pct: float,
    atr_pct: float,
    model: str = "gpt-4o-mini",
) -> GPTVerdict | None:
    """Teknik sinyali GPT ile dogrular.

    Returns
    -------
    GPTVerdict ya da None (hata / key yok → fail-open, sinyal gecilir).
    """
    if not api_key:
        return None

    try:
        from openai import AsyncOpenAI  # noqa: PLC0415
    except ImportError:
        logger.warning("openai paketi kurulu degil — GPT filtresi devre disi")
        return None

    user_prompt = (
        f"Sembol         : {symbol}\n"
        f"Yon            : {suggested_side}\n"
        f"Teknik skor    : {total_score:.1f}/100\n"
        f"RSI            : {rsi:.1f}\n"
        f"EMA trendi     : {ema_trend}\n"
        f"Hacim/20MA     : {volume_ratio:.2f}x\n"
        f"Funding rate   : {funding_rate_pct:.4f}%\n"
        f"ATR volatilite : {atr_pct:.2f}%\n\n"
        "Bu sinyali degerlendir ve JSON yanitini ver."
    )

    try:
        client = AsyncOpenAI(api_key=api_key)
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            max_tokens=150,
            temperature=0.2,
        )
        raw = response.choices[0].message.content or "{}"
        data = json.loads(raw)

        verdict = str(data.get("verdict", "CONFIRM")).upper().strip()
        if verdict not in ("CONFIRM", "REJECT", "CAUTION"):
            verdict = "CONFIRM"
        confidence = max(0, min(100, int(data.get("confidence", 70))))
        reason = str(data.get("reason", ""))[:80]

        logger.info(
            "GPT sinyal [%s %s] → %s (guven: %d%%) — %s",
            symbol, suggested_side, verdict, confidence, reason,
        )
        return GPTVerdict(verdict=verdict, confidence=confidence, reason=reason)

    except Exception:
        logger.warning(
            "GPT sinyal dogrulama basarisiz, orijinal sinyal korunuyor (%s)",
            symbol,
            exc_info=True,
        )
        return None
