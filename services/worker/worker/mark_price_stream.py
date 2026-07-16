"""Binance USDS-M Futures combine mark price WebSocket akisi (sartname bolum 8, 25).

``!markPrice@arr`` akisi TUM semboller icin mark price / funding rate
bilgisini ~3 saniyede bir yayinlar. Baglanti koptugunda otomatik olarak
ARTAN (exponential) bekleme suresiyle yeniden baglanir.
"""

from __future__ import annotations

import asyncio
import json
import logging
from decimal import Decimal
from typing import Awaitable, Callable

import websockets

from shared.binance.types import MarkPriceTick

logger = logging.getLogger("worker.mark_price_stream")

TickHandler = Callable[[MarkPriceTick], Awaitable[None]]

_MAX_BACKOFF_SECONDS = 60


def _parse_tick(entry: dict) -> MarkPriceTick:
    return MarkPriceTick(
        symbol=entry["s"],
        mark_price=Decimal(str(entry["p"])),
        index_price=Decimal(str(entry.get("i", entry["p"]))),
        funding_rate=Decimal(str(entry.get("r", "0"))),
        next_funding_time_ms=int(entry.get("T", 0)),
        time_ms=int(entry.get("E", 0)),
    )


async def run_mark_price_stream(
    ws_base_url: str, on_tick: TickHandler, stop_event: asyncio.Event
) -> None:
    """Baglanti kesilse bile ``stop_event`` set edilene kadar sonsuz yeniden
    baglanmaya calisir. Ayri bir asyncio Task olarak calistirilmalidir."""

    url = f"{ws_base_url}/ws/!markPrice@arr"
    backoff = 1

    while not stop_event.is_set():
        try:
            logger.info("Mark price WebSocket'ine baglaniliyor: %s", url)
            async with websockets.connect(url, ping_interval=20, ping_timeout=20, close_timeout=5) as ws:
                backoff = 1
                logger.info("Mark price WebSocket baglantisi kuruldu")
                while not stop_event.is_set():
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=30)
                    except asyncio.TimeoutError:
                        continue
                    try:
                        payload = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    entries = payload if isinstance(payload, list) else [payload]
                    for entry in entries:
                        if "s" not in entry or "p" not in entry:
                            continue
                        try:
                            tick = _parse_tick(entry)
                        except (KeyError, ValueError, TypeError):
                            continue
                        try:
                            await on_tick(tick)
                        except Exception:  # noqa: BLE001
                            logger.exception("Mark price tick isleme hatasi (%s)", entry.get("s"))
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning("Mark price WebSocket baglantisi koptu (%s), %ds sonra yeniden denenecek", exc, backoff)

        if stop_event.is_set():
            break
        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, _MAX_BACKOFF_SECONDS)
