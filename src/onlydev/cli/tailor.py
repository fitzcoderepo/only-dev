from __future__ import annotations

import argparse
import os

from dotenv import load_dotenv

from onlydev.core.db import connect
from onlydev.core.tailor import get_section_diffs, build_tailored_docx
from onlydev.api.description import description as clean_description


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="Tailor resume to a job")
    parser.add_argument("job_id", type=int, help="Job ID from the database")
    args = parser.parse_args()

    conn = connect("jobs.db")
    row = conn.execute("SELECT * FROM jobs WHERE id=?", (args.job_id,)).fetchone()
    if not row:
        print(f"Job {args.job_id} not found.")
        return

    job = dict(row)
    job["description_text"] = clean_description(job["description_text"])

    print(f"\nTailoring resume for: {job['title']} @ {job['company']}\n")
    print("Fetching suggestions from OpenAI...")

    diffs = get_section_diffs(job)

    approved: dict[str, str] = {}

    for section, diff in diffs.items():
        original = diff.get("original", "").strip()
        suggested = diff.get("suggested", "").strip()

        if original == suggested:
            print(f"\n── {section.upper()} ── (no changes suggested, keeping original)")
            approved[section] = original
            continue

        print(f"\n{'─' * 60}")
        print(f"  SECTION: {section.upper()}")
        print(f"{'─' * 60}")
        print(f"\n  ORIGINAL:\n")
        for line in original.splitlines():
            print(f"    {line}")
        print(f"\n  SUGGESTED:\n")
        for line in suggested.splitlines():
            print(f"    {line}")
        print()

        while True:
            choice = input(f"  Accept suggested changes for [{section}]? (y/n): ").strip().lower()
            if choice in ("y", "n"):
                break

        approved[section] = suggested if choice == "y" else original

    print("\nBuilding tailored resume...")
    out_path = build_tailored_docx(approved, job)
    print(f"✓ Saved to: {out_path}\n")