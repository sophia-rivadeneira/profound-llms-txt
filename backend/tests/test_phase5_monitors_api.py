from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db.session import get_db
from app.main import app
from app.models import CrawlJob, Monitor, Site
from app.routers import crawls as crawls_router
from app.routers import sites as sites_router
from app.services import scheduler


@pytest_asyncio.fixture
async def client(session_factory, monkeypatch):
    """ASGI test client with DB overridden to the test session factory and
    background crawl + scheduler patched out so nothing touches the real DB
    or spawns real HTTP work."""

    async def _override_get_db():
        async with session_factory() as s:
            yield s

    async def _noop_run_crawl(site_id: int, job_id: int) -> None:
        return None

    def _noop_start() -> None:
        return None

    async def _noop_stop() -> None:
        return None

    monkeypatch.setattr(sites_router, "run_crawl_in_background", _noop_run_crawl)
    monkeypatch.setattr(crawls_router, "run_crawl_in_background", _noop_run_crawl)
    monkeypatch.setattr(scheduler, "start", _noop_start)
    monkeypatch.setattr(scheduler, "stop", _noop_stop)
    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_db, None)


class TestMonitorAutoCreate:
    async def test_post_sites_creates_monitor_with_defaults(
        self, client, session_factory
    ):
        resp = await client.post("/sites", json={"url": "https://example.com"})
        assert resp.status_code == 201
        site_id = resp.json()["site"]["id"]

        async with session_factory() as s:
            monitor = await s.scalar(
                select(Monitor).where(Monitor.site_id == site_id)
            )
            assert monitor is not None
            assert monitor.is_active is True
            assert monitor.interval_hours == 24
            assert monitor.next_check_at is not None
            now = datetime.now(timezone.utc)
            assert monitor.next_check_at > now + timedelta(hours=23)
            assert monitor.next_check_at < now + timedelta(hours=25)

    async def test_duplicate_post_does_not_create_second_monitor(
        self, client, session_factory
    ):
        r1 = await client.post("/sites", json={"url": "https://example.com"})
        assert r1.status_code == 201
        r2 = await client.post("/sites", json={"url": "https://example.com"})
        assert r2.status_code == 201
        assert r1.json()["site"]["id"] == r2.json()["site"]["id"]

        async with session_factory() as s:
            result = await s.execute(select(Monitor))
            monitors = result.scalars().all()
            assert len(monitors) == 1


class TestGetMonitor:
    async def test_returns_all_fields(self, client, session_factory):
        resp = await client.post("/sites", json={"url": "https://example.com"})
        site_id = resp.json()["site"]["id"]

        r = await client.get(f"/sites/{site_id}/monitor")
        assert r.status_code == 200
        body = r.json()
        assert body["site_id"] == site_id
        assert body["interval_hours"] == 24
        assert body["is_active"] is True
        assert body["next_check_at"] is not None
        assert body["last_checked_at"] is None
        # paused_reason and consecutive_failures were dropped — the monitors
        # table no longer stores cause or counter, and the frontend renders
        # one unified "Paused" panel regardless of cause.
        assert "paused_reason" not in body
        assert "consecutive_failures" not in body

    async def test_404_when_site_missing(self, client):
        r = await client.get("/sites/99999/monitor")
        assert r.status_code == 404


class TestPatchMonitorValidation:
    async def test_rejects_interval_zero(self, client):
        resp = await client.post("/sites", json={"url": "https://example.com"})
        site_id = resp.json()["site"]["id"]

        r = await client.patch(
            f"/sites/{site_id}/monitor", json={"interval_hours": 0}
        )
        assert r.status_code == 422

    async def test_rejects_interval_above_168(self, client):
        resp = await client.post("/sites", json={"url": "https://example.com"})
        site_id = resp.json()["site"]["id"]

        r = await client.patch(
            f"/sites/{site_id}/monitor", json={"interval_hours": 169}
        )
        assert r.status_code == 422

    async def test_accepts_interval_1(self, client):
        resp = await client.post("/sites", json={"url": "https://example.com"})
        site_id = resp.json()["site"]["id"]

        r = await client.patch(
            f"/sites/{site_id}/monitor", json={"interval_hours": 1}
        )
        assert r.status_code == 200
        assert r.json()["interval_hours"] == 1

    async def test_accepts_interval_168(self, client):
        resp = await client.post("/sites", json={"url": "https://example.com"})
        site_id = resp.json()["site"]["id"]

        r = await client.patch(
            f"/sites/{site_id}/monitor", json={"interval_hours": 168}
        )
        assert r.status_code == 200
        assert r.json()["interval_hours"] == 168

    async def test_rejects_empty_body(self, client):
        """PATCH with no fields set is a pointless no-op; reject it loudly."""
        resp = await client.post("/sites", json={"url": "https://example.com"})
        site_id = resp.json()["site"]["id"]

        r = await client.patch(f"/sites/{site_id}/monitor", json={})
        assert r.status_code == 422


class TestPatchMonitorBehavior:
    async def test_interval_change_recomputes_next_check_at(
        self, client, session_factory
    ):
        resp = await client.post("/sites", json={"url": "https://example.com"})
        site_id = resp.json()["site"]["id"]

        r = await client.patch(
            f"/sites/{site_id}/monitor", json={"interval_hours": 6}
        )
        assert r.status_code == 200

        async with session_factory() as s:
            monitor = await s.scalar(
                select(Monitor).where(Monitor.site_id == site_id)
            )
            now = datetime.now(timezone.utc)
            # last_checked_at is None → base is "now" per the router
            assert monitor.next_check_at > now + timedelta(hours=5)
            assert monitor.next_check_at < now + timedelta(hours=7)

    async def test_pause_flips_is_active(
        self, client, session_factory
    ):
        resp = await client.post("/sites", json={"url": "https://example.com"})
        site_id = resp.json()["site"]["id"]

        r = await client.patch(
            f"/sites/{site_id}/monitor", json={"is_active": False}
        )
        assert r.status_code == 200

        async with session_factory() as s:
            monitor = await s.scalar(
                select(Monitor).where(Monitor.site_id == site_id)
            )
            assert monitor.is_active is False

    async def test_resume_fires_next_check_immediately(
        self, client, session_factory
    ):
        """On resume, next_check_at is reset to roughly 'now' so the next
        scheduler tick picks the monitor up and re-checks the site — giving
        the user instant feedback on whether it has recovered."""
        resp = await client.post("/sites", json={"url": "https://example.com"})
        site_id = resp.json()["site"]["id"]

        # Simulate an auto-paused monitor: flip is_active off directly.
        async with session_factory() as s:
            monitor = await s.scalar(
                select(Monitor).where(Monitor.site_id == site_id)
            )
            monitor.is_active = False
            await s.commit()

        r = await client.patch(
            f"/sites/{site_id}/monitor", json={"is_active": True}
        )
        assert r.status_code == 200

        async with session_factory() as s:
            monitor = await s.scalar(
                select(Monitor).where(Monitor.site_id == site_id)
            )
            assert monitor.is_active is True
            now = datetime.now(timezone.utc)
            assert monitor.next_check_at is not None
            assert abs(monitor.next_check_at - now) < timedelta(seconds=5)


class TestActiveCrawlUniqueness:
    async def test_manual_retrigger_with_active_crawl_returns_409(
        self, client, session_factory
    ):
        """POST /sites/{id}/crawls with a pending/running crawl already in
        the table is rejected by the unique partial index on crawl_jobs,
        which the router catches and converts to a 409."""
        resp = await client.post("/sites", json={"url": "https://example.com"})
        site_id = resp.json()["site"]["id"]

        # POST /sites auto-inserted a pending "initial" crawl already.
        r = await client.post(f"/sites/{site_id}/crawls")
        assert r.status_code == 409

        async with session_factory() as s:
            result = await s.execute(
                select(CrawlJob).where(CrawlJob.site_id == site_id)
            )
            jobs = result.scalars().all()
            assert len(jobs) == 1
            assert jobs[0].triggered_by == "manual"

    async def test_manual_trigger_succeeds_after_crawl_completes(
        self, client, session_factory
    ):
        resp = await client.post("/sites", json={"url": "https://example.com"})
        site_id = resp.json()["site"]["id"]

        async with session_factory() as s:
            initial = await s.scalar(
                select(CrawlJob).where(CrawlJob.site_id == site_id)
            )
            initial.status = "completed"
            await s.commit()

        r = await client.post(f"/sites/{site_id}/crawls")
        assert r.status_code == 201
