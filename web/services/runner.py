from __future__ import annotations

import asyncio
import subprocess
import sys
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from web.paths import OUTPUTS_DIR, PROJECT_ROOT


@dataclass
class Job:
    id: str
    process: subprocess.Popen
    log_path: Path
    toc_file: str
    model: str
    status: str = "running"
    started_at: datetime = field(default_factory=datetime.now)
    return_code: int | None = None


_jobs: dict[str, Job] = {}


def start_generation(
    toc_file: str,
    model: str,
    output_dir: str | None = None,
    language: str = "ko",
    words: str = "3000-5000",
    extra_args: list[str] | None = None,
) -> str:
    out = Path(output_dir) if output_dir else OUTPUTS_DIR
    job_id = uuid.uuid4().hex[:12]
    log_path = out / f".job-{job_id}.log"
    out.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable, "main.py",
        "--toc", toc_file,
        "--model", model,
        "--output-dir", str(out),
        "--lang", language,
        "--words", words,
    ]
    if extra_args:
        cmd.extend(extra_args)

    log_file = open(log_path, "w")
    proc = subprocess.Popen(
        cmd,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        cwd=PROJECT_ROOT,
    )

    job = Job(
        id=job_id, process=proc, log_path=log_path,
        toc_file=toc_file, model=model,
    )
    _jobs[job_id] = job

    def _monitor():
        proc.wait()
        job.status = "completed" if proc.returncode == 0 else "failed"
        job.return_code = proc.returncode
        log_file.close()

    threading.Thread(target=_monitor, daemon=True).start()
    return job_id


def get_job(job_id: str) -> Job | None:
    return _jobs.get(job_id)


def get_all_jobs() -> list[Job]:
    return list(_jobs.values())


async def tail_log(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        return
    with open(job.log_path, "r") as f:
        while True:
            line = f.readline()
            if line:
                yield line.rstrip("\n")
            elif job.status != "running":
                return
            else:
                await asyncio.sleep(0.3)
