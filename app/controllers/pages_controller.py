"""
pages_controller.py
─────────────────────────────────────────────────────────────────────────────
Router encargado exclusivamente de servir las páginas HTML (SSR con Jinja2).
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

from app.config import get_settings
from app.models.registro import TipoRegistro

router = APIRouter(tags=["Páginas"])
templates = Jinja2Templates(directory="templates")


@router.get("/")
def home(request: Request):
    settings = get_settings()
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "app_name": settings.APP_NAME,
            "tipos_registro": TipoRegistro.values(),
        },
    )
