from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
import subprocess
import threading
import sys
import os

from onlydev.core.repository import list_active_sources, mark_missing_jobs_inactive, upsert_job, set_source_active, insert_run_count, utc_now_iso
from onlydev.ats.greenhouse import fetch_greenhouse_jobs, GreenhouseNotFound
from onlydev.ats.lever import fetch_lever_jobs, LeverNotFound
from onlydev.core.filters import FilterConfig, should_consider_job
from onlydev.core.db import connect, init_db
from onlydev.core.config import get

"""
threading.Lock on DB writes since SQLite isn't thread-safe for concurrent writes. The lock ensures only one thread writes at a time. 
The network fetching and filtering still happen in parallel.. only the short DB upsert is serialized.
"""
db_lock = threading.Lock()

def fetch_source(row, cfg, conn):
    source_id = int(row["id"])
    source_type = row["source_type"]
    root_url = row["root_url"]
    slug = root_url.rstrip("/").split("/")[-1]
    company_key = f"{source_type}:{slug}"

    jobs = []
    disabled = False

    if source_type == "lever":
        try:
            jobs = fetch_lever_jobs(root_url)
        except LeverNotFound:
            with db_lock:
                set_source_active(conn, source_id, False)
            return company_key, [], True

    elif source_type == "greenhouse":
        try:
            jobs = fetch_greenhouse_jobs(root_url)
        except GreenhouseNotFound:
            with db_lock:
                set_source_active(conn, source_id, False)
            return company_key, [], True

    matched = []
    for j in jobs:
        allowed, hits = should_consider_job(j.title, j.location_text, j.description_text, cfg)
        if not allowed:
            continue
        j.matched_keywords = hits
        matched.append(j)

    # get all job urls seen for the source
    all_urls = [j.job_url for j in jobs]

    return company_key, matched, all_urls, False


"""
Concurrency with ThreadPoolExecutor so all sources are fetched in parallel rather than one at a time.
"""

def main():
    subprocess.run('cls' if os.name == 'nt' else 'clear', shell=True)

    cfg_filters = get('filters')
    cfg_monitor = get('monitor')

    conn = connect("jobs.db")
    init_db(conn)

    run_utc = utc_now_iso()
    matched_counts: dict[str, int] = defaultdict(int)
    new_counts: dict[str, int] = defaultdict(int)

    cfg = FilterConfig(
        keywords=tuple(cfg_filters["keywords"]),
        home_zip=cfg_filters["home_zip"],
        zip_radius_miles=cfg_filters["zip_radius_miles"],
        local_city_tokens=tuple(cfg_filters["local_city_tokens"]),
        local_state_tokens=tuple(cfg_filters["local_state_tokens"]),
        remote_tokens=tuple(cfg_filters["remote_tokens"]),
        exclude_if_not_local_tokens=tuple(cfg_filters["exclude_if_not_local_tokens"]),
    )

    sources = list(list_active_sources(conn))
    total = len(sources)

    total_matched = 0
    total_new = 0
    disabled = 0

    with ThreadPoolExecutor(max_workers=cfg_monitor['max_workers']) as executor:
        futures = {executor.submit(fetch_source, row, cfg, conn): row for row in sources}

        for i, future in enumerate(as_completed(futures), start=1):
            company_key, matched_jobs, all_urls, was_disabled = future.result()

            if was_disabled:
                disabled += 1
            else:
                with db_lock:
                    for j in matched_jobs:
                        job_id, is_new = upsert_job(conn, int(futures[future]["id"]), j)
                        matched_counts[company_key] += 1
                        total_matched += 1
                        if is_new:
                            new_counts[company_key] += 1
                            total_new += 1

                mark_missing_jobs_inactive(conn, int(futures[future]["id"]), all_urls)
                

            sys.stdout.write(f"\rScanning sources ({i}/{total})… matched={total_matched} new={total_new} disabled={disabled}")
            sys.stdout.flush()

    sys.stdout.write(f"\rScanning sources ({total}/{total}) ✓ matched={total_matched} new={total_new} disabled={disabled}\n")
    sys.stdout.flush()

    for company_key, matched in matched_counts.items():
        new_jobs = new_counts.get(company_key, 0)
        insert_run_count(
            conn,
            run_utc,
            company_key,
            matched,
            new_jobs,
        )
    conn.close()

if __name__ == "__main__":
    main()