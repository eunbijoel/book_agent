from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Form, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from web.paths import OUTPUTS_DIR, TOC_DIR
from web.services import ollama, runner

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


PROVIDER_MODELS = {
    "ollama": [],
    "gemini": ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"],
    "claude": ["claude-haiku-4-5", "claude-sonnet-4-6"],
    "openai": ["gpt-4.1-mini", "gpt-4.1", "gpt-4o", "gpt-4o-mini"],
}


@router.get("/", response_class=HTMLResponse)
async def pipeline_form(request: Request):
    toc_files = sorted(TOC_DIR.glob("*.json")) if TOC_DIR.exists() else []
    try:
        ollama_models = [m["name"] for m in ollama.list_models()]
    except Exception:
        ollama_models = []

    return templates.TemplateResponse("pipeline.html", {
        "request": request,
        "toc_files": [f.name for f in toc_files],
        "ollama_models": ollama_models,
        "provider_models": {**PROVIDER_MODELS, "ollama": ollama_models},
        "ollama_ok": ollama.is_running(),
    })


@router.get("/models")
async def get_models():
    try:
        return {"models": [m["name"] for m in ollama.list_models()]}
    except Exception as e:
        return {"models": [], "error": str(e)}


@router.get("/provider-models/{provider}")
async def get_provider_models(provider: str):
    if provider == "ollama":
        try:
            return {"models": [m["name"] for m in ollama.list_models()]}
        except Exception:
            return {"models": []}
    return {"models": PROVIDER_MODELS.get(provider, [])}


@router.post("/run")
async def run_pipeline(
    request: Request,
    input_mode: str = Form("toc"),
    toc_file: str = Form(""),
    topic: str = Form(""),
    topic_description: str = Form(""),
    topic_chapters: int = Form(5),
    provider: str = Form("ollama"),
    model: str = Form(...),
    language: str = Form("ko"),
    words: str = Form("3000-5000"),
    test_mode: bool = Form(False),
    input_url: str = Form(""),
):
    extra = ["--test-mode"] if test_mode else None

    if input_mode == "url" and input_url.strip():
        job_id = runner.start_generation(
            topic=topic.strip() or input_url.strip()[:60],
            description=topic_description.strip(),
            chapters=topic_chapters,
            model=model,
            provider=provider,
            output_dir=str(OUTPUTS_DIR),
            language=language,
            words=words,
            input_url=input_url.strip(),
            extra_args=extra,
        )
    elif input_mode == "topic" and topic.strip():
        job_id = runner.start_generation(
            topic=topic.strip(),
            description=topic_description.strip(),
            chapters=topic_chapters,
            model=model,
            provider=provider,
            output_dir=str(OUTPUTS_DIR),
            language=language,
            words=words,
            extra_args=extra,
        )
    else:
        toc_path = str(TOC_DIR / toc_file)
        job_id = runner.start_generation(
            toc_file=toc_path,
            model=model,
            provider=provider,
            output_dir=str(OUTPUTS_DIR),
            language=language,
            words=words,
            extra_args=extra,
        )

    accept = request.headers.get("accept", "")
    if "application/json" in accept:
        return JSONResponse({"job_id": job_id})
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
            "topic": j.topic,
            "source": j.source_label,
            "model": j.model,
            "status": j.status,
            "started_at": j.started_at.isoformat(),
        }
        for j in jobs
    ]
