from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Form, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from web.paths import OUTPUTS_DIR, TOC_DIR
from web.services import ollama, runner

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


@router.get("/", response_class=HTMLResponse)
async def pipeline_form(request: Request):
    toc_files = sorted(TOC_DIR.glob("*.json")) if TOC_DIR.exists() else []
    try:
        models = ollama.list_models()
    except Exception:
        models = []

    return templates.TemplateResponse("pipeline.html", {
        "request": request,
        "toc_files": [f.name for f in toc_files],
        "models": [m["name"] for m in models],
        "ollama_ok": ollama.is_running(),
    })


@router.get("/models")
async def get_models():
    try:
        return {"models": [m["name"] for m in ollama.list_models()]}
    except Exception as e:
        return {"models": [], "error": str(e)}


@router.post("/run")
async def run_pipeline(
    toc_file: str = Form(...),
    model: str = Form(...),
    language: str = Form("ko"),
    words: str = Form("3000-5000"),
    test_mode: bool = Form(False),
):
    toc_path = str(TOC_DIR / toc_file)
    extra = ["--test-mode"] if test_mode else None
    job_id = runner.start_generation(
        toc_file=toc_path,
        model=model,
        output_dir=str(OUTPUTS_DIR),
        language=language,
        words=words,
        extra_args=extra,
    )
    return RedirectResponse(url=f"/pipeline/job/{job_id}", status_code=303)


@router.get("/job/{job_id}", response_class=HTMLResponse)
async def job_page(request: Request, job_id: str):
    job = runner.get_job(job_id)
    return templates.TemplateResponse("job.html", {
        "request": request,
        "job": job,
        "job_id": job_id,
    })


@router.websocket("/ws/{job_id}")
async def ws_log_stream(websocket: WebSocket, job_id: str):
    await websocket.accept()
    try:
        async for line in runner.tail_log(job_id):
            await websocket.send_text(line)
        await websocket.send_text("[DONE]")
    except WebSocketDisconnect:
        pass


@router.get("/jobs")
async def list_jobs():
    jobs = runner.get_all_jobs()
    return [
        {
            "id": j.id,
            "toc_file": j.toc_file,
            "model": j.model,
            "status": j.status,
            "started_at": j.started_at.isoformat(),
        }
        for j in jobs
    ]
