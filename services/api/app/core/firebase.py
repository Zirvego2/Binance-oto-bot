"""Firebase Admin SDK baslatma (API servisi)."""

from __future__ import annotations

from pathlib import Path

from shared.firestore.bootstrap import firebase_enabled as _firebase_enabled
from shared.firestore.bootstrap import init_firebase as _init_firebase

from .config import Settings, get_settings


def init_firebase(settings: Settings | None = None) -> None:
    settings_obj = settings or get_settings()
    repo_root = Path(__file__).resolve().parents[4]
    _init_firebase(
        project_id=settings_obj.firebase_project_id,
        service_account_path=settings_obj.firebase_service_account_path,
        service_account_json=settings_obj.firebase_service_account_json,
        repo_root=repo_root,
    )


def firebase_enabled() -> bool:
    return _firebase_enabled()
