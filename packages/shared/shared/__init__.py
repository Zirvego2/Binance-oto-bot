"""Binance USDS-M Futures bot icin servisler arasi paylasilan cekirdek mantik.

Bu paket, ``services/api`` ve ``services/worker`` tarafindan ortak olarak
kullanilir. Burada tanimlanan tum finansal hesaplamalar ``decimal.Decimal``
kullanir; hicbir yerde binary float ile para/miktar/fiyat hesabi yapilmaz.
"""

from importlib import metadata

try:
    __version__ = metadata.version("trading-bot-shared")
except metadata.PackageNotFoundError:  # pragma: no cover - local/dev calistirma
    __version__ = "0.1.0"

__all__ = ["__version__"]
