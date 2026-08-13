"""
schemas.py
─────────────────────────────────────────────────────────────────────────────
Esquemas Pydantic: validan y documentan automáticamente (Swagger/OpenAPI) los
payloads de entrada y salida de la API REST.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.models.registro import TipoRegistro


class RegistroAsistenciaRequest(BaseModel):
    """Payload enviado por el navegador al marcar asistencia."""

    imagen: str = Field(..., min_length=100, description="Foto capturada, como data URL base64")
    tipo: TipoRegistro = Field(..., description="Tipo de marcación")
    latitud: float | None = Field(None, ge=-90, le=90)
    longitud: float | None = Field(None, ge=-180, le=180)

    @field_validator("imagen")
    @classmethod
    def imagen_no_vacia(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("La imagen no puede estar vacía")
        return value


class RegistroAsistenciaResponse(BaseModel):
    """Respuesta de una marcación exitosa."""

    exito: bool = True
    mensaje: str
    nombre: str
    cedula: str
    tipo: str
    hora: str
    fecha: str
    similitud: float
    ubicacion: str


class ErrorResponse(BaseModel):
    exito: bool = False
    mensaje: str
    detalle: str | None = None


class UbicacionResponse(BaseModel):
    latitud: float
    longitud: float
    direccion: str


class EstadoSistemaResponse(BaseModel):
    personal_cargado: int
    personal_con_encoding: int
    cache_valida: bool
