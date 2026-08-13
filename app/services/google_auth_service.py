"""
google_auth_service.py
─────────────────────────────────────────────────────────────────────────────
Maneja la autenticación con la cuenta de servicio de Google. Implementa un
Singleton perezoso (lazy) para reutilizar las credenciales sin releer el
archivo credentials.json en cada llamada.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import Resource, build

from app.config import get_settings
from app.utils.exceptions import GoogleAuthError
from app.utils.logger import get_logger

logger = get_logger(__name__)


class GoogleAuthService:
    """
    Punto único de autenticación contra la API de Google.
    Expone clientes ya construidos para Sheets y Drive.
    """

    _instance: "GoogleAuthService | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "GoogleAuthService":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._settings = get_settings()
        self._credentials: service_account.Credentials | None = None
        self._sheets_client: Resource | None = None
        self._drive_client: Resource | None = None
        self._initialized = True

    def _load_credentials(self) -> service_account.Credentials:
        if self._credentials is not None:
            return self._credentials

        cred_path = Path(self._settings.GOOGLE_CREDENTIALS_PATH)
        if not cred_path.exists():
            raise GoogleAuthError(
                f"No se encontró el archivo de credenciales en '{cred_path}'. "
                "Coloca tu credentials.json de la cuenta de servicio en assets/keys/."
            )

        try:
            info = json.loads(cred_path.read_text(encoding="utf-8"))
            self._credentials = service_account.Credentials.from_service_account_info(
                info, scopes=self._settings.GOOGLE_SCOPES
            )
        except (json.JSONDecodeError, ValueError, KeyError) as exc:
            raise GoogleAuthError(f"credentials.json inválido: {exc}") from exc

        return self._credentials

    def get_sheets_client(self) -> Resource:
        if self._sheets_client is None:
            creds = self._load_credentials()
            try:
                self._sheets_client = build("sheets", "v4", credentials=creds, cache_discovery=False)
            except Exception as exc:  # noqa: BLE001
                raise GoogleAuthError(f"No se pudo construir el cliente de Sheets: {exc}") from exc
        return self._sheets_client

    def get_drive_client(self) -> Resource:
        if self._drive_client is None:
            creds = self._load_credentials()
            try:
                self._drive_client = build("drive", "v3", credentials=creds, cache_discovery=False)
            except Exception as exc:  # noqa: BLE001
                raise GoogleAuthError(f"No se pudo construir el cliente de Drive: {exc}") from exc
        return self._drive_client
