from __future__ import annotations


from onlydev.core.repository import upsert_source
from onlydev.core.db import connect, init_db
from onlydev.core.models import Source


""" 
Creates source records from tokens and prevents duplicates
"""
def seed_greenhouse_sources(tokens: list[str], db_path: str = "jobs.db") -> None:
    conn = connect(db_path)
    init_db(conn)

    for token in tokens:
        root = f"https://boards.greenhouse.io/{token}"
        upsert_source(conn, Source("greenhouse", root, discovered_from="github"))

    conn.close()
    print(f"Seeded {len(tokens)} Greenhouse sources.")


