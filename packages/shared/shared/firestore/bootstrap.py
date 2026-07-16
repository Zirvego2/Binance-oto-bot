"""Firebase Admin SDK baslatma (API + Worker ortak)."""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)
_initialized = False


def init_firebase(
    *,
    project_id: str,
    service_account_path: str = "",
    service_account_json: str = "",
    repo_root: Path | None = None,
) -> bool:
    """Firebase Admin SDK baslatir. Basarili ise True."""
    global _initialized
    if _initialized:
        return True

    if not project_id:
        logger.warning("Firebase yapilandirilmamis (FIREBASE_PROJECT_ID eksik)")
        return False

    if not service_account_path and not service_account_json:
        logger.warning("Firebase yapilandirilmamis (service account dosyasi veya JSON eksik)")
        return False

    try:
        import firebase_admin
        from firebase_admin import credentials
    except ImportError:
        logger.error("firebase-admin paketi yuklu degil")
        return False

    cred = None
    if service_account_json.strip():
        try:
            cred = credentials.Certificate(json.loads(service_account_json))
        except json.JSONDecodeError:
            logger.error("FIREBASE_SERVICE_ACCOUNT_JSON gecersiz JSON")
            return False
    else:
        resolved = Path(service_account_path)
        if not resolved.is_absolute():
            root = repo_root or Path(__file__).resolve().parents[4]
            resolved = root / service_account_path
        if not resolved.is_file():
            logger.error("Firebase service account dosyasi bulunamadi: %s", resolved)
            return False
        cred = credentials.Certificate(str(resolved))

    firebase_admin.initialize_app(cred, {"projectId": project_id})
    _initialized = True
    logger.info("Firebase Admin SDK baslatildi (project=%s)", project_id)
    return True


def firebase_enabled() -> bool:
    return _initialized
