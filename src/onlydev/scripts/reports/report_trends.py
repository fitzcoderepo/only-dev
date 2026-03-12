from __future__ import annotations

import argparse

from onlydev.core.db import connect, init_db



def section(title: str) -> None:
    print(f"\n{'━' * 60}")
    print(f"  {title}")
    print(f"{'━' * 60}")


def report_new_jobs(conn) -> None:
    section("NEW JOBS SINCE LAST RUN")

    # Get the second most recent run_utc as the cutoff
    row = conn.execute(
        """
        SELECT DISTINCT run_utc FROM job_run_counts
        ORDER BY run_utc DESC
        LIMIT 1 OFFSET 1
        """
    ).fetchone()

    if not row:
        print("  Not enough runs yet to compare.")
        return

    since = row["run_utc"]

    rows = conn.execute(
        """
        SELECT title, company, location_text, department, office, job_url
        FROM jobs
        WHERE first_seen_utc >= ? AND active=1
        ORDER BY first_seen_utc DESC
        """,
        (since,),
    ).fetchall()

    if not rows:
        print("  No new jobs.")
        return

    for r in rows:
        dept = f" [{r['department']}]" if r['department'] else ""
        loc = r['office'] or r['location_text'] or "Unknown"
        print(f"  {r['company']}{dept} — {r['title']}")
        print(f"    📍 {loc}")
        print(f"    🔗 {r['job_url']}")
        print()



def report_keyword_frequency(conn, since: str) -> None:
    section("KEYWORD FREQUENCY")
    rows = conn.execute(
        """
        SELECT matched_keywords FROM jobs
        WHERE first_seen_utc >= ? AND matched_keywords IS NOT NULL AND matched_keywords != ''
        """,
        (since,),
    ).fetchall()

    counts: dict[str, int] = {}
    for r in rows:
        for kw in r["matched_keywords"].split(","):
            kw = kw.strip()
            if kw:
                counts[kw] = counts.get(kw, 0) + 1

    if not counts:
        print("  No keyword data.")
        return

    max_count = max(counts.values())
    max_bar = 40

    for kw, count in sorted(counts.items(), key=lambda x: x[1], reverse=True):
        bar = "█" * int(count / max_count * max_bar)
        print(f"  {kw:<25} {bar} {count}")

# this runs at report time to collapse everything into 5 clean buckets
def normalize_department(raw: str) -> str:
    d = raw.lower()
    if any(t in d for t in ("engineer", "software", "backend", "fullstack", "platform", "infrastructure", "cloud", "devops", "development")):
        return "Engineering"
    if any(t in d for t in ("data", "machine learning", "ai", "analytics")):
        return "Data & AI"
    if "security" in d:
        return "Security"
    if "product" in d:
        return "Product"
    return "Other"


def report_department_breakdown(conn, since: str) -> None:
    section("DEPARTMENT BREAKDOWN")
    rows = conn.execute(
        """
        SELECT department FROM jobs
        WHERE first_seen_utc >= ? AND department IS NOT NULL AND department != ''
        """,
        (since,),
    ).fetchall()

    if not rows:
        print("  No department data.")
        return

    counts: dict[str, int] = {}
    for r in rows:
        category = normalize_department(r["department"])
        counts[category] = counts.get(category, 0) + 1

    max_count = max(counts.values())
    max_bar = 40

    for category, count in sorted(counts.items(), key=lambda x: x[1], reverse=True):
        bar = "█" * int(count / max_count * max_bar)
        print(f"  {category:<20} {bar} {count}")


def report_hiring_velocity(conn, since: str) -> None:
    section("HIRING VELOCITY (new jobs per run)")
    rows = conn.execute(
        """
        SELECT run_utc, SUM(new_count) as total_new, SUM(match_count) as total_matched
        FROM job_run_counts
        WHERE run_utc >= ?
        GROUP BY run_utc
        ORDER BY run_utc ASC
        """,
        (since,),
    ).fetchall()

    if not rows:
        print("  No run data.")
        return

    print(f"  {'RUN (UTC)':<26} {'MATCHED':>8} {'NEW':>6}")
    print(f"  {'-' * 44}")
    for r in rows:
        print(f"  {r['run_utc']:<26} {r['total_matched']:>8} {r['total_new']:>6}")



def report_remote_ratio(conn, since: str) -> None:
    section("REMOTE vs LOCAL RATIO")
    rows = conn.execute(
        """
        SELECT
            SUM(is_remote) as remote_count,
            COUNT(*) - SUM(is_remote) as local_count,
            COUNT(*) as total
        FROM jobs
        WHERE first_seen_utc >= ?
        """,
        (since,),
    ).fetchone()

    if not rows or not rows["total"]:
        print("  No data.")
        return

    remote_pct = rows["remote_count"] / rows["total"] * 100
    local_pct = rows["local_count"] / rows["total"] * 100
    print(f"  Remote: {rows['remote_count']} ({remote_pct:.1f}%)")
    print(f"  Local:  {rows['local_count']} ({local_pct:.1f}%)")


def report_job_longevity(conn) -> None:
    section("JOB LONGEVITY (time-to-disappear)")
    rows = conn.execute(
        """
        SELECT company, title, first_seen_utc, last_seen_utc,
            ROUND(
                (julianday(last_seen_utc) - julianday(first_seen_utc)),
                1
            ) as days_active
        FROM jobs
        WHERE active=0
        ORDER BY days_active ASC
        LIMIT 20
        """,
    ).fetchall()

    if not rows:
        print("  No inactive jobs yet.")
        return

    print(f"  {'COMPANY':<25} {'TITLE':<35} {'DAYS ACTIVE':>11}")
    print(f"  {'-' * 73}")
    for r in rows:
        print(f"  {r['company']:<25} {r['title']:<35} {r['days_active']:>11}")


def main() -> None:
    parser = argparse.ArgumentParser(description="onlydev report")
    parser.add_argument(
        "--days", type=int, default=7,
        help="Number of days of history to include (default: 7)"
    )
    args = parser.parse_args()

    conn = connect("jobs.db")
    init_db(conn)

    # Compute the cutoff date
    since = conn.execute(
        f"SELECT datetime('now', '-{args.days} days')"
    ).fetchone()[0]

    print(f"\n  onlydev report — last {args.days} day(s)  |  since {since} UTC")

    report_new_jobs(conn)
    report_keyword_frequency(conn, since)
    report_department_breakdown(conn, since)
    report_hiring_velocity(conn, since)
    report_remote_ratio(conn, since)
    report_job_longevity(conn)

    conn.close()


if __name__ == "__main__":
    main()