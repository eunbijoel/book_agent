from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from web.paths import OUTPUTS_DIR
from web.services.books import scan_output_books

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


@router.get("/", response_class=HTMLResponse)
async def list_outputs(request: Request):
    return templates.TemplateResponse("outputs.html", {
        "request": request,
        "books": scan_output_books(OUTPUTS_DIR),
    })


@router.delete("/{slug}")
async def delete_output(slug: str):
    path = OUTPUTS_DIR / slug
    if path.exists() and path.is_dir():
        shutil.rmtree(path)
        return {"ok": True}
    return {"ok": False, "error": "not found"}
