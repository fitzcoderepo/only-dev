from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from html import unescape
from openai import OpenAI
import os

from onlydev.core.db import connect, init_db
from onlydev.api.description import description
from onlydev.core.config import load_config, save_config

load_dotenv()


static_dir = os.path.join(os.path.dirname(__file__), "static")

app = FastAPI(title="OnlyDevAPP", summary="Dev jobs only", description=description)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/config")
def get_config():
    return load_config()


@app.patch("/config")
def update_config(body: dict):
    try:
        current = load_config()
        # Deep merge body into current config
        for section, values in body.items():
            if section in current and isinstance(current[section], dict):
                current[section].update(values)
            else:
                current[section] = values
        save_config(current)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
def root():
    return FileResponse(os.path.join(static_dir, "index.html"))


@app.get("/jobs")
def get_jobs():
    conn = connect("jobs.db")
    rows = conn.execute("SELECT * FROM jobs WHERE active=1").fetchall()
    jobs = []
    for row in rows:
        job = dict(row)
        job["description_text"] = clean_job_description(job["description_text"])
        jobs.append(job)

    return jobs


@app.get("/runs/latest")
def get_latest_run():
    conn = connect("jobs.db")
    row = conn.execute(
        "SELECT DISTINCT run_utc FROM job_run_counts ORDER BY run_utc DESC LIMIT 1 OFFSET 1"
    ).fetchone()

    return {"previous_run_utc": row["run_utc"] if row else None}


@app.patch("/jobs/{job_id}/applied")
def set_applied(job_id: int, body: dict):
    conn = connect("jobs.db")
    conn.execute(
        "UPDATE jobs SET applied=? WHERE id=?", (1 if body["applied"] else 0, job_id)
    )
    conn.commit()

    return {"ok": True}


import subprocess
from fastapi.responses import StreamingResponse
from onlydev.core.tailor import get_section_diffs, build_tailored_docx

# openai
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@app.post("/jobs/{job_id}/tailor/diff")
def tailor_diff(job_id: int):
    conn = connect("jobs.db")
    row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    job = dict(row)
    job["description_text"] = clean_job_description(job["description_text"])
    diffs = get_section_diffs(job)
    return {"diffs": diffs}


@app.post("/jobs/{job_id}/tailor/apply")
def tailor_apply(job_id: int, body: dict):
    conn = connect("jobs.db")
    row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    job = dict(row)
    approved = body.get("approved", {})  # {section: text}
    out_path = build_tailored_docx(approved, job)
    return {"ok": True, "path": str(out_path)}

@app.post("/run/{command}")
def run_command(command: str):
    commands = {
        "discover": "od-discover",
        "monitor": "od-monitor",
        "report": "od-report",
        "run": "od-run",
    }
    if command not in commands:
        raise HTTPException(status_code=400, detail="Unknown command")

    def stream():
        process = subprocess.Popen(
            commands[command],
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        for line in process.stdout:
            yield line
        process.wait()

    return StreamingResponse(stream(), media_type="text/plain")


# ---------------------------------------------------------
def clean_job_description(raw: str) -> str:
    if not raw:
        return ""
    unescaped = unescape(raw)
    soup = BeautifulSoup(unescaped, "html.parser")

    # Add newlines after block elements before extracting text
    for tag in soup.find_all(["p", "li", "div", "h1", "h2", "h3", "h4", "br"]):
        tag.append("\n")

    text = soup.get_text(separator="")

    # Collapse 3+ newlines down to 2
    import re

    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
