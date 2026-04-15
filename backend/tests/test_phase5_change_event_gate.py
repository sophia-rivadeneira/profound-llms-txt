from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.models import ChangeEvent, CrawlJob, LlmsFile, PageData, Site
from app.services.generator import generate_llms_txt


async def _make_site(session) -> Site:
    site = Site(url="https://example.com/", domain="example.com", slug="example-com")
    session.add(site)
    await session.flush()
    return site


async def _make_crawl_with_pages(
    session, site: Site, page_titles: list[tuple[str, str]]
) -> CrawlJob:
    crawl = CrawlJob(
        site_id=site.id,
        triggered_by="scheduled",
        status="completed",
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
    )
    session.add(crawl)
    await session.flush()
    for url, title in page_titles:
        session.add(
            PageData(
                crawl_job_id=crawl.id,
                url=url,
                title=title,
                description=None,
                section="Docs",
                is_optional=False,
            )
        )
    await session.flush()
    return crawl


class TestChangeEventGate:
    async def test_no_event_on_first_crawl(self, session):
        site = await _make_site(session)
        crawl = await _make_crawl_with_pages(
            session,
            site,
            [
                ("https://example.com/", "Home"),
                ("https://example.com/docs", "Docs"),
            ],
        )
        await session.commit()

        await generate_llms_txt(site, crawl, session)

        llms = await session.scalar(select(LlmsFile).where(LlmsFile.site_id == site.id))
        assert llms is not None  # file was generated
        events = (
            await session.execute(select(ChangeEvent).where(ChangeEvent.site_id == site.id))
        ).scalars().all()
        assert events == []

    async def test_no_event_on_unchanged_recrawl(self, session):
        site = await _make_site(session)
        crawl1 = await _make_crawl_with_pages(
            session,
            site,
            [("https://example.com/", "Home"), ("https://example.com/docs", "Docs")],
        )
        await session.commit()
        await generate_llms_txt(site, crawl1, session)

        crawl2 = await _make_crawl_with_pages(
            session,
            site,
            [("https://example.com/", "Home"), ("https://example.com/docs", "Docs")],
        )
        await session.commit()
        await generate_llms_txt(site, crawl2, session)

        events = (
            await session.execute(select(ChangeEvent).where(ChangeEvent.site_id == site.id))
        ).scalars().all()
        assert events == []

    async def test_event_created_when_content_changes(self, session):
        site = await _make_site(session)
        crawl1 = await _make_crawl_with_pages(
            session, site, [("https://example.com/", "Home")]
        )
        await session.commit()
        await generate_llms_txt(site, crawl1, session)

        crawl2 = await _make_crawl_with_pages(
            session,
            site,
            [
                ("https://example.com/", "Home"),
                ("https://example.com/new", "New Page"),
            ],
        )
        await session.commit()
        await generate_llms_txt(site, crawl2, session)

        events = (
            await session.execute(select(ChangeEvent).where(ChangeEvent.site_id == site.id))
        ).scalars().all()
        assert len(events) == 1
        assert events[0].crawl_job_id == crawl2.id
