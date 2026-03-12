from __future__ import annotations

from urllib.parse import urlparse
from typing import Iterable
import requests

from onlydev.core.models import Job



HEADERS = {"User-Agent": "OnlyDev/0.1"}

class LeverNotFound(Exception):
    pass

def _tenant_from_root(root_url: str) -> str:
    path = urlparse(root_url).path.strip("/")
    return path.split("/")[0]

def fetch_lever_jobs(root_url: str) -> list[Job]:
    tenant = _tenant_from_root(root_url)
    api = f"https://api.lever.co/v0/postings/{tenant}?mode=json"

    try:
        r = requests.get(api, headers=HEADERS, timeout=25)
    except requests.RequestException as e:
        # transient network error; treat as no jobs for now
        return []

    if r.status_code == 404:
        raise LeverNotFound(f"Lever tenant not found: {tenant}")

    if r.status_code != 200:
        # other errors: skip this run
        return []

    data = r.json()
    jobs: list[Job] = []

    for item in data:
        title = item.get("text") or ""
        job_url = item.get("hostedUrl") or item.get("applyUrl") or ""
        categories = item.get("categories") or {}
        location = categories.get("location") or ""
        desc = item.get("descriptionPlain") or ""
        company = tenant

        jobs.append(
            Job(
                source_root_url=root_url,
                job_url=job_url,
                title=title,
                company=company,
                location_text=location,
                description_text=desc,
                is_remote=("remote" in (location or "").lower()),
            )
        )

    return jobs