"""API entegrasyon testleri icin ortak fixture'lar.

Gercek PostgreSQL/Redis GEREKTIRMEZ: SQLite (aiosqlite) ve fakeredis
kullanilir. Binance'e gercek HTTP istegi ATILMAZ; gerekli yerlerde adapter
mocklanir.
"""

from __future__ import annotations

import os
import uuid

os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///./test_integration_{uuid.uuid4().hex}.db")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("APP_SECRET", "test-secret")
os.environ.setdefault("ADMIN_EMAIL", "admin@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "TestPassword123!")
os.environ.setdefault("SECURE_COOKIES", "false")
os.environ.setdefault("ENABLE_LIVE_TRADING", "false")
os.environ.setdefault("ENABLE_DEMO_TRADING", "false")

import fakeredis.aioredis
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from sqlalchemy import select

from app.core.database import AsyncSessionLocal, create_all_tables
from app.core.security import hash_password
from app.main import app
from app.api.deps import get_redis_dep
from shared.db import Admin, AdminSession

_fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)


async def _override_get_redis():
    return _fake_redis


app.dependency_overrides[get_redis_dep] = _override_get_redis


@pytest_asyncio.fixture(autouse=True)
async def _setup_database():
    await create_all_tables()
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Admin).where(Admin.email == "admin@example.com"))
        if result.scalar_one_or_none() is None:
            admin = Admin(email="admin@example.com", password_hash=hash_password("TestPassword123!"))
            session.add(admin)
            await session.commit()
    yield


@pytest_asyncio.fixture
async def client():
    await _fake_redis.flushall()
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Admin).where(Admin.email == "admin@example.com"))
        admin = result.scalar_one_or_none()
        if admin is not None:
            admin.failed_login_count = 0
            admin.locked_until = None
        await session.execute(AdminSession.__table__.delete())
        await session.commit()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest_asyncio.fixture
async def authenticated_client(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/login", json={"email": "admin@example.com", "password": "TestPassword123!"}
    )
    assert response.status_code == 200, response.text
    csrf_token = response.json()["csrf_token"]
    client.headers.update({"X-CSRF-Token": csrf_token})
    return client
