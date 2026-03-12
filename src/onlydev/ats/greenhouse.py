from __future__ import annotations

from urllib.parse import urlparse
import requests

from onlydev.core.models import Job
from onlydev.core.config import get


HEADERS = {"User-Agent": "OnlyDev/0.1"}


class GreenhouseNotFound(Exception):
    pass


def _board_from_root(root_url: str) -> str:
    # root_url: https://boards.greenhouse.io/<board>
    path = urlparse(root_url).path.strip("/")
    parts = path.split("/")
    return parts[0] if parts and parts[0] else ""


def fetch_greenhouse_jobs(root_url: str) -> list[Job]:
    board = _board_from_root(root_url)
    if not board:
        raise ValueError(f"Invalid Greenhouse root_url (no board): {root_url}")

    api = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs"
    r = requests.get(api, headers=HEADERS, timeout=25)

    if r.status_code == 404:
        raise GreenhouseNotFound(f"Greenhouse board not found: {board}")
    if r.status_code != 200:
        raise RuntimeError(
            f"Greenhouse API error {r.status_code} for {api}: {r.text[:200]}"
        )

    data = r.json()
    items = data.get("jobs") or []

    remote_tokens = (
        "remote",
        "work from anywhere",
        "distributed",
        "anywhere",
    )

    jobs: list[Job] = []
    for item in items:
        job_id = item.get("id")
        title = item.get("title") or ""
        job_url = item.get("absolute_url") or ""
        location = (item.get("location") or {}).get("name") or ""
        company = board
        department = (item.get("departments") or [{}])[0].get("name") or ""
        office = (item.get("office") or [{}])[0].get("name") or ""
        updated_at = item.get("updated_at")

        loc = location.lower()
        is_remote = any(tok in loc for tok in remote_tokens)

        # Only fetch description if title looks relevant
        likely_engineering_tokens = get("ats")["greenhouse"][
            "likely_engineering_tokens"
        ]

        likely_engineering = any(
            word in title.lower() for word in likely_engineering_tokens
        )

        detail = {}
        if likely_engineering and job_id:
            detail = fetch_greenhouse_job_detail(board, job_id)

        desc = detail.get("content") or ""

        # Fall back to detail response if list endpoint didn't return these
        if not department:
            department = (detail.get("departments") or [{}])[0].get("name") or ""
        if not office:
            office = (detail.get("offices") or [{}])[0].get("name") or ""

        jobs.append(
            Job(
                source_root_url=root_url,
                job_url=job_url,
                title=title,
                company=company,
                location_text=location,
                description_text=desc,
                is_remote=is_remote,
                department=department,
                office=office,
                job_updated_at=updated_at,
            )
        )

    return jobs


def fetch_greenhouse_job_detail(board: str, job_id: int) -> dict:
    api = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{job_id}"
    r = requests.get(api, headers=HEADERS, timeout=25)
    if r.status_code != 200:
        return {}
    return r.json()
