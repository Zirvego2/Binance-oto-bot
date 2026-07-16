"""Worker servisi ayarlari (API'nin core/config.py ile aynı ortam degiskenlerini okur)."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = Field(default="development", alias="APP_ENV")
    app_secret: str = Field(default="dev-insecure-secret-change-me", alias="APP_SECRET")
    app_encryption_key: str = Field(default="", alias="APP_ENCRYPTION_KEY")

    database_url: str = Field(
        default="postgresql+asyncpg://trading_bot:trading_bot@localhost:5432/trading_bot",
        alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    binance_env: str = Field(default="paper", alias="BINANCE_ENV")
    binance_api_key: str = Field(default="", alias="BINANCE_API_KEY")
    binance_api_secret: str = Field(default="", alias="BINANCE_API_SECRET")

    binance_futures_base_url: str = Field(default="https://fapi.binance.com", alias="BINANCE_FUTURES_BASE_URL")
    binance_futures_ws_url: str = Field(default="wss://fstream.binance.com", alias="BINANCE_FUTURES_WS_URL")
    binance_demo_base_url: str = Field(default="https://testnet.binancefuture.com", alias="BINANCE_DEMO_BASE_URL")
    binance_demo_ws_url: str = Field(default="wss://stream.binancefuture.com", alias="BINANCE_DEMO_WS_URL")

    enable_demo_trading: bool = Field(default=False, alias="ENABLE_DEMO_TRADING")
    enable_live_trading: bool = Field(default=False, alias="ENABLE_LIVE_TRADING")
    max_allowed_leverage: int = Field(default=20, alias="MAX_ALLOWED_LEVERAGE")

    paper_start_balance_usdt: str = Field(default="100", alias="PAPER_START_BALANCE_USDT")
    paper_taker_commission_rate: str = Field(default="0.0004", alias="PAPER_TAKER_COMMISSION_RATE")

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    ai_signal_filter_enabled: bool = Field(default=False, alias="AI_SIGNAL_FILTER_ENABLED")
    ai_explanation_enabled: bool = Field(default=True, alias="AI_EXPLANATION_ENABLED")

    worker_instance_id: str = Field(default="", alias="WORKER_INSTANCE_ID")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    firebase_project_id: str = Field(default="", alias="FIREBASE_PROJECT_ID")
    firebase_service_account_path: str = Field(default="", alias="FIREBASE_SERVICE_ACCOUNT_PATH")
    firebase_service_account_json: str = Field(default="", alias="FIREBASE_SERVICE_ACCOUNT_JSON")

    market_sync_interval_seconds: int = Field(default=1800, alias="MARKET_SYNC_INTERVAL_SECONDS")
    reconciliation_interval_seconds: int = Field(default=300, alias="RECONCILIATION_INTERVAL_SECONDS")
    heartbeat_interval_seconds: int = Field(default=15, alias="HEARTBEAT_INTERVAL_SECONDS")

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def market_ws_base_url(self) -> str:
        return self.binance_demo_ws_url if self.binance_env == "demo" else self.binance_futures_ws_url

    @property
    def market_rest_base_url(self) -> str:
        if self.binance_env == "demo":
            return self.binance_demo_base_url
        return self.binance_futures_base_url


@lru_cache
def get_worker_settings() -> WorkerSettings:
    return WorkerSettings()
