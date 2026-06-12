from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from web.paths import TOC_DIR

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


def _load_tocs() -> list[dict]:
    TOC_DIR.mkdir(exist_ok=True)
    tocs = []
    for p in sorted(TOC_DIR.glob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            tocs.append({
                "filename": p.name,
                "title": data.get("title", p.stem),
                "chapters": len(data.get("chapters", [])),
                "language": data.get("language", ""),
            })
        except json.JSONDecodeError:
            continue
    return tocs


@router.get("/", response_class=HTMLResponse)
async def list_tocs(request: Request):
    return templates.TemplateResponse("toc_list.html", {
        "request": request,
        "tocs": _load_tocs(),
    })


@router.get("/create", response_class=HTMLResponse)
async def create_form(request: Request):
    return templates.TemplateResponse("toc_form.html", {
        "request": request,
        "toc": None,
        "filename": None,
    })


@router.post("/create")
async def create_toc(request: Request):
    form = await request.form()
    toc_data = _form_to_toc(form)

    from slugify import slugify
    filename = slugify(toc_data["title"], max_length=60) + ".json"
    TOC_DIR.mkdir(exist_ok=True)
    (TOC_DIR / filename).write_text(
        json.dumps(toc_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return RedirectResponse(url="/toc/", status_code=303)


@router.get("/{filename}", response_class=HTMLResponse)
async def edit_form(request: Request, filename: str):
    path = TOC_DIR / filename
    if not path.exists():
        return RedirectResponse(url="/toc/", status_code=303)
    toc = json.loads(path.read_text(encoding="utf-8"))
    return templates.TemplateResponse("toc_form.html", {
        "request": request,
        "toc": toc,
        "filename": filename,
    })


@router.post("/{filename}")
async def update_toc(request: Request, filename: str):
    form = await request.form()
    toc_data = _form_to_toc(form)
    (TOC_DIR / filename).write_text(
        json.dumps(toc_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return RedirectResponse(url="/toc/", status_code=303)


@router.delete("/{filename}")
async def delete_toc(filename: str):
    path = TOC_DIR / filename
    if path.exists():
        path.unlink()
    return {"ok": True}


@router.get("/{filename}/raw")
async def raw_toc(filename: str):
    path = TOC_DIR / filename
    if not path.exists():
        return {"error": "not found"}
    return json.loads(path.read_text(encoding="utf-8"))


def _form_to_toc(form) -> dict:
    guidelines_raw = form.get("writing_guidelines", "")
    guidelines = [g.strip() for g in guidelines_raw.split("\n") if g.strip()]

    chapters = []
    i = 0
    while True:
        title = form.get(f"chapter_title_{i}")
        if title is None:
            break
        chapters.append({
            "number": i + 1,
            "title": title,
            "description": form.get(f"chapter_desc_{i}", ""),
        })
        i += 1

    return {
        "title": form.get("title", ""),
        "description": form.get("description", ""),
        "language": form.get("language", "Korean"),
        "words_per_chapter": form.get("words_per_chapter", "3000-5000"),
        "writing_guidelines": guidelines,
        "chapters": chapters,
    }
