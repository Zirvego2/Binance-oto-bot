"""Binance adapter katmani icin hata siniflari."""

from __future__ import annotations


class BinanceAdapterError(Exception):
    """Tum Binance adapter hatalarinin taban sinifi."""


class BinanceNotConfiguredError(BinanceAdapterError):
    """API anahtarlari tanimlanmamis oldugunda (sartname bolum 6 & 33)."""


class BinanceConnectionError(BinanceAdapterError):
    """Aga/HTTP baglanti hatasi (timeout, DNS, TCP reset vb.)."""


class BinanceApiError(BinanceAdapterError):
    """Binance'in donen hata kodu (ornek: -1021 timestamp, -2019 margin yetersiz)."""

    def __init__(self, code: int, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"Binance API hatasi [{code}]: {message}")


class BinanceOrderRejectedError(BinanceAdapterError):
    """Emir Binance filtrelerine gore reddedildi."""


class LeverageNotConfirmedError(BinanceAdapterError):
    """Binance istenen kaldiraci dogrulamadi."""
