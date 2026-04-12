from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ChangeEvent, CrawlJob, LlmsFile, PageData, Site
from app.services.classifier import classify_by_url, is_optional_section


async def generate_llms_txt(
    site: Site,
    crawl_job: CrawlJob,
    session: AsyncSession,
) -> None:
    result = await session.execute(
        select(PageData)
        .where(PageData.crawl_job_id == crawl_job.id)
        .order_by(PageData.crawled_at)
    )
    pages = result.scalars().all()
    if not pages:
        return

    _classify_pages(pages)

    existing = await session.execute(
        select(LlmsFile).where(LlmsFile.site_id == site.id)
    )
    llms_file = existing.scalar_one_or_none()

    new_summary = site.description
    display_summary = _resolve_display_summary(llms_file, new_summary)

    content = _build_markdown(site, display_summary, pages)
    content_hash = hashlib.sha256(content.encode()).hexdigest()

    old_hash = None
    if llms_file:
        old_hash = llms_file.content_hash
        llms_file.content = content
        llms_file.content_hash = content_hash
        llms_file.summary = display_summary
        llms_file.summary_generated = new_summary
        llms_file.generated_at = datetime.now(timezone.utc)
    else:
        llms_file = LlmsFile(
            site_id=site.id,
            content=content,
            content_hash=content_hash,
            summary=display_summary,
            summary_generated=new_summary,
            generated_at=datetime.now(timezone.utc),
        )
        session.add(llms_file)

    if old_hash and old_hash != content_hash:
        change_event = await _compute_change_event(
            site, crawl_job, old_hash, pages, session
        )
        session.add(change_event)

    await session.commit()


def _classify_pages(pages: list[PageData]) -> None:
    for page in pages:
        section = classify_by_url(page.url)
        if section:
            page.section = section
            page.is_optional = is_optional_section(section)
        else:
            page.section = "General"
            page.is_optional = False


def _resolve_display_summary(
    llms_file: LlmsFile | None,
    new_summary: str | None,
) -> str | None:
    if llms_file is None:
        return new_summary

    user_edited = llms_file.summary != llms_file.summary_generated
    if user_edited and llms_file.summary_generated == new_summary:
        return llms_file.summary
    return new_summary


def _build_markdown(
    site: Site,
    summary: str | None,
    pages: list[PageData],
) -> str:
    lines: list[str] = []

    lines.append(f"# {site.title or site.domain}")
    lines.append("")

    if summary:
        lines.append(f"> {summary}")
        lines.append("")

    sections: dict[str, list[PageData]] = defaultdict(list)
    optional_sections: dict[str, list[PageData]] = defaultdict(list)

    for page in pages:
        section = page.section or "General"
        if page.is_optional:
            optional_sections[section].append(page)
        else:
            sections[section].append(page)

    for section_name, section_pages in sections.items():
        lines.append(f"## {section_name}")
        lines.append("")
        for page in section_pages:
            link_text = page.title or page.url
            description = f": {page.description}" if page.description else ""
            lines.append(f"- [{link_text}]({page.url}){description}")
        lines.append("")

    if optional_sections:
        lines.append("## Optional")
        lines.append("")
        for section_name, section_pages in optional_sections.items():
            lines.append(f"### {section_name}")
            lines.append("")
            for page in section_pages:
                link_text = page.title or page.url
                description = f": {page.description}" if page.description else ""
                lines.append(f"- [{link_text}]({page.url}){description}")
            lines.append("")

    return "\n".join(lines)


async def _compute_change_event(
    site: Site,
    crawl_job: CrawlJob,
    old_hash: str,
    current_pages: list[PageData],
    session: AsyncSession,
) -> ChangeEvent:
    previous_crawl_result = await session.execute(
        select(CrawlJob)
        .where(
            CrawlJob.site_id == site.id,
            CrawlJob.status == "completed",
            CrawlJob.id != crawl_job.id,
        )
        .order_by(CrawlJob.completed_at.desc())
        .limit(1)
    )
    previous_crawl = previous_crawl_result.scalar_one_or_none()

    pages_added = 0
    pages_removed = 0
    pages_modified = 0
    changes: list[str] = []

    if previous_crawl:
        prev_pages_result = await session.execute(
            select(PageData).where(PageData.crawl_job_id == previous_crawl.id)
        )
        prev_pages = {p.url: p for p in prev_pages_result.scalars().all()}
        curr_pages = {p.url: p for p in current_pages}

        added_urls = set(curr_pages) - set(prev_pages)
        removed_urls = set(prev_pages) - set(curr_pages)

        for url in set(curr_pages) & set(prev_pages):
            curr = curr_pages[url]
            prev = prev_pages[url]
            if (curr.title != prev.title
                    or curr.description != prev.description
                    or curr.section != prev.section):
                pages_modified += 1

        pages_added = len(added_urls)
        pages_removed = len(removed_urls)

        if added_urls:
            sample = list(added_urls)[:3]
            changes.append(f"Added {', '.join(sample)}")
        if removed_urls:
            sample = list(removed_urls)[:3]
            changes.append(f"Removed {', '.join(sample)}")
        if pages_modified:
            changes.append(f"{pages_modified} page(s) modified")

    return ChangeEvent(
        site_id=site.id,
        crawl_job_id=crawl_job.id,
        detected_at=datetime.now(timezone.utc),
        old_hash=old_hash,
        pages_added=pages_added,
        pages_removed=pages_removed,
        pages_modified=pages_modified,
        summary="; ".join(changes) if changes else "llms.txt content changed",
    )
