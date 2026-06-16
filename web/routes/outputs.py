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


@router.delete("/{slug:path}")
async def delete_output(slug: str):
    path = (OUTPUTS_DIR / slug).resolve()
    if not str(path).startswith(str(OUTPUTS_DIR.resolve())):
        return {"ok": False, "error": "invalid path"}
    if path.exists() and path.is_dir():
        shutil.rmtree(path)
        parent = path.parent
        if parent != OUTPUTS_DIR.resolve() and parent.is_dir() and not any(parent.iterdir()):
            parent.rmdir()
        return {"ok": True}
    return {"ok": False, "error": "not found"}
