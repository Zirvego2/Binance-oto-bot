"""Gelismis karar motorunu etkinlestirir: schema + ayarlar + rejim profilleri seed."""

from __future__ import annotations

import asyncio
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "trading_bot.db"
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
STOP = ROOT / "scripts" / "stop_bot.ps1"
START = ROOT / "scripts" / "start_bot.ps1"

sys.path.insert(0, str(ROOT / "packages" / "shared"))
sys.path.insert(0, str(ROOT / "services" / "worker"))

ENHANCED_SETTINGS = {
    "market_regime_enabled": 1,
    "block_trades_in_risk_off": 1,
    "min_regime_confidence": 40,
    "high_volatility_score_threshold": 75,
    "high_volatility_min_signal_score": 65,
    "unknown_regime_min_signal_score": 60,
    "max_allowed_risk_score": 80,
    "high_risk_min_signal_score": 75,
    "block_critical_risk": 1,
    "risk_adjusted_leverage_enabled": 0,
    "minimum_risk_reward_ratio": 1.2,
    "symbol_profile_enabled": 1,
    "symbol_profile_shadow_mode": 1,
    "symbol_profile_weight": 0.3,
    "minimum_profile_sample_size": 10,
    "correlation_control_enabled": 1,
    "correlation_lookback": 100,
    "max_position_correlation": 0.80,
    "block_high_correlation_trades": 0,
    "correlation_penalty_weight": 1.0,
    "btc_mtf_filter_enabled": 1,
    "btc_block_against_trend": 0,
    "enhanced_engine_enabled": 1,
    "enhanced_engine_shadow_mode": 1,
    "enhanced_engine_live_enabled": 0,
    "shadow_mode_active": 1,
    "ai_explanation_enabled": 1,
    "ai_post_trade_report_enabled": 1,
    "ai_timeout_seconds": 15,
    "ai_daily_budget_usd": 5,
    "ai_model": "gpt-4o-mini",
    "ai_data_retention_enabled": 1,
}

# SQLite ALTER TABLE — nullable kolonlar
SQLITE_NEW_COLUMNS: dict[str, str] = {
    "market_regime_enabled": "BOOLEAN NOT NULL DEFAULT 1",
    "block_trades_in_risk_off": "BOOLEAN NOT NULL DEFAULT 1",
    "min_regime_confidence": "NUMERIC(10,4) NOT NULL DEFAULT 40",
    "high_volatility_score_threshold": "NUMERIC(10,4) NOT NULL DEFAULT 75",
    "high_volatility_min_signal_score": "NUMERIC(10,4) NOT NULL DEFAULT 65",
    "unknown_regime_min_signal_score": "NUMERIC(10,4) NOT NULL DEFAULT 60",
    "max_allowed_risk_score": "NUMERIC(10,4) NOT NULL DEFAULT 80",
    "high_risk_min_signal_score": "NUMERIC(10,4) NOT NULL DEFAULT 75",
    "block_critical_risk": "BOOLEAN NOT NULL DEFAULT 1",
    "risk_adjusted_leverage_enabled": "BOOLEAN NOT NULL DEFAULT 0",
    "minimum_risk_reward_ratio": "NUMERIC(10,4) NOT NULL DEFAULT 1.2",
    "symbol_profile_enabled": "BOOLEAN NOT NULL DEFAULT 1",
    "symbol_profile_shadow_mode": "BOOLEAN NOT NULL DEFAULT 1",
    "symbol_profile_weight": "NUMERIC(10,4) NOT NULL DEFAULT 0.3",
    "minimum_profile_sample_size": "INTEGER NOT NULL DEFAULT 10",
    "correlation_control_enabled": "BOOLEAN NOT NULL DEFAULT 1",
    "correlation_lookback": "INTEGER NOT NULL DEFAULT 100",
    "max_position_correlation": "NUMERIC(10,4) NOT NULL DEFAULT 0.80",
    "block_high_correlation_trades": "BOOLEAN NOT NULL DEFAULT 0",
    "correlation_penalty_weight": "NUMERIC(10,4) NOT NULL DEFAULT 1.0",
    "btc_mtf_filter_enabled": "BOOLEAN NOT NULL DEFAULT 1",
    "btc_block_against_trend": "BOOLEAN NOT NULL DEFAULT 0",
    "enhanced_engine_enabled": "BOOLEAN NOT NULL DEFAULT 0",
    "enhanced_engine_shadow_mode": "BOOLEAN NOT NULL DEFAULT 1",
    "enhanced_engine_live_enabled": "BOOLEAN NOT NULL DEFAULT 0",
    "shadow_mode_active": "BOOLEAN NOT NULL DEFAULT 1",
    "opportunity_score_weights": "JSON",
    "ai_explanation_enabled": "BOOLEAN NOT NULL DEFAULT 1",
    "ai_post_trade_report_enabled": "BOOLEAN NOT NULL DEFAULT 1",
    "ai_timeout_seconds": "INTEGER NOT NULL DEFAULT 15",
    "ai_daily_budget_usd": "NUMERIC(20,8) NOT NULL DEFAULT 5",
    "ai_model": "VARCHAR(64) NOT NULL DEFAULT 'gpt-4o-mini'",
    "ai_data_retention_enabled": "BOOLEAN NOT NULL DEFAULT 1",
    "active_strategy_version_id": "VARCHAR(36)",
}

OTHER_ALTER = {
    "strategy_signals": {
        "strategy_version_id": "VARCHAR(36)",
        "risk_score": "NUMERIC(10,4)",
        "regime_at_signal": "VARCHAR(32)",
    },
    "positions": {"strategy_version_id": "VARCHAR(36)"},
    "trades": {"strategy_version_id": "VARCHAR(36)"},
}


def ensure_sqlite_columns() -> None:
    conn = sqlite3.connect(DB, timeout=60)
    conn.execute("PRAGMA journal_mode=WAL")
    cur = conn.cursor()

    cur.execute("PRAGMA table_info(bot_settings)")
    existing = {r[1] for r in cur.fetchall()}
    for col, typedef in SQLITE_NEW_COLUMNS.items():
        if col not in existing:
            cur.execute(f"ALTER TABLE bot_settings ADD COLUMN {col} {typedef}")
            print(f"  + bot_settings.{col}")

    for table, cols in OTHER_ALTER.items():
        cur.execute(f"PRAGMA table_info({table})")
        tex = {r[1] for r in cur.fetchall()}
        for col, typedef in cols.items():
            if col not in tex:
                cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typedef}")
                print(f"  + {table}.{col}")

    conn.commit()
    conn.close()


async def ensure_tables_and_seed() -> None:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from shared.db import Base, BotSettings
    from shared.enhanced.seed_profiles import seed_strategy_regime_profiles

    engine = create_async_engine(
        f"sqlite+aiosqlite:///{DB.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        await seed_strategy_regime_profiles(session)
        settings = await session.get(BotSettings, "default")
        if settings is None:
            settings = BotSettings(id="default")
            session.add(settings)
        settings.market_regime_enabled = True
        settings.block_trades_in_risk_off = True
        settings.min_regime_confidence = Decimal("40")
        settings.high_volatility_score_threshold = Decimal("75")
        settings.high_volatility_min_signal_score = Decimal("65")
        settings.unknown_regime_min_signal_score = Decimal("60")
        settings.max_allowed_risk_score = Decimal("80")
        settings.high_risk_min_signal_score = Decimal("75")
        settings.block_critical_risk = True
        settings.risk_adjusted_leverage_enabled = False
        settings.minimum_risk_reward_ratio = Decimal("1.2")
        settings.symbol_profile_enabled = True
        settings.symbol_profile_shadow_mode = True
        settings.symbol_profile_weight = Decimal("0.3")
        settings.minimum_profile_sample_size = 10
        settings.correlation_control_enabled = True
        settings.correlation_lookback = 100
        settings.max_position_correlation = Decimal("0.80")
        settings.block_high_correlation_trades = False
        settings.correlation_penalty_weight = Decimal("1.0")
        settings.btc_mtf_filter_enabled = True
        settings.btc_block_against_trend = False
        settings.enhanced_engine_enabled = True
        settings.enhanced_engine_shadow_mode = True
        settings.enhanced_engine_live_enabled = False
        settings.shadow_mode_active = True
        settings.ai_explanation_enabled = True
        settings.ai_post_trade_report_enabled = True
        settings.ai_timeout_seconds = 15
        settings.ai_daily_budget_usd = Decimal("5")
        settings.ai_model = "gpt-4o-mini"
        settings.ai_data_retention_enabled = True
        settings.updated_at = datetime.now(timezone.utc)
        await session.commit()
    await engine.dispose()


def stamp_alembic() -> None:
    conn = sqlite3.connect(DB, timeout=60)
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)")
    cur.execute("DELETE FROM alembic_version")
    cur.execute("INSERT INTO alembic_version (version_num) VALUES ('a1b2c3d4e5f6')")
    conn.commit()
    conn.close()


def update_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    text = env_path.read_text(encoding="utf-8")
    if "AI_SIGNAL_FILTER_ENABLED=true" in text:
        text = text.replace("AI_SIGNAL_FILTER_ENABLED=true", "AI_SIGNAL_FILTER_ENABLED=false")
    if "AI_EXPLANATION_ENABLED" not in text:
        text = text.replace(
            "AI_SIGNAL_FILTER_ENABLED=false",
            "AI_SIGNAL_FILTER_ENABLED=false\nAI_EXPLANATION_ENABLED=true",
        )
    env_path.write_text(text, encoding="utf-8")
    print("  .env: AI_SIGNAL_FILTER_ENABLED=false, AI_EXPLANATION_ENABLED=true")


def restart_services() -> None:
    subprocess.run(
        ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(STOP)],
        cwd=ROOT,
        check=False,
    )
    subprocess.run(
        ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(START)],
        cwd=ROOT,
        check=True,
    )


def print_status() -> None:
    conn = sqlite3.connect(DB, timeout=60)
    row = conn.execute(
        "SELECT enhanced_engine_enabled, enhanced_engine_shadow_mode, shadow_mode_active, "
        "market_regime_enabled, ai_explanation_enabled, bot_enabled, mode "
        "FROM bot_settings WHERE id='default'"
    ).fetchone()
    tables = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name IN "
        "('market_regime_snapshots','shadow_decisions','trade_candidate_rankings','strategy_regime_profiles')"
    ).fetchone()
    conn.close()
    print("\n=== Gelismis Motor Durumu ===")
    print("Ayarlar:", row)
    print("Enhanced tablolar (4/4):", tables[0] == 4)


if __name__ == "__main__":
    if not DB.exists():
        sys.exit(f"DB bulunamadi: {DB}")
    print("1) SQLite kolonlari ekleniyor...")
    ensure_sqlite_columns()
    print("2) Tablolar + rejim profilleri seed...")
    asyncio.run(ensure_tables_and_seed())
    print("3) Alembic versiyon damgalaniyor...")
    stamp_alembic()
    print("4) .env guncelleniyor...")
    update_env()
    print("5) Servisler yeniden baslatiliyor...")
    restart_services()
    print_status()
    print("\nGelismis karar motoru ETKIN (PAPER + Shadow). LIVE kapali — guvenli.")
