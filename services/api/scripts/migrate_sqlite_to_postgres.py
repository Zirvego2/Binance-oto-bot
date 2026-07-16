#!/usr/bin/env python3
"""Yerel SQLite veritabanini sunucu PostgreSQL'e aktarir.

Kullanim (sunucuda, api/worker durdurulmusken):
    docker compose stop api worker
    docker compose exec -T api python scripts/migrate_sqlite_to_postgres.py /tmp/trading_bot.db
    docker compose start api worker

Onkosul:
    - APP_SECRET ve APP_ENCRYPTION_KEY local ile sunucu .env'de AYNI olmali
      (sifreli profil alanlari bozulmasin diye).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

# shared.db modellerini metadata'ya kaydet
import shared.db  # noqa: F401
from shared.db import Base

SKIP_TABLES = {
    "dev_agent_runs",
    "dev_agent_status",
    "dev_proposals",
    "dev_tasks",
    "sqlite_sequence",
}


def _sqlite_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    rows = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
    return [r[1] for r in rows]


def _normalize_value(value):
    if isinstance(value, memoryview):
        return bytes(value)
    return value


async def _pg_columns(conn, table: str) -> tuple[list[str], dict[str, str], dict[str, str]]:
    rows = await conn.fetch(
        """
        SELECT column_name, data_type, udt_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = $1
        ORDER BY ordinal_position
        """,
        table,
    )
    names = [r["column_name"] for r in rows]
    types = {r["column_name"]: r["data_type"] for r in rows}
    udts = {r["column_name"]: r["udt_name"] for r in rows}
    return names, types, udts


def _is_json_column(pg_type: str, udt_name: str) -> bool:
    return pg_type in {"json", "jsonb"} or udt_name in {"json", "jsonb"}


def _parse_datetime(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    if " " in text and "T" not in text:
        text = text.replace(" ", "T", 1)
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _parse_date(value: str) -> date:
    return date.fromisoformat(value.strip()[:10])


def _coerce_value(value, pg_type: str, udt_name: str = ""):
    if value is None:
        return None

    if pg_type == "boolean":
        if isinstance(value, int):
            return bool(value)
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "t", "yes"}
        return bool(value)

    if _is_json_column(pg_type, udt_name):
        if isinstance(value, (list, dict)):
            return json.dumps(value, ensure_ascii=False)
        return value

    if isinstance(value, str):
        if pg_type in {"timestamp with time zone", "timestamp without time zone"}:
            return _parse_datetime(value)
        if pg_type == "date":
            return _parse_date(value)
        if pg_type in {"numeric", "double precision", "real"}:
            return Decimal(value)
        if pg_type in {"integer", "bigint", "smallint"}:
            return int(value)

    if pg_type in {"numeric", "double precision", "real"} and isinstance(value, (int, float)):
        return Decimal(str(value))

    return _normalize_value(value)


async def migrate(sqlite_path: Path, database_url: str) -> None:
    if not sqlite_path.is_file():
        raise SystemExit(f"SQLite dosyasi bulunamadi: {sqlite_path}")

    dsn = database_url.replace("postgresql+asyncpg://", "postgresql://")
    import asyncpg

    sqlite_conn = sqlite3.connect(str(sqlite_path))
    sqlite_conn.row_factory = sqlite3.Row

    pg_conn = await asyncpg.connect(dsn)

    try:
        model_tables = {t.name for t in Base.metadata.sorted_tables}
        sqlite_tables = {
            r[0]
            for r in sqlite_conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        }
        tables = [t.name for t in Base.metadata.sorted_tables if t.name in sqlite_tables and t.name not in SKIP_TABLES]

        skipped = sqlite_tables - model_tables - SKIP_TABLES
        if skipped:
            print(f"Atlanan (SQLite-only) tablolar: {', '.join(sorted(skipped))}")

        print(f"Aktarilacak tablo sayisi: {len(tables)}")

        await pg_conn.execute("SET session_replication_role = 'replica';")

        existing = await pg_conn.fetch(
            """
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'public'
            """
        )
        pg_table_names = [r["tablename"] for r in existing]
        if pg_table_names:
            quoted = ", ".join(f'"{t}"' for t in pg_table_names)
            await pg_conn.execute(f"TRUNCATE {quoted} RESTART IDENTITY CASCADE;")
            print(f"PostgreSQL tablolari temizlendi ({len(pg_table_names)} tablo).")

        total_rows = 0
        for table in tables:
            sqlite_cols = _sqlite_columns(sqlite_conn, table)
            pg_cols, pg_types, pg_udts = await _pg_columns(pg_conn, table)
            cols = [c for c in sqlite_cols if c in pg_cols]
            if not cols:
                print(f"  - {table}: ortak kolon yok, atlandi")
                continue

            rows = sqlite_conn.execute(f'SELECT * FROM "{table}"').fetchall()
            if not rows:
                print(f"  - {table}: 0 kayit")
                continue

            col_list = ", ".join(f'"{c}"' for c in cols)
            placeholders = ", ".join(f"${i + 1}" for i in range(len(cols)))
            sql = f'INSERT INTO "{table}" ({col_list}) VALUES ({placeholders})'

            batch_size = 500
            inserted = 0
            for i in range(0, len(rows), batch_size):
                batch = rows[i : i + batch_size]
                async with pg_conn.transaction():
                    for row in batch:
                        values = [_coerce_value(row[c], pg_types[c], pg_udts[c]) for c in cols]
                        try:
                            await pg_conn.execute(sql, *values)
                        except Exception as exc:
                            raise RuntimeError(f"Insert hatasi tablo={table}, kolonlar={cols}") from exc
                inserted += len(batch)

            total_rows += inserted
            print(f"  - {table}: {inserted} kayit")

        await pg_conn.execute("SET session_replication_role = 'origin';")

        version_row = sqlite_conn.execute("SELECT version_num FROM alembic_version").fetchone()
        if version_row:
            await pg_conn.execute("DELETE FROM alembic_version")
            await pg_conn.execute(
                "INSERT INTO alembic_version (version_num) VALUES ($1)",
                version_row[0],
            )
            print(f"Alembic surumu: {version_row[0]}")

        print(f"\nTamamlandi. Toplam {total_rows} satir aktarildi.")
    finally:
        sqlite_conn.close()
        await pg_conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="SQLite -> PostgreSQL veri aktarimi")
    parser.add_argument(
        "sqlite_path",
        nargs="?",
        default="/tmp/trading_bot.db",
        help="SQLite dosya yolu (varsayilan: /tmp/trading_bot.db)",
    )
    parser.add_argument(
        "--database-url",
        default="",
        help="PostgreSQL URL (varsayilan: DATABASE_URL ortam degiskeni)",
    )
    args = parser.parse_args()

    database_url = args.database_url
    if not database_url:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from app.core.config import get_settings

        database_url = get_settings().database_url

    if not database_url.startswith("postgresql"):
        raise SystemExit(f"Gecersiz DATABASE_URL: {database_url}")

    asyncio.run(migrate(Path(args.sqlite_path), database_url))


if __name__ == "__main__":
    main()
