from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from web.paths import OUTPUTS_DIR, TOC_DIR
from web.routes import outputs, pipeline, reader, toc
from web.services.books import scan_output_books

BASE_DIR = Path(__file__).parent


def create_app() -> FastAPI:
    app = FastAPI(title="Book Agent Manager")

    app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

    app.include_router(toc.router, prefix="/toc", tags=["TOC"])
    app.include_router(pipeline.router, prefix="/pipeline", tags=["Pipeline"])
    app.include_router(outputs.router, prefix="/outputs", tags=["Outputs"])
    app.include_router(reader.router, prefix="/reader", tags=["Reader"])

    tmpl = Jinja2Templates(directory=BASE_DIR / "templates")

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        toc_count = len(list(TOC_DIR.glob("*.json"))) if TOC_DIR.exists() else 0

        books = scan_output_books(OUTPUTS_DIR)

        from web.services.runner import get_all_jobs
        active_jobs = [j for j in get_all_jobs() if j.status == "running"]

        return tmpl.TemplateResponse("index.html", {
            "request": request,
            "toc_count": toc_count,
            "books": books,
            "active_jobs": active_jobs,
        })

    return app


app = create_app()


def run_server():
    import uvicorn
    uvicorn.run("web.app:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    run_server()
