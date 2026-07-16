"""Binance USDS-M Futures icin imzali/imzasiz dusuk seviye HTTP istemcisi.

Bu modul dogrudan ``https://fapi.binance.com`` (veya testnet) REST
endpointlerini cagirir. Ust seviye adapterler (``LiveFuturesAdapter``)
bu istemciyi kullanir; uygulamanin diger katmanlari bu modulu asla
dogrudan import etmemelidir.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any
from urllib.parse import urlencode

import httpx

from .errors import BinanceApiError, BinanceConnectionError

DEFAULT_TIMEOUT_SECONDS = 10.0
DEFAULT_RECV_WINDOW_MS = 5000


class BinanceRestClient:
    def __init__(
        self,
        base_url: str,
        api_key: str = "",
        api_secret: str = "",
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._api_secret = api_secret
        self._client = httpx.AsyncClient(base_url=self._base_url, timeout=timeout_seconds)
        self._server_time_offset_ms = 0

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key and self._api_secret)

    async def close(self) -> None:
        await self._client.aclose()

    def _sign(self, params: dict[str, Any]) -> dict[str, Any]:
        query = urlencode(params, doseq=True)
        signature = hmac.new(self._api_secret.encode("utf-8"), query.encode("utf-8"), hashlib.sha256).hexdigest()
        signed = dict(params)
        signed["signature"] = signature
        return signed

    def _headers(self) -> dict[str, str]:
        return {"X-MBX-APIKEY": self._api_key} if self._api_key else {}

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        signed: bool = False,
    ) -> Any:
        params = {k: v for k, v in (params or {}).items() if v is not None}

        if signed:
            params["timestamp"] = int(time.time() * 1000) + self._server_time_offset_ms
            params["recvWindow"] = DEFAULT_RECV_WINDOW_MS
            params = self._sign(params)

        try:
            response = await self._client.request(
                method, path, params=params, headers=self._headers() if signed else {}
            )
        except httpx.TimeoutException as exc:
            raise BinanceConnectionError(f"Binance istegi zaman asimina ugradi: {path}") from exc
        except httpx.HTTPError as exc:
            raise BinanceConnectionError(f"Binance baglanti hatasi: {path}: {exc}") from exc

        if response.status_code >= 400:
            try:
                body = response.json()
                code = int(body.get("code", response.status_code))
                message = str(body.get("msg", response.text))
            except Exception:
                code = response.status_code
                message = response.text
            raise BinanceApiError(code, message)

        if not response.content:
            return None
        return response.json()

    async def public_get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return await self._request("GET", path, params, signed=False)

    async def signed_get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        self._require_configured()
        return await self._request("GET", path, params, signed=True)

    async def signed_post(self, path: str, params: dict[str, Any] | None = None) -> Any:
        self._require_configured()
        return await self._request("POST", path, params, signed=True)

    async def signed_delete(self, path: str, params: dict[str, Any] | None = None) -> Any:
        self._require_configured()
        return await self._request("DELETE", path, params, signed=True)

    def _require_configured(self) -> None:
        if not self.is_configured:
            from .errors import BinanceNotConfiguredError

            raise BinanceNotConfiguredError("Binance API anahtari/secret tanimlanmamis")

    async def sync_server_time(self) -> None:
        data = await self.public_get("/fapi/v1/time")
        server_time_ms = int(data["serverTime"])
        local_time_ms = int(time.time() * 1000)
        self._server_time_offset_ms = server_time_ms - local_time_ms
