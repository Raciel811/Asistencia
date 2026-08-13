"""
reference_cache_service.py
─────────────────────────────────────────────────────────────────────────────
Cachea en disco (pickle) los encodings faciales del personal, evitando
descargar cada foto de Drive y recalcular su encoding en cada marcación de
asistencia. Aplica el patrón Repository + una capa de caché con TTL.

Este servicio es lo que hace viable usar el sistema con decenas o cientos de
empleados sin que cada marcación tarde minutos: la primera vez que arranca la
app (o cuando expira el TTL / se fuerza refresco) descarga y calcula todos
los encodings; de ahí en adelante los sirve desde memoria y disco.
"""

from __future__ import annotations

import pickle
import threading
import time
from dataclasses import dataclass

import numpy as np

from app.config import get_settings
from app.models.persona import Persona
from app.repositories.drive_repository import DriveRepository
from app.repositories.sheets_repository import SheetsRepository
from app.services.face_recognition_service import FaceRecognitionService
from app.utils.image_utils import ImageCodec
from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class _CacheEntry:
    personas: list[Persona]
    timestamp: float


class ReferenceCacheService:
    """
    Mantiene en memoria (y respaldado en disco) la lista de personal con sus
    encodings faciales ya calculados, refrescándolos cuando expira el TTL.
    """

    _instance: "ReferenceCacheService | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "ReferenceCacheService":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(
        self,
        sheets_repo: SheetsRepository | None = None,
        drive_repo: DriveRepository | None = None,
        face_service: FaceRecognitionService | None = None,
    ) -> None:
        if self._initialized:
            return
        self._settings = get_settings()
        self._sheets_repo = sheets_repo or SheetsRepository()
        self._drive_repo = drive_repo or DriveRepository()
        self._face_service = face_service or FaceRecognitionService()
        self._cache: _CacheEntry | None = None
        self._build_lock = threading.Lock()
        self._initialized = True

    def _is_stale(self) -> bool:
        if self._cache is None:
            return True
        return (time.time() - self._cache.timestamp) > self._settings.CACHE_TTL_SECONDS

    def obtener_personal_con_encodings(self, forzar_refresco: bool = False) -> list[Persona]:
        """Devuelve la lista de Persona con `.encodings` poblado, usando caché cuando es válida."""
        if not forzar_refresco and not self._is_stale():
            return self._cache.personas  # type: ignore[union-attr]

        with self._build_lock:
            if not forzar_refresco and not self._is_stale():
                return self._cache.personas  # type: ignore[union-attr]
            return self._reconstruir_cache()

    def _reconstruir_cache(self) -> list[Persona]:
        logger.info("Reconstruyendo caché de encodings de referencia...")
        personas = self._sheets_repo.leer_personal()

        disco = self._cargar_disco()

        for persona in personas:
            if disco and persona.cedula in disco:
                persona.encodings = disco[persona.cedula]
                continue

            fotos_bytes = self._drive_repo.descargar_fotos(persona.cedula)
            if not fotos_bytes:
                logger.warning("Sin fotos de referencia en Drive para %s", persona.cedula)
                continue

            encodings_persona: list[np.ndarray] = []
            for foto_bytes in fotos_bytes:
                try:
                    imagen_rgb = ImageCodec.file_bytes_to_rgb_array(foto_bytes)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Foto inválida para %s: %s", persona.cedula, exc)
                    continue

                # Genera un banco de encodings a partir de esta única foto
                # (original + variantes sintéticas: volteo, brillo, contraste,
                # rotación leve, gafas/pendientes simulados). Esto amplía la
                # tolerancia del reconocimiento sin requerir fotos adicionales.
                encodings_de_esta_foto = self._face_service.generar_encodings_aumentados(
                    imagen_rgb
                )
                if not encodings_de_esta_foto:
                    logger.warning(
                        "No se detectó rostro en una de las fotos de referencia de %s",
                        persona.cedula,
                    )
                    continue
                encodings_persona.extend(encodings_de_esta_foto)

            persona.encodings = encodings_persona
            if encodings_persona:
                logger.info(
                    "%s: %d encoding(s) de referencia (fotos + variantes aumentadas)",
                    persona.cedula,
                    len(encodings_persona),
                )

        self._guardar_disco(personas)
        self._cache = _CacheEntry(personas=personas, timestamp=time.time())
        logger.info(
            "Caché reconstruida: %d personas, %d con al menos un encoding válido",
            len(personas),
            sum(1 for p in personas if p.tiene_encoding),
        )
        return personas

    def _cargar_disco(self) -> dict[str, list[np.ndarray]] | None:
        ruta = self._settings.ENCODINGS_CACHE_FILE
        if not ruta.exists():
            return None
        try:
            with open(ruta, "rb") as f:
                datos = pickle.load(f)
        except (pickle.PickleError, EOFError, OSError) as exc:
            logger.warning("No se pudo leer la caché en disco: %s", exc)
            return None

        # Compatibilidad hacia atrás: si la caché en disco viene del formato
        # viejo (un único np.ndarray por cédula), la envolvemos en una lista.
        normalizado: dict[str, list[np.ndarray]] = {}
        for cedula, valor in datos.items():
            if isinstance(valor, list):
                normalizado[cedula] = valor
            else:
                normalizado[cedula] = [valor]
        return normalizado

    def _guardar_disco(self, personas: list[Persona]) -> None:
        mapa = {p.cedula: p.encodings for p in personas if p.tiene_encoding}
        try:
            with open(self._settings.ENCODINGS_CACHE_FILE, "wb") as f:
                pickle.dump(mapa, f)
        except OSError as exc:
            logger.warning("No se pudo persistir la caché en disco: %s", exc)

    def invalidar(self) -> None:
        """Fuerza que la próxima consulta reconstruya la caché desde Sheets/Drive."""
        self._cache = None
