"""Yapilandirilmis loglama - hassas veriler otomatik maskelenir (sartname bolum 22 & 28)."""

from __future__ import annotations

import logging
import sys

from shared.masking import mask_text

from .config import get_settings


class SensitiveDataFilter(logging.Filter):
    """API key, secret, sifre, token, cookie, Authorization header degerlerini maskeler."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.msg = mask_text(str(record.msg))
            if record.args:
                record.args = tuple(
                    mask_text(str(a)) if isinstance(a, str) else a for a in record.args
                )
        except Exception:  # pragma: no cover - loglama asla uygulamayi cokertmemeli
            pass
        return True


def configure_logging() -> None:
    settings = get_settings()
    root = logging.getLogger()
    root.setLevel(settings.log_level.upper())

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
    )
    handler.addFilter(SensitiveDataFilter())

    root.handlers.clear()
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
