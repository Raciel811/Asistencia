"""
drive_repository.py
─────────────────────────────────────────────────────────────────────────────
Implementación concreta de IDriveRepository. Descarga las fotos de referencia
del personal desde la carpeta compartida de Google Drive.

Soporta MÚLTIPLES fotos por cédula (ej. "1234.jpg" y "1234_2.jpg"), para que
el reconocimiento facial tolere variaciones naturales de apariencia de la
misma persona (con lentes / sin lentes, distinta luz, etc.). Convención de
nombres: "<cedula>.jpg" para la foto principal, y "<cedula>_2.jpg",
"<cedula>_3.jpg", ... para adicionales.
"""

from __future__ import annotations

import io

from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

from app.config import get_settings
from app.interfaces.contracts import IDriveRepository
from app.services.google_auth_service import GoogleAuthService
from app.utils.logger import get_logger

logger = get_logger(__name__)

_EXTENSIONES_VALIDAS = (".jpg", ".jpeg", ".png")


class DriveRepository(IDriveRepository):
    """Acceso de solo lectura a la carpeta de fotos de referencia en Drive."""

    def __init__(self, auth_service: GoogleAuthService | None = None) -> None:
        self._settings = get_settings()
        self._auth = auth_service or GoogleAuthService()

    def _buscar_archivos(self, cedula: str) -> list[dict]:
        """
        Busca todos los archivos cuyo nombre empiece por la cédula
        (ej. "1234.jpg", "1234_2.jpg", "1234_lentes.jpg"). La API de Drive no
        soporta "empieza con" de forma nativa, así que filtramos con
        `contains` en el servidor y afinamos con startswith en cliente.
        """
        drive = self._auth.get_drive_client()
        query = (
            f"'{self._settings.DRIVE_FOLDER_ID}' in parents "
            f"and name contains '{cedula}' and trashed = false"
        )
        try:
            resultado = drive.files().list(q=query, fields="files(id,name)").execute()
        except HttpError as exc:
            logger.error("Error buscando fotos de %s en Drive: %s", cedula, exc)
            return []

        archivos = resultado.get("files", [])
        candidatos = [
            a
            for a in archivos
            if a["name"].lower().startswith(cedula.lower())
            and a["name"].lower().endswith(_EXTENSIONES_VALIDAS)
        ]
        # Orden estable: la foto principal "<cedula>.jpg" primero, luego el resto
        candidatos.sort(key=lambda a: (not a["name"].lower().startswith(f"{cedula.lower()}."), a["name"]))

        if not candidatos:
            logger.warning("No existe ninguna foto de referencia para la cédula %s", cedula)
        return candidatos

    def descargar_foto(self, cedula: str) -> bytes | None:
        """Descarga solo la primera foto encontrada (compatibilidad hacia atrás)."""
        fotos = self.descargar_fotos(cedula)
        return fotos[0] if fotos else None

    def descargar_fotos(self, cedula: str) -> list[bytes]:
        """Descarga TODAS las fotos de referencia disponibles para la cédula."""
        archivos = self._buscar_archivos(cedula)
        if not archivos:
            return []

        drive = self._auth.get_drive_client()
        resultados: list[bytes] = []
        for archivo in archivos:
            try:
                request = drive.files().get_media(fileId=archivo["id"])
                buffer = io.BytesIO()
                downloader = MediaIoBaseDownload(buffer, request)
                done = False
                while not done:
                    _, done = downloader.next_chunk()
                resultados.append(buffer.getvalue())
            except HttpError as exc:
                logger.error(
                    "Error descargando '%s' de %s: %s", archivo.get("name"), cedula, exc
                )
        return resultados