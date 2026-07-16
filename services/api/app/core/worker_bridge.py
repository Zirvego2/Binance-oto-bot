"""Worker order_engine modulune erisim (API manuel sinyal islemi icin)."""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

_WORKER_ROOT = Path(__file__).resolve().parents[3] / "worker"


def ensure_worker_import_path() -> None:
    if _WORKER_ROOT.is_dir():
        worker_path = str(_WORKER_ROOT)
        if worker_path not in sys.path:
            sys.path.insert(0, worker_path)


@lru_cache(maxsize=1)
def get_order_engine_module():
    ensure_worker_import_path()
    from worker import order_engine  # noqa: PLC0415

    return order_engine
