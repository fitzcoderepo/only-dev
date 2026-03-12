from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
import subprocess
import requests
import time
import os
import re

from onlydev.core.config import get
from onlydev.scripts.sources.seed_sources import seed_greenhouse_sources
from onlydev.scripts.discovery.validate_greenhouse import validate_greenhouse_tokens


SEARCH_URL = "https://api.github.com/search/code"
TOKEN_RE = re.compile(r"https?://(?:boards|job-boards)\.greenhouse\.io/([^/\s]+)")


def github_search_all_pages(query: str, *, max_pages: int = 10) -> list[dict]:
    token = os.getenv("GITHUB_TOKEN", "")
    if not token:
        raise RuntimeError("Missing GITHUB_TOKEN in environment/.env")

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }

    all_items = []
    for page in range(1, max_pages + 1):
        params = {"q": query, "per_page": 100, "page": page}
        r = requests.get(SEARCH_URL, headers=headers, params=params, timeout=25)
        if r.status_code == 422:
            break
        r.raise_for_status()
        items = r.json().get("items", [])
        if not items:
            break
        all_items.extend(items)
        time.sleep(1)
    return all_items


def to_raw_url(html_url: str) -> str:
    return html_url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")


def extract_tokens_from_text(text: str) -> set[str]:
    return set(TOKEN_RE.findall(text or ""))


def fetch_tokens_from_item(item: dict) -> set[str]:
    raw_url = to_raw_url(item["html_url"])
    try:
        r = requests.get(raw_url, timeout=20)
        if r.status_code == 200:
            return extract_tokens_from_text(r.text)
    except requests.RequestException:
        pass
    return set()


def main() -> None:
    load_dotenv() # get github access token from .env
    subprocess.run('cls' if os.name == 'nt' else 'clear', shell=True)

    items = github_search_all_pages("boards.greenhouse.io", max_pages=1)
    print("Files returned:", len(items))

    tokens: set[str] = set()

    cfg = get('discovery')
    items = github_search_all_pages('boards.greenhouse.io', max_pages=cfg['max_pages'])

    with ThreadPoolExecutor(max_workers=cfg['max_workers']) as executor:
        futures = [executor.submit(fetch_tokens_from_item, item) for item in items]
        for future in as_completed(futures):
            tokens |= future.result()

    print("\nTOKENS FOUND:", len(tokens))
    print("\nVALIDATING...")

    valid_tokens = validate_greenhouse_tokens(tokens)

    seed_greenhouse_sources(valid_tokens)

    print("\n\nDone")


if __name__ == "__main__":
    main()