"""Firestore koleksiyon semasi (100+ musteri SaaS).

Yapi:
  customers/{firebaseUid}           — profil (Auth UID ile)
  tenantIndex/{adminId}             — adminId → firebaseUid lookup
  tenants/{adminId}/settings/current
  tenants/{adminId}/runtime/current
  tenants/{adminId}/positions/{positionId}
  tenants/{adminId}/trades/{tradeId}
  tenants/{adminId}/orders/{orderId}
  tenants/{adminId}/symbolRules/{symbol}
  tenants/{adminId}/analysis/{analysisId}
  tenants/{adminId}/signals/{signalId}
  platform/defaults                 — panel varsayilan ayarlari
  platform/shared/analysis/{id}   — ortak analiz (tum musteriler)
  platform/shared/signals/{id}    — ortak sinyaller (tum musteriler)
"""

from __future__ import annotations

# Kok koleksiyonlar
CUSTOMERS_COLLECTION = "customers"
TENANTS_COLLECTION = "tenants"
TENANT_INDEX_COLLECTION = "tenantIndex"
PLATFORM_COLLECTION = "platform"

# tenants/{adminId} alt koleksiyonlari
SUBCOL_SETTINGS = "settings"
SUBCOL_RUNTIME = "runtime"
SUBCOL_POSITIONS = "positions"
SUBCOL_TRADES = "trades"
SUBCOL_ORDERS = "orders"
SUBCOL_SYMBOL_RULES = "symbolRules"
SUBCOL_ANALYSIS = "analysis"
SUBCOL_SIGNALS = "signals"
SUBCOL_BOT_EVENTS = "botEvents"

# Tekil dokuman kimlikleri
DOC_CURRENT = "current"
DOC_DEFAULTS = "defaults"
DOC_SHARED = "shared"

# Musteri profil alanlari (camelCase — Firestore convention)
PROFILE_FIELDS = frozenset(
    {
        "email",
        "adminId",
        "fullName",
        "accountType",
        "plan",
        "approvalStatus",
        "connections",
        "createdAt",
        "updatedAt",
    }
)
