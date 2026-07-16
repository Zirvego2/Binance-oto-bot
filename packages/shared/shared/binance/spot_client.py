"""Binance Spot / Wallet API istemcisi (withdraw, transfer, apiRestrictions)."""

from __future__ import annotations

import hashlib
import hmac
import time
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode

import httpx

from ..decimal_utils import format_decimal_plain, to_decimal
from .errors import BinanceApiError, BinanceConnectionError

DEFAULT_TIMEOUT_SECONDS = 15.0
DEFAULT_RECV_WINDOW_MS = 5000


@dataclass(frozen=True)
class ApiRestrictions:
    ip_restrict: bool
    enable_withdrawals: bool
    enable_internal_transfer: bool
    enable_reading: bool
    enable_spot_and_margin_trading: bool
    enable_futures: bool


@dataclass(frozen=True)
class CoinNetworkConfig:
    coin: str
    network: str
    withdraw_fee: Decimal
    withdraw_min: Decimal
    withdraw_max: Decimal
    withdraw_enabled: bool


class BinanceSpotClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        api_secret: str,
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
        return {"X-MBX-APIKEY": self._api_key}

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        signed: bool = False,
    ) -> Any:
        params = {k: v for k, v in (params or {}).items() if v is not None}

        if signed:
            params["timestamp"] = int(time.time() * 1000) + self._server_time_offset_ms
            params["recvWindow"] = DEFAULT_RECV_WINDOW_MS
            params = self._sign(params)

        try:
            response = await self._client.request(
                method,
                path,
                params=params,
                headers=self._headers() if signed else {},
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

    async def sync_server_time(self) -> None:
        data = await self._request("GET", "/api/v3/time")
        server_time_ms = int(data["serverTime"])
        local_time_ms = int(time.time() * 1000)
        self._server_time_offset_ms = server_time_ms - local_time_ms

    async def get_api_restrictions(self) -> ApiRestrictions:
        data = await self._request("GET", "/sapi/v1/account/apiRestrictions", signed=True)
        return ApiRestrictions(
            ip_restrict=bool(data.get("ipRestrict")),
            enable_withdrawals=bool(data.get("enableWithdrawals")),
            enable_internal_transfer=bool(data.get("enableInternalTransfer")),
            enable_reading=bool(data.get("enableReading")),
            enable_spot_and_margin_trading=bool(data.get("enableSpotAndMarginTrading")),
            enable_futures=bool(data.get("enableFutures")),
        )

    async def get_asset_balance(self, asset: str) -> Decimal:
        data = await self._request("GET", "/api/v3/account", signed=True)
        asset_upper = asset.upper()
        for row in data.get("balances", []):
            if str(row.get("asset", "")).upper() == asset_upper:
                return to_decimal(row.get("free"))
        return Decimal("0")

    async def transfer_futures_to_spot(self, asset: str, amount: Decimal) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/sapi/v1/futures/transfer",
            {
                "asset": asset,
                "amount": format_decimal_plain(amount),
                "type": 2,
            },
            signed=True,
        )

    async def get_coin_network_config(self, coin: str, network: str) -> CoinNetworkConfig | None:
        data = await self._request("GET", "/sapi/v1/capital/config/getall", signed=True)
        coin_upper = coin.upper()
        network_upper = network.upper()
        for item in data:
            if str(item.get("coin", "")).upper() != coin_upper:
                continue
            for net in item.get("networkList", []):
                if str(net.get("network", "")).upper() != network_upper:
                    continue
                return CoinNetworkConfig(
                    coin=coin_upper,
                    network=network_upper,
                    withdraw_fee=to_decimal(net.get("withdrawFee")),
                    withdraw_min=to_decimal(net.get("withdrawMin")),
                    withdraw_max=to_decimal(net.get("withdrawMax")),
                    withdraw_enabled=bool(net.get("withdrawEnable")),
                )
        return None

    async def withdraw(
        self,
        *,
        coin: str,
        address: str,
        amount: Decimal,
        network: str,
        withdraw_order_id: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "coin": coin.upper(),
            "address": address,
            "amount": format_decimal_plain(amount),
            "network": network.upper(),
            "withdrawOrderId": withdraw_order_id or uuid.uuid4().hex,
        }
        return await self._request("POST", "/sapi/v1/capital/withdraw/apply", params, signed=True)
