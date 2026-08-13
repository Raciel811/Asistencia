"""
asistencia_controller.py
─────────────────────────────────────────────────────────────────────────────
Controlador (router de FastAPI) para el dominio de asistencia. Traduce
peticiones HTTP en llamadas al AsistenciaService, sin contener lógica de
negocio propia (Single Responsibility).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.models.schemas import (
    EstadoSistemaResponse,
    RegistroAsistenciaRequest,
    RegistroAsistenciaResponse,
    UbicacionResponse,
)
from app.services.asistencia_service import AsistenciaService
from app.services.geolocation_service import GeolocationService
from app.services.reference_cache_service import ReferenceCacheService
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/asistencia", tags=["Asistencia"])


def get_asistencia_service() -> AsistenciaService:
    return AsistenciaService()


def get_geolocation_service() -> GeolocationService:
    return GeolocationService()


def get_cache_service() -> ReferenceCacheService:
    return ReferenceCacheService()


@router.post("/registrar", response_model=RegistroAsistenciaResponse)
def registrar_asistencia(
    payload: RegistroAsistenciaRequest,
    service: AsistenciaService = Depends(get_asistencia_service),
    geo_service: GeolocationService = Depends(get_geolocation_service),
) -> RegistroAsistenciaResponse:
    """Recibe la foto capturada + tipo de marcación y registra la asistencia."""

    ubicacion_str = "Ubicación no disponible"
    if payload.latitud is not None and payload.longitud is not None:
        ubicacion = geo_service.resolver_direccion(payload.latitud, payload.longitud)
        ubicacion_str = f"{ubicacion.coordenadas_str} | {ubicacion.direccion}"

    resultado = service.registrar(
        imagen_data_url=payload.imagen, tipo=payload.tipo, ubicacion_str=ubicacion_str
    )

    return RegistroAsistenciaResponse(
        mensaje=f"{resultado.tipo.value} registrado correctamente",
        nombre=resultado.persona.nombre or resultado.persona.cedula,
        cedula=resultado.persona.cedula,
        tipo=resultado.tipo.value,
        hora=resultado.timestamp.strftime("%H:%M:%S"),
        fecha=resultado.timestamp.strftime("%d/%m/%Y"),
        similitud=round(resultado.similitud, 4),
        ubicacion=resultado.ubicacion,
    )


@router.get("/ubicacion", response_model=UbicacionResponse)
def resolver_ubicacion(
    lat: float, lng: float, geo_service: GeolocationService = Depends(get_geolocation_service)
) -> UbicacionResponse:
    """Convierte coordenadas del navegador en una dirección legible."""
    ubicacion = geo_service.resolver_direccion(lat, lng)
    return UbicacionResponse(
        latitud=ubicacion.latitud, longitud=ubicacion.longitud, direccion=ubicacion.direccion
    )


@router.get("/estado", response_model=EstadoSistemaResponse)
def estado_sistema(
    cache_service: ReferenceCacheService = Depends(get_cache_service),
) -> EstadoSistemaResponse:
    """Devuelve el estado de la caché de personal, útil para diagnóstico."""
    personal = cache_service.obtener_personal_con_encodings()
    return EstadoSistemaResponse(
        personal_cargado=len(personal),
        personal_con_encoding=sum(1 for p in personal if p.tiene_encoding),
        cache_valida=cache_service._cache is not None,  # noqa: SLF001 - endpoint de diagnóstico
    )


@router.post("/refrescar-cache", response_model=EstadoSistemaResponse)
def refrescar_cache(
    cache_service: ReferenceCacheService = Depends(get_cache_service),
) -> EstadoSistemaResponse:
    """Fuerza la reconstrucción de la caché de encodings (ej. tras subir personal nuevo)."""
    personal = cache_service.obtener_personal_con_encodings(forzar_refresco=True)
    return EstadoSistemaResponse(
        personal_cargado=len(personal),
        personal_con_encoding=sum(1 for p in personal if p.tiene_encoding),
        cache_valida=True,
    )