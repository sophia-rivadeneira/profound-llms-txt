from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models import CrawlJob, Monitor, Site
from app.services import scheduler
from app.services.crawler import AUTO_PAUSE_FAILURE_THRESHOLD, _finalize_monitor


async def _make_site(session, url: str = "https://example.com/") -> Site:
    site = Site(url=url, domain="example.com", slug=None)
    session.add(site)
    await session.flush()
    return site


async def _make_monitor(
    session,
    site: Site,
    *,
    is_active: bool = True,
    next_check_at: datetime | None = None,
    interval_hours: int = 24,
    last_checked_at: datetime | None = None,
) -> Monitor:
    monitor = Monitor(
        site_id=site.id,
        interval_hours=interval_hours,
        is_active=is_active,
        next_check_at=next_check_at,
        last_checked_at=last_checked_at,
    )
    session.add(monitor)
    await session.flush()
    return monitor


async def _seed_failed_crawls(session, site: Site, count: int) -> None:
    """Insert `count` failed crawl_jobs for the site so _count_trailing_failures
    has real history to derive from."""
    for _ in range(count):
        session.add(
            CrawlJob(
                site_id=site.id,
                triggered_by="scheduled",
                status="failed",
                completed_at=datetime.now(timezone.utc),
            )
        )
    await session.flush()


async def _seed_completed_crawl(session, site: Site) -> None:
    session.add(
        CrawlJob(
            site_id=site.id,
            triggered_by="scheduled",
            status="completed",
            completed_at=datetime.now(timezone.utc),
        )
    )
    await session.flush()


class TestFinalizeMonitor:
    async def test_success_bumps_timestamps(self, session):
        site = await _make_site(session)
        await _make_monitor(session, site)
        await session.commit()

        await _finalize_monitor(site.id, session, success=True)

        monitor = await session.scalar(select(Monitor).where(Monitor.site_id == site.id))
        assert monitor.last_checked_at is not None
        assert monitor.next_check_at is not None
        assert monitor.next_check_at > monitor.last_checked_at
        delta = monitor.next_check_at - monitor.last_checked_at
        assert abs(delta - timedelta(hours=24)) < timedelta(seconds=1)
        assert monitor.is_active is True

    async def test_single_failure_stays_active(self, session):
        """One failure with no history shouldn't auto-pause."""
        site = await _make_site(session)
        await _make_monitor(session, site)
        # Seed one failed crawl (the one that just "finished" before _finalize_monitor ran).
        await _seed_failed_crawls(session, site, 1)
        await session.commit()

        await _finalize_monitor(site.id, session, success=False)

        monitor = await session.scalar(select(Monitor).where(Monitor.site_id == site.id))
        assert monitor.is_active is True
        assert monitor.last_checked_at is not None
        assert monitor.next_check_at is not None

    async def test_three_trailing_failures_auto_pauses(self, session):
        """Auto-pause fires when the derived count of trailing 'failed' rows
        in crawl_jobs hits the threshold — not by tracking a stored counter."""
        site = await _make_site(session)
        await _make_monitor(session, site)
        await _seed_failed_crawls(session, site, AUTO_PAUSE_FAILURE_THRESHOLD)
        await session.commit()

        await _finalize_monitor(site.id, session, success=False)

        monitor = await session.scalar(select(Monitor).where(Monitor.site_id == site.id))
        assert monitor.is_active is False

    async def test_completed_crawl_breaks_the_failure_run(self, session):
        """A 'completed' row in the history resets the derived count: two
        failures before a success + two after should NOT auto-pause."""
        site = await _make_site(session)
        await _make_monitor(session, site)
        # Oldest-first: 2 failed, 1 completed, 2 failed (the most recent)
        await _seed_failed_crawls(session, site, 2)
        await _seed_completed_crawl(session, site)
        await _seed_failed_crawls(session, site, 2)
        await session.commit()

        await _finalize_monitor(site.id, session, success=False)

        monitor = await session.scalar(select(Monitor).where(Monitor.site_id == site.id))
        assert monitor.is_active is True  # only 2 trailing failures, < 3

    async def test_paused_monitor_does_not_bump_next_check_at(self, session):
        """Manual re-crawl of a user-paused monitor shouldn't drift its
        next_check_at — PATCH /monitor resets it on resume anyway."""
        site = await _make_site(session)
        frozen_next_check = datetime.now(timezone.utc) + timedelta(hours=48)
        await _make_monitor(
            session,
            site,
            is_active=False,
            next_check_at=frozen_next_check,
        )
        await session.commit()

        await _finalize_monitor(site.id, session, success=True)

        monitor = await session.scalar(select(Monitor).where(Monitor.site_id == site.id))
        assert monitor.next_check_at == frozen_next_check
        assert monitor.last_checked_at is not None  # still updates this

    async def test_paused_monitor_failure_does_not_reauto_pause(self, session):
        """A failure on an already-paused monitor is a no-op — we're not
        running the auto-pause check at all when is_active is already False."""
        site = await _make_site(session)
        await _make_monitor(session, site, is_active=False)
        await _seed_failed_crawls(session, site, AUTO_PAUSE_FAILURE_THRESHOLD + 5)
        await session.commit()

        await _finalize_monitor(site.id, session, success=False)

        monitor = await session.scalar(select(Monitor).where(Monitor.site_id == site.id))
        assert monitor.is_active is False  # unchanged, didn't flip anything

    async def test_missing_monitor_is_noop(self, session):
        site = await _make_site(session)
        await session.commit()

        # No monitor exists for this site — should not raise.
        await _finalize_monitor(site.id, session, success=True)

        count = await session.scalar(
            select(Monitor).where(Monitor.site_id == site.id).exists().select()
        )
        assert count is False


class TestTick:
    @pytest.fixture(autouse=True)
    def patch_session_local_and_crawl(self, monkeypatch, session_factory):
        """Bind scheduler's session factory to the test engine and stub out the crawler."""
        dispatched: list[tuple[int, int]] = []

        async def fake_run_crawl(site_id: int, job_id: int) -> None:
            dispatched.append((site_id, job_id))

        monkeypatch.setattr(scheduler, "AsyncSessionLocal", session_factory)
        monkeypatch.setattr(scheduler, "run_crawl_in_background", fake_run_crawl)
        self.dispatched = dispatched
        self.session_factory_ref = session_factory

    async def _drain_dispatched_tasks(self) -> None:
        # _tick creates dispatch tasks via asyncio.create_task; yield so they run.
        for _ in range(5):
            await asyncio.sleep(0)

    async def test_dispatches_due_active_monitor(self, session):
        past = datetime.now(timezone.utc) - timedelta(minutes=1)
        site = await _make_site(session)
        await _make_monitor(session, site, is_active=True, next_check_at=past)
        await session.commit()

        await scheduler._tick()
        await self._drain_dispatched_tasks()

        assert len(self.dispatched) == 1
        assert self.dispatched[0][0] == site.id

    async def test_skips_inactive_monitor(self, session):
        past = datetime.now(timezone.utc) - timedelta(minutes=1)
        site = await _make_site(session)
        await _make_monitor(session, site, is_active=False, next_check_at=past)
        await session.commit()

        await scheduler._tick()
        await self._drain_dispatched_tasks()

        assert self.dispatched == []

    async def test_skips_future_monitor(self, session):
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        site = await _make_site(session)
        await _make_monitor(session, site, is_active=True, next_check_at=future)
        await session.commit()

        await scheduler._tick()
        await self._drain_dispatched_tasks()

        assert self.dispatched == []

    async def test_advances_next_check_at_within_tick(self, session, session_factory):
        past = datetime.now(timezone.utc) - timedelta(minutes=1)
        site = await _make_site(session)
        site_id = site.id
        await _make_monitor(
            session, site, is_active=True, next_check_at=past, interval_hours=6
        )
        await session.commit()

        await scheduler._tick()
        await self._drain_dispatched_tasks()

        async with session_factory() as s2:
            monitor = await s2.scalar(
                select(Monitor).where(Monitor.site_id == site_id)
            )
            assert monitor.next_check_at > datetime.now(timezone.utc) + timedelta(hours=5)
            assert monitor.next_check_at < datetime.now(timezone.utc) + timedelta(hours=7)

    async def test_creates_scheduled_crawl_job_row(self, session):
        past = datetime.now(timezone.utc) - timedelta(minutes=1)
        site = await _make_site(session)
        await _make_monitor(session, site, is_active=True, next_check_at=past)
        await session.commit()

        await scheduler._tick()
        await self._drain_dispatched_tasks()

        result = await session.execute(
            select(CrawlJob).where(CrawlJob.site_id == site.id)
        )
        jobs = result.scalars().all()
        assert len(jobs) == 1
        assert jobs[0].triggered_by == "scheduled"
        assert jobs[0].status == "pending"

    async def test_skips_monitor_with_active_crawl(self, session):
        """The unique partial index on crawl_jobs enforces this at the DB
        level: an existing pending/running row for the same site causes the
        scheduler's insert to raise IntegrityError, which _tick catches and
        skips. next_check_at still advances (phase 1) so we don't busy-loop."""
        past = datetime.now(timezone.utc) - timedelta(minutes=1)
        site = await _make_site(session)
        await _make_monitor(
            session, site, is_active=True, next_check_at=past, interval_hours=6
        )
        running_job = CrawlJob(
            site_id=site.id, triggered_by="manual", status="running"
        )
        session.add(running_job)
        await session.commit()

        await scheduler._tick()
        await self._drain_dispatched_tasks()

        assert self.dispatched == []
        # No new scheduled job was created.
        result = await session.execute(
            select(CrawlJob).where(
                CrawlJob.site_id == site.id,
                CrawlJob.triggered_by == "scheduled",
            )
        )
        assert result.scalars().all() == []
        # next_check_at was advanced so we don't re-check this monitor next
        # tick while the manual crawl is still running.
        async with self.session_factory_ref() as s2:
            monitor = await s2.scalar(
                select(Monitor).where(Monitor.site_id == site.id)
            )
            assert monitor.next_check_at > datetime.now(timezone.utc) + timedelta(hours=5)

    async def test_dispatches_multiple_due_monitors(self, session):
        past = datetime.now(timezone.utc) - timedelta(minutes=1)
        site_a = await _make_site(session, url="https://a.example.com/")
        site_a.domain = "a.example.com"
        site_a.slug = "a"
        site_b = await _make_site(session, url="https://b.example.com/")
        site_b.domain = "b.example.com"
        site_b.slug = "b"
        await _make_monitor(session, site_a, is_active=True, next_check_at=past)
        await _make_monitor(session, site_b, is_active=True, next_check_at=past)
        await session.commit()

        await scheduler._tick()
        await self._drain_dispatched_tasks()

        assert len(self.dispatched) == 2
        assert {s for s, _ in self.dispatched} == {site_a.id, site_b.id}


class TestLoopExceptionIsolation:
    async def test_loop_survives_tick_exception(self, monkeypatch):
        call_count = {"n": 0}

        async def flaky_tick() -> None:
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise RuntimeError("boom")

        monkeypatch.setattr(scheduler, "_tick", flaky_tick)
        monkeypatch.setattr(scheduler, "TICK_INTERVAL_SECONDS", 0.005)

        task = asyncio.create_task(scheduler._loop())
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert call_count["n"] >= 2
