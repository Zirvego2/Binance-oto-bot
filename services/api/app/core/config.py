"""Uygulama ayarlari - ortam degiskenlerinden okunur (sartname bolum 6)."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
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

    app_timezone: str = Field(default="Europe/Istanbul", alias="APP_TIMEZONE")

    admin_email: str = Field(default="admin@example.com", alias="ADMIN_EMAIL")
    admin_password: str = Field(default="ChangeMe123!", alias="ADMIN_PASSWORD")
    platform_admin_email: str = Field(default="", alias="PLATFORM_ADMIN_EMAIL")
    platform_admin_password: str = Field(default="", alias="PLATFORM_ADMIN_PASSWORD")

    binance_env: str = Field(default="paper", alias="BINANCE_ENV")
    binance_api_key: str = Field(default="", alias="BINANCE_API_KEY")
    binance_api_secret: str = Field(default="", alias="BINANCE_API_SECRET")

    binance_futures_base_url: str = Field(default="https://fapi.binance.com", alias="BINANCE_FUTURES_BASE_URL")
    binance_futures_ws_url: str = Field(default="wss://fstream.binance.com", alias="BINANCE_FUTURES_WS_URL")
    binance_demo_base_url: str = Field(default="https://testnet.binancefuture.com", alias="BINANCE_DEMO_BASE_URL")
    binance_demo_ws_url: str = Field(default="wss://stream.binancefuture.com", alias="BINANCE_DEMO_WS_URL")
    binance_spot_base_url: str = Field(default="https://api.binance.com", alias="BINANCE_SPOT_BASE_URL")

    admin_trc20_address: str = Field(
        default="TPkJEf1ZwL1MoTkpCyfvmKHTiZvuRUmwVM",
        alias="ADMIN_TRC20_ADDRESS",
    )
    admin_trc20_network: str = Field(default="TRX", alias="ADMIN_TRC20_NETWORK")
    fund_transfer_min_usdt: str = Field(default="1", alias="FUND_TRANSFER_MIN_USDT")

    enable_demo_trading: bool = Field(default=False, alias="ENABLE_DEMO_TRADING")
    enable_live_trading: bool = Field(default=False, alias="ENABLE_LIVE_TRADING")
    max_allowed_leverage: int = Field(default=20, alias="MAX_ALLOWED_LEVERAGE")

    paper_start_balance_usdt: str = Field(default="100", alias="PAPER_START_BALANCE_USDT")
    paper_taker_commission_rate: str = Field(default="0.0004", alias="PAPER_TAKER_COMMISSION_RATE")
    paper_funding_simulation_enabled: bool = Field(default=True, alias="PAPER_FUNDING_SIMULATION_ENABLED")

    web_origin: str = Field(default="http://localhost:3000", alias="WEB_ORIGIN")
    api_origin: str = Field(default="http://localhost:8000", alias="API_ORIGIN")

    session_cookie_name: str = Field(default="trading_bot_session", alias="SESSION_COOKIE_NAME")
    session_ttl_minutes: int = Field(default=480, alias="SESSION_TTL_MINUTES")
    secure_cookies: bool = Field(default=False, alias="SECURE_COOKIES")

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    emergency_close_password: str = Field(default="1453", alias="EMERGENCY_CLOSE_PASSWORD")
    profile_access_password: str = Field(default="14531453", alias="PROFILE_ACCESS_PASSWORD")
    profile_unlock_ttl_minutes: int = Field(default=30, alias="PROFILE_UNLOCK_TTL_MINUTES")

    firebase_project_id: str = Field(default="", alias="FIREBASE_PROJECT_ID")
    firebase_service_account_path: str = Field(default="", alias="FIREBASE_SERVICE_ACCOUNT_PATH")
    firebase_service_account_json: str = Field(default="", alias="FIREBASE_SERVICE_ACCOUNT_JSON")

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    ai_explanation_enabled: bool = Field(default=True, alias="AI_EXPLANATION_ENABLED")
    ai_market_research_enabled: bool = Field(default=True, alias="AI_MARKET_RESEARCH_ENABLED")
    ai_model: str = Field(default="gpt-4o-mini", alias="AI_MODEL")
    ai_timeout_seconds: int = Field(default=30, alias="AI_TIMEOUT_SECONDS")
    ai_market_research_cache_seconds: int = Field(default=300, alias="AI_MARKET_RESEARCH_CACHE_SECONDS")

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
