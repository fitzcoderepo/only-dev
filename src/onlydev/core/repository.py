from __future__ import annotations

from typing import Iterable, Optional, Sequence
from datetime import datetime, timezone
from dataclasses import asdict
import sqlite3

from onlydev.core.models import Source, Job

""" 
Data access layer where read/write of application data happens. Bridges models.py and db.py, translating py objects and DB rows
(takes a Job dataclass in, writes SQL out, reads SQL back, returns a Job dataclass)
"""


def utc_now_iso() -> str: return datetime.now(timezone.utc).isoformat(timespec='seconds')

# For each keyword, if it exists and still has content after stripping whitespace, include its stripped version.
# filters out None, "", and other falsy values, strips whitespace, if stripped result is empty(" " -> ""), filter it out
def _kw_serialize(keywords: Sequence[str]) -> str:
    # switch to json later
    return ",".join(k.strip() for k in keywords if k and k.strip())


# convert comma separated string from DB back into a clean tuple of keywords. 
# Example: "Python, Django ,Next.js" → ("Python", "Django", "Next.js")
# If the string is empty or None, return an empty tuple.
# Otherwise, split by commas, trim each piece, and return only the non-empty cleaned values as a tuple.
def _kw_deserialize(s: str | None) -> tuple[str, ...]:
    if not s:
        return tuple()
    return tuple(x.strip() for x in s.split(",") if x.strip())


# tracking
def insert_run_count(
    conn: sqlite3.Connection,
    run_utc: str,
    company_key: str,
    match_count: int,
    new_count: int,
) -> None:
    source_type = company_key.split(":", 1)[0]

    conn.execute(
        """
        INSERT INTO job_run_counts (run_utc, source_type, company_key, match_count, new_count)
        VALUES (?, ?, ?, ?, ?)
        """,
        (run_utc, source_type, company_key, match_count, new_count),
    )
    conn.commit()

# --------------------------------------------------------------------------------------------------------
# --------------------------------------------------------------------------------------------------------
# Sources
# --------------------------------------------------------------------------------------------------------
# --------------------------------------------------------------------------------------------------------

def upsert_source(conn: sqlite3.Connection, source: Source) -> int:
    """
    Insert or update a source by root_url. Returns source_id.
    - If new: sets first_seen_utc + last_seen_utc to now.
    - If existing: updates last_seen_utc, active, source_type, discovered_from.
    """
    now = utc_now_iso()

    conn.execute(
        """
        INSERT INTO sources (source_type, root_url, discovered_from, active, first_seen_utc, last_seen_utc)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(root_url) DO UPDATE SET
            source_type=excluded.source_type,
            discovered_from=excluded.discovered_from,
            active=excluded.active,
            last_seen_utc=excluded.last_seen_utc
        """,
        (
            source.source_type,
            source.root_url,
            source.discovered_from,
            1 if source.active else 0,
            now,
            now,
        ),
    )
    conn.commit()

    row = conn.execute(
        'SELECT id FROM sources WHERE root_url = ?', (source.root_url,),
    ).fetchone()

    return int(row['id'])


def list_active_sources(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        'SELECT id, source_type, root_url FROM sources WHERE active=1 ORDER BY last_seen_utc DESC'
    ).fetchall()


def set_source_active(conn: sqlite3.Connection, source_id: int, active: bool) -> None:
    conn.execute(
        'UPDATE sources SET active=? WHERE id=?', (1 if active else 0, source_id),
    )
    conn.commit()

# --------------------------------------------------------------------------------------------------------
# --------------------------------------------------------------------------------------------------------
# Jobs
# --------------------------------------------------------------------------------------------------------
# --------------------------------------------------------------------------------------------------------

def get_job_by_url(conn: sqlite3.Connection, job_url: str) -> Optional[sqlite3.Row]:
    return conn.execute(
        'SELECT * FROM jobs WHERE job_url=?',
        (job_url,),
    ).fetchone()


def upsert_job(conn: sqlite3.Connection, source_id: int, job: Job) -> tuple[int, bool]:
    """
    Upsert a job by job_url. Returns (job_id, is_new).

    is_new == True only when the job is inserted for the first time.
    """
    now = utc_now_iso()

    existing = conn.execute(
        'SELECT id, first_seen_utc FROM jobs WHERE job_url=?',
        (job.job_url,),
    ).fetchone()

    matched = _kw_serialize(job.matched_keywords)

    if existing is None:
        cur = conn.execute(
        """
        INSERT INTO jobs (
            source_id, job_url, title, company, location_text, description_text,
            is_remote, matched_keywords, department, office, job_updated_at,
            first_seen_utc, last_seen_utc
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            source_id,
            job.job_url,
            job.title,
            job.company,
            job.location_text,
            job.description_text,
            1 if job.is_remote else 0,
            matched,
            job.department,
            job.office,
            job.job_updated_at,
            now,
            now,
        ),
    )
        conn.commit()
        return int(cur.lastrowid), True

    # Update existing
    conn.execute(
        """
        UPDATE jobs SET
            source_id=?,
            title=?,
            company=?,
            location_text=?,
            description_text=?,
            is_remote=?,
            matched_keywords=?,
            department=?,
            office=?,
            job_updated_at=?,
            last_seen_utc=?
        WHERE job_url=?
        """,
        (
            source_id,
            job.title,
            job.company,
            job.location_text,
            job.description_text,
            1 if job.is_remote else 0,
            matched,
            job.department,
            job.office,
            job.job_updated_at,
            now,
            job.job_url,
        ),
    )
    conn.commit()
    return int(existing['id']), False


def list_jobs_for_source(conn: sqlite3.Connection, source_id: int, limit: int = 200) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT *
        FROM jobs
        WHERE source_id=?
        ORDER BY last_seen_utc DESC
        LIMIT ?
        """,
        (source_id, limit),
    ).fetchall()


def mark_missing_jobs_inactive(
    conn: sqlite3.Connection,
    source_id: int,
    seen_job_urls: Iterable[str],
) -> int:
    """
    Marks jobs as inactive if they were not seen in the latest monitor run.
    Returns the number of jobs marked inactive.
    """
    seen = set(seen_job_urls)

    rows = conn.execute(
        "SELECT id, job_url FROM jobs WHERE source_id=? AND active=1",
        (source_id,),
    ).fetchall()

    inactive_ids = [row["id"] for row in rows if row["job_url"] not in seen]

    if inactive_ids:
        conn.execute(
            f"UPDATE jobs SET active=0 WHERE id IN ({','.join('?' * len(inactive_ids))})",
            inactive_ids,
        )
        conn.commit()

    return len(inactive_ids)



