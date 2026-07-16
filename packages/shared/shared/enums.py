"""Sistem genelinde kullanilan enum tanimlari."""

from __future__ import annotations

from enum import Enum


class UserRole(str, Enum):
    PLATFORM_ADMIN = "platform_admin"
    CUSTOMER = "customer"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    BLOCKED = "blocked"


class BotEnvironment(str, Enum):
    """Botun calisma modu."""

    PAPER = "paper"
    DEMO = "demo"
    LIVE = "live"


class PositionSide(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class BinancePositionSide(str, Enum):
    """Binance'e gonderilen positionSide degeri. ONE_WAY modunda hep BOTH."""

    BOTH = "BOTH"
    LONG = "LONG"
    SHORT = "SHORT"


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class MarginType(str, Enum):
    ISOLATED = "ISOLATED"
    CROSSED = "CROSSED"


class PositionModeType(str, Enum):
    ONE_WAY = "ONE_WAY"
    HEDGE = "HEDGE"


class WorkingType(str, Enum):
    MARK_PRICE = "MARK_PRICE"
    CONTRACT_PRICE = "CONTRACT_PRICE"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_MARKET = "STOP_MARKET"
    TAKE_PROFIT_MARKET = "TAKE_PROFIT_MARKET"
    TRAILING_STOP_MARKET = "TRAILING_STOP_MARKET"


class OrderStatus(str, Enum):
    """Emir yasam dongusu durumlari (bkz. sartname bolum 14)."""

    PENDING = "PENDING"
    SUBMITTING = "SUBMITTING"
    SUBMITTED = "SUBMITTED"
    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    EXPIRED = "EXPIRED"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"


TERMINAL_ORDER_STATUSES = frozenset(
    {
        OrderStatus.FILLED,
        OrderStatus.CANCELED,
        OrderStatus.EXPIRED,
        OrderStatus.REJECTED,
    }
)


class AlgoOrderPurpose(str, Enum):
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"
    TRAILING_STOP = "TRAILING_STOP"


class PositionStatus(str, Enum):
    OPEN = "OPEN"
    CLOSING = "CLOSING"
    CLOSED = "CLOSED"
    EXTERNAL = "EXTERNAL"  # Binance'de var ama sistemde acilmamis (harici pozisyon)


class PositionCloseReason(str, Enum):
    TAKE_PROFIT = "TAKE_PROFIT"
    STOP_LOSS = "STOP_LOSS"
    TRAILING_STOP = "TRAILING_STOP"
    MANUAL = "MANUAL"
    EMERGENCY_STOP = "EMERGENCY_STOP"
    LIQUIDATION = "LIQUIDATION"
    RECONCILIATION = "RECONCILIATION"
    UNKNOWN = "UNKNOWN"


class SignalDecision(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    WAIT = "BEKLE"
    NOT_ELIGIBLE = "UYGUN_DEGIL"
    SKIPPED_RISK = "RISK_NEDENIYLE_ATLANDI"
    SKIPPED_MIN_NOTIONAL = "MINIMUM_TUTAR_NEDENIYLE_ATLANDI"


class BotRunState(str, Enum):
    STOPPED = "STOPPED"
    RUNNING = "RUNNING"
    SAFE_MODE = "SAFE_MODE"
    DEGRADED = "DEGRADED"
    EMERGENCY_STOPPED = "EMERGENCY_STOPPED"


class LogType(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    TRADE = "TRADE"
    RISK = "RISK"
    BINANCE = "BINANCE"
    SECURITY = "SECURITY"


class RiskEventType(str, Enum):
    DAILY_LOSS_LIMIT = "DAILY_LOSS_LIMIT"
    CONSECUTIVE_LOSS_LIMIT = "CONSECUTIVE_LOSS_LIMIT"
    MAX_POSITIONS = "MAX_POSITIONS"
    MIN_NOTIONAL_NOT_MET = "MIN_NOTIONAL_NOT_MET"
    LIQUIDATION_DISTANCE = "LIQUIDATION_DISTANCE"
    SPREAD_TOO_WIDE = "SPREAD_TOO_WIDE"
    SLIPPAGE_TOO_HIGH = "SLIPPAGE_TOO_HIGH"
    FUNDING_RATE_LIMIT = "FUNDING_RATE_LIMIT"
    VOLATILITY_LIMIT = "VOLATILITY_LIMIT"
    STALE_PRICE_DATA = "STALE_PRICE_DATA"
    CONNECTION_LOST = "CONNECTION_LOST"
    PROTECTIVE_ORDER_FAILED = "PROTECTIVE_ORDER_FAILED"
    RECONCILIATION_MISMATCH = "RECONCILIATION_MISMATCH"
    DUPLICATE_ORDER_PREVENTED = "DUPLICATE_ORDER_PREVENTED"
    COOLDOWN_ACTIVE = "COOLDOWN_ACTIVE"
    LEVERAGE_NOT_CONFIRMED = "LEVERAGE_NOT_CONFIRMED"
    SYMBOL_NOT_ELIGIBLE = "SYMBOL_NOT_ELIGIBLE"


class BotEventType(str, Enum):
    BOT_STARTED = "BOT_STARTED"
    BOT_STOPPED = "BOT_STOPPED"
    MODE_CHANGED = "MODE_CHANGED"
    EMERGENCY_STOP = "EMERGENCY_STOP"
    SAFE_MODE_ENTERED = "SAFE_MODE_ENTERED"
    SAFE_MODE_EXITED = "SAFE_MODE_EXITED"
    POSITION_OPENED = "POSITION_OPENED"
    POSITION_CLOSED = "POSITION_CLOSED"
    RECONCILIATION_RUN = "RECONCILIATION_RUN"
    SETTINGS_CHANGED = "SETTINGS_CHANGED"


class SystemHealthStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    UNKNOWN = "UNKNOWN"


class ConnectionStatus(str, Enum):
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    ERROR = "ERROR"
    NOT_CONFIGURED = "NOT_CONFIGURED"


class ReconciliationStatus(str, Enum):
    OK = "OK"
    MISMATCH_FOUND = "MISMATCH_FOUND"
    EXTERNAL_POSITION_FOUND = "EXTERNAL_POSITION_FOUND"
    FAILED = "FAILED"
