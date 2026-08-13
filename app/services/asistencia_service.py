"""
asistencia_service.py
─────────────────────────────────────────────────────────────────────────────
Orquesta el flujo completo de una marcación de asistencia:
  1. Decodifica la foto capturada por la cámara del navegador.
  2. Extrae su encoding facial.
  3. Lo compara contra el personal (usando la caché de referencias).
  4. Verifica que no exista ya un registro de ese tipo hoy.
  5. Guarda el registro en Google Sheets con fecha, hora y ubicación.

Es el equivalente en Python al método `_procesoAsistencia` de la app Flutter.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import numpy as np

from app.config import get_settings
from app.models.persona import Persona
from app.models.registro import RegistroAsistencia, TipoRegistro
from app.repositories.sheets_repository import SheetsRepository
from app.services.face_recognition_service import FaceRecognitionService
from app.services.reference_cache_service import ReferenceCacheService
from app.utils.exceptions import (
    DuplicateRegistrationError,
    FaceNotRecognizedError,
    NoFaceDetectedError,
    PersonnelNotFoundError,
)
from app.utils.image_utils import ImageCodec
from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ResultadoAsistencia:
    persona: Persona
    tipo: TipoRegistro
    similitud: float
    timestamp: datetime
    ubicacion: str


class AsistenciaService:
    """Caso de uso principal: registrar una marcación biométrica."""

    def __init__(
        self,
        sheets_repo: SheetsRepository | None = None,
        face_service: FaceRecognitionService | None = None,
        cache_service: ReferenceCacheService | None = None,
    ) -> None:
        self._settings = get_settings()
        self._sheets_repo = sheets_repo or SheetsRepository()
        self._face_service = face_service or FaceRecognitionService()
        self._cache_service = cache_service or ReferenceCacheService()

    def registrar(
        self, imagen_data_url: str, tipo: TipoRegistro, ubicacion_str: str
    ) -> ResultadoAsistencia:
        imagen_rgb = ImageCodec.data_url_to_rgb_array(imagen_data_url)

        encoding_capturado = self._face_service.obtener_encoding(imagen_rgb)
        if encoding_capturado is None:
            raise NoFaceDetectedError(
                "No se detectó un rostro. Verifica la iluminación y centra tu "
                "cara frente a la cámara."
            )

        personal = self._cache_service.obtener_personal_con_encodings()
        if not personal:
            raise PersonnelNotFoundError("No hay personal registrado en la hoja PERSONAL")

        persona_encontrada, mejor_similitud = self._buscar_mejor_coincidencia(
            encoding_capturado, personal
        )

        if persona_encontrada is None:
            raise FaceNotRecognizedError(
                "No se pudo identificar tu rostro con el personal registrado",
                best_score=mejor_similitud,
            )

        if self._sheets_repo.existe_registro_hoy(persona_encontrada.cedula, tipo.value):
            raise DuplicateRegistrationError(
                f"Ya existe un registro de '{tipo.value}' hoy para {persona_encontrada.nombre or persona_encontrada.cedula}"
            )

        ahora = datetime.now()
        registro = RegistroAsistencia(
            cedula=persona_encontrada.cedula,
            tipo=tipo,
            nombre=persona_encontrada.nombre,
            cargo=persona_encontrada.cargo,
            area=persona_encontrada.area,
            sede=persona_encontrada.sede,
            ubicacion=ubicacion_str,
            timestamp=ahora,
        )
        self._sheets_repo.guardar_registro(registro)

        logger.info(
            "Registro guardado: %s | %s | similitud=%.4f",
            persona_encontrada.cedula,
            tipo.value,
            mejor_similitud,
        )

        return ResultadoAsistencia(
            persona=persona_encontrada,
            tipo=tipo,
            similitud=mejor_similitud,
            timestamp=ahora,
            ubicacion=ubicacion_str,
        )

    def _buscar_mejor_coincidencia(
        self, encoding_capturado: np.ndarray, personal: list[Persona]
    ) -> tuple[Persona | None, float]:
        """
        Recorre todo el personal con encoding disponible y devuelve la persona
        con mayor similitud, siempre que supere el umbral de coincidencia.
        `mejor_similitud` se reporta incluso sin match (útil para depurar).
        """
        mejor_persona: Persona | None = None
        mejor_similitud = 0.0
        ranking: list[tuple[str, str, float]] = []

        for persona in personal:
            if not persona.tiene_encoding:
                continue
            similitud = self._face_service.comparar_multiple(encoding_capturado, persona.encodings)
            ranking.append((persona.cedula, persona.nombre or "", similitud))
            if similitud > mejor_similitud:
                mejor_similitud = similitud
                mejor_persona = persona if self._face_service.es_coincidencia(similitud) else mejor_persona

        if mejor_persona is None and ranking:
            # Diagnóstico: sin esto solo se ve la MEJOR similitud en el mensaje
            # de error, y no hay forma de saber si fue un caso límite (ej. 48%
            # contra un umbral de 50%) o un rechazo claro (ej. 20%). Ordenamos
            # de mayor a menor para ver rápido qué tan cerca estuvo cada uno.
            ranking.sort(key=lambda r: r[2], reverse=True)
            top = ranking[:5]
            resumen = ", ".join(f"{nombre or cedula}: {sim:.1%}" for cedula, nombre, sim in top)
            logger.info(
                "Sin coincidencia (umbral=%.0f%%). Ranking de similitud: %s",
                (1 - self._settings.FACE_MATCH_TOLERANCE) * 100,
                resumen,
            )

        return mejor_persona, mejor_similitud
