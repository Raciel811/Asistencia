"""
sheets_repository.py
─────────────────────────────────────────────────────────────────────────────
Implementación concreta de ISheetsRepository. Encapsula toda interacción con
la API de Google Sheets: lectura de PERSONAL, verificación de duplicados y
escritura de nuevos registros en DATOS.
"""

from __future__ import annotations

from datetime import datetime

from googleapiclient.errors import HttpError

from app.config import get_settings
from app.interfaces.contracts import ISheetsRepository
from app.models.persona import Persona
from app.models.registro import RegistroAsistencia
from app.services.google_auth_service import GoogleAuthService
from app.utils.exceptions import SheetsReadError, SheetsWriteError
from app.utils.logger import get_logger

logger = get_logger(__name__)


class SheetsRepository(ISheetsRepository):
    """Acceso a datos sobre la hoja de cálculo compartida (PERSONAL / DATOS)."""

    def __init__(self, auth_service: GoogleAuthService | None = None) -> None:
        self._settings = get_settings()
        self._auth = auth_service or GoogleAuthService()

    def _values_api(self):
        return self._auth.get_sheets_client().spreadsheets().values()

    def _leer_rango(self, rango: str) -> list[list]:
        try:
            response = (
                self._values_api()
                .get(spreadsheetId=self._settings.SPREADSHEET_ID, range=rango)
                .execute()
            )
            return response.get("values", [])
        except HttpError as exc:
            status = getattr(exc.resp, "status", None)
            if status == 400:
                # Rango sin datos aún (grid vacío) - no es un error fatal
                logger.warning("Rango '%s' vacío o fuera de límites: %s", rango, exc)
                return []
            logger.error("Error leyendo rango '%s': %s", rango, exc)
            raise SheetsReadError(f"No se pudo leer la hoja ({rango})") from exc

    def leer_personal(self) -> list[Persona]:
        filas = self._leer_rango(self._settings.PERSONAL_RANGE)
        personas = [Persona.from_row(fila) for fila in filas]
        return [p for p in personas if p.is_valid]

    def existe_registro_hoy(self, cedula: str, tipo: str) -> bool:
        filas = self._leer_rango(self._settings.DATOS_RANGE)
        hoy = datetime.now()
        fecha_hoy = f"{hoy.day}/{hoy.month}/{hoy.year}"

        for fila in filas:
            if len(fila) < 3:
                continue
            fila_cedula = str(fila[0]).strip()
            fila_fecha = str(fila[1]).split(" ")[0].strip()
            fila_tipo = str(fila[2]).strip()
            if fila_cedula == cedula and fila_fecha == fecha_hoy and fila_tipo == tipo:
                return True
        return False

    def guardar_registro(self, registro: RegistroAsistencia) -> None:
        try:
            body = {"values": [registro.to_row()]}
            (
                self._values_api()
                .append(
                    spreadsheetId=self._settings.SPREADSHEET_ID,
                    range=self._settings.DATOS_RANGE,
                    valueInputOption="RAW",
                    body=body,
                )
                .execute()
            )
        except HttpError as exc:
            logger.error("Error escribiendo registro: %s", exc)
            raise SheetsWriteError("No se pudo guardar el registro en Google Sheets") from exc
