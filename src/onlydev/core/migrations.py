
MIGRATIONS = [
    # v0 — base schema
    """
    CREATE TABLE IF NOT EXISTS sources (
      id              INTEGER PRIMARY KEY AUTOINCREMENT,
      source_type     TEXT NOT NULL,
      root_url        TEXT NOT NULL UNIQUE,
      discovered_from TEXT,
      active          INTEGER NOT NULL DEFAULT 1,
      first_seen_utc  TEXT NOT NULL,
      last_seen_utc   TEXT NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_sources_active
      ON sources(active);

    CREATE TABLE IF NOT EXISTS jobs (
      id                INTEGER PRIMARY KEY AUTOINCREMENT,
      source_id         INTEGER NOT NULL,
      job_url           TEXT NOT NULL UNIQUE,
      title             TEXT,
      company           TEXT,
      location_text     TEXT,
      description_text  TEXT,
      is_remote         INTEGER NOT NULL DEFAULT 0,
      matched_keywords  TEXT,
      first_seen_utc    TEXT NOT NULL,
      last_seen_utc     TEXT NOT NULL,
      FOREIGN KEY(source_id) REFERENCES sources(id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_jobs_source_id
      ON jobs(source_id);

    CREATE INDEX IF NOT EXISTS idx_jobs_last_seen
      ON jobs(last_seen_utc);

    CREATE INDEX IF NOT EXISTS idx_jobs_is_remote
      ON jobs(is_remote);

    CREATE TABLE IF NOT EXISTS job_run_counts (
      id            INTEGER PRIMARY KEY AUTOINCREMENT,
      run_utc       TEXT NOT NULL,
      source_type   TEXT NOT NULL,
      company_key   TEXT NOT NULL,
      match_count   INTEGER NOT NULL,
      new_count     INTEGER NOT NULL DEFAULT 0
    );

    CREATE INDEX IF NOT EXISTS idx_job_run_counts_run
      ON job_run_counts(run_utc);

    CREATE INDEX IF NOT EXISTS idx_job_run_counts_company
      ON job_run_counts(company_key);
    """,

    # v1 — add department, office, job_updated_at to jobs
    """
    ALTER TABLE jobs ADD COLUMN department TEXT;
    ALTER TABLE jobs ADD COLUMN office TEXT;
    ALTER TABLE jobs ADD COLUMN job_updated_at TEXT;
    """,

    # v2 — add active column to jobs
    """
    ALTER TABLE jobs ADD COLUMN active INTEGER NOT NULL DEFAULT 1;
    CREATE INDEX IF NOT EXISTS idx_jobs_active ON jobs(active);
    """,

    # v3 — add applied column to jobs
    """
    ALTER TABLE jobs ADD COLUMN applied INTEGER NOT NULL DEFAULT 0;
    """,
]