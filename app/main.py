"""
main.py
─────────────────────────────────────────────────────────────────────────────
Punto de entrada de la aplicación FastAPI. Registra routers, sirve archivos
estáticos, configura CORS y centraliza el manejo de excepciones del dominio.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.controllers import asistencia_controller, pages_controller
from app.utils.exceptions import AppException
from app.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Sistema de control de asistencia con reconocimiento facial, "
    "integrado con Google Sheets y Google Drive.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(pages_controller.router)
app.include_router(asistencia_controller.router)


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Traduce cualquier excepción del dominio en una respuesta JSON consistente."""
    logger.warning("AppException en %s: %s", request.url.path, exc.message)
    extra = {}
    if hasattr(exc, "best_score"):
        extra["similitud"] = round(getattr(exc, "best_score"), 4)  # noqa: B009
    return JSONResponse(
        status_code=exc.status_code,
        content={"exito": False, "mensaje": exc.message, **extra},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Error no controlado en %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"exito": False, "mensaje": "Error interno del servidor", "detalle": str(exc)},
    )


@app.get("/health", tags=["Sistema"])
def health_check() -> dict:
    return {"status": "ok", "version": settings.APP_VERSION}
