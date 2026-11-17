"""GET and PUT /trips/auto-accept (#42) over HTTP, against a real PostgreSQL."""

from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from common_security.testing import TestAuth
from trips.adapters.persistence.tables import auto_accept_rules
from trips.infrastructure.main import create_app
from trips.infrastructure.settings import get_settings

pytestmark = pytest.mark.usefixtures("trips_database")

RULES = {"enabled": True, "maxDetourMinutes": 10, "minRating": 4.5}
DEFAULTS = {"enabled": False, "maxDetourMinutes": 5, "minRating": None}

type API = tuple[FastAPI, TestAuth, AsyncEngine]


@pytest.fixture
async def api() -> AsyncIterator[API]:
    auth = TestAuth()
    app = create_app()
    auth.install(app)
    engine = create_async_engine(get_settings().database_url)
    app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield app, auth, engine
    finally:
        # The database is shared by the whole run; only these tests use this table.
        async with engine.begin() as connection:
            await connection.execute(delete(auto_accept_rules))
        await engine.dispose()


def client(app: FastAPI, auth: TestAuth, **headers: object) -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=auth.headers(**headers),
    )


async def test_a_driver_who_never_saved_rules_gets_the_defaults(api: API) -> None:
    app, auth, _ = api
    async with client(app, auth) as driver:
        response = await driver.get("/auto-accept")

    assert response.status_code == 200, response.text
    assert response.json() == DEFAULTS


async def test_saved_rules_are_read_back(api: API) -> None:
    app, auth, _ = api
    async with client(app, auth) as driver:
        saved = await driver.put("/auto-accept", json=RULES)
        read = await driver.get("/auto-accept")

    assert saved.status_code == 200, saved.text
    assert saved.json() == RULES
    assert read.json() == RULES


async def test_saving_again_replaces_the_rules_and_turns_them_off(api: API) -> None:
    app, auth, _ = api
    off = {"enabled": False, "maxDetourMinutes": 0, "minRating": None}
    async with client(app, auth) as driver:
        await driver.put("/auto-accept", json=RULES)
        await driver.put("/auto-accept", json=off)
        read = await driver.get("/auto-accept")

    assert read.json() == off


async def test_each_driver_has_their_own_rules(api: API) -> None:
    app, auth, _ = api
    async with client(app, auth) as maya:
        await maya.put("/auto-accept", json=RULES)
    async with client(app, auth, user_id=uuid4()) as tomas:
        response = await tomas.get("/auto-accept")

    assert response.json() == DEFAULTS


@pytest.mark.parametrize(
    "change", [{"maxDetourMinutes": 31}, {"maxDetourMinutes": -1}, {"minRating": 0}]
)
async def test_invalid_rules_are_422_and_nothing_is_saved(
    api: API, change: dict[str, object]
) -> None:
    app, auth, _ = api
    async with client(app, auth) as driver:
        refused = await driver.put("/auto-accept", json={**RULES, **change})
        read = await driver.get("/auto-accept")

    assert refused.status_code == 422
    assert refused.json()["code"] == "invalid_input"
    assert read.json() == DEFAULTS


async def test_it_needs_a_token(api: API) -> None:
    app, _, _ = api
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as anyone:
        assert (await anyone.get("/auto-accept")).status_code == 401
        assert (await anyone.put("/auto-accept", json=RULES)).status_code == 401


async def test_the_database_refuses_a_detour_over_30_minutes(api: API) -> None:
    _, _, engine = api

    with pytest.raises(IntegrityError, match="ck_auto_accept_rules_valid_max_detour"):
        async with engine.begin() as connection:
            await connection.execute(
                auto_accept_rules.insert().values(
                    driver_id=uuid4(), enabled=True, max_detour_minutes=45
                )
            )
