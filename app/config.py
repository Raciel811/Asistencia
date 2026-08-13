"""
config.py
─────────────────────────────────────────────────────────────────────────────
Configuración central de la aplicación. Aplica el patrón Singleton para
garantizar una única fuente de verdad para las variables de entorno y rutas
del proyecto.
"""

import os
from pathlib import Path
from functools import lru_cache
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings:
    """
    Configuración de la aplicación (Singleton vía lru_cache en get_settings()).
    Centraliza credenciales, IDs de Google Sheets/Drive y parámetros del
    motor de reconocimiento facial.
    """

    # ── App ──────────────────────────────────────────────────────────────
    APP_NAME: str = "Sistema de Asistencia Biométrico"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    # ── Google API ───────────────────────────────────────────────────────
    GOOGLE_CREDENTIALS_PATH: str = os.getenv(
        "GOOGLE_CREDENTIALS_PATH", str(BASE_DIR / "assets" / "keys" / "credentials.json")
    )
    GOOGLE_SCOPES: list[str] = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.readonly",
    ]

    SPREADSHEET_ID: str = os.getenv(
        "SPREADSHEET_ID", "1xRbkZtuUQooJYiztslEkfpm1MKw2FzCpXkD0WMY5jIA"
    )
    DATOS_RANGE: str = os.getenv("DATOS_RANGE", "DATOS!A2:H")
    PERSONAL_RANGE: str = os.getenv("PERSONAL_RANGE", "PERSONAL!A2:E")
    DRIVE_FOLDER_ID: str = os.getenv(
        "DRIVE_FOLDER_ID", "1ZzvJhQlnRwsbyTKCru0KatqpKN1gLJBd"
    )

    # ── Reconocimiento facial ───────────────────────────────────────────
    # Distancia euclidiana máxima entre encodings (128-d, dlib ResNet) para
    # considerar una coincidencia positiva. Cuanto más bajo, más estricto.
    FACE_MATCH_TOLERANCE: float = float(os.getenv("FACE_MATCH_TOLERANCE", "0.45"))
    FACE_DETECTION_MODEL: str = os.getenv("FACE_DETECTION_MODEL", "hog")  # "hog" o "cnn"
    # Con 2 upsamples, dlib "acerca" la imagen una vez más antes de buscar
    # rostros; ayuda a detectar caras pequeñas o con poco contraste (ej. luz
    # baja), a costa de un poco más de tiempo de procesamiento con "hog".
    FACE_UPSAMPLE_TIMES: int = int(os.getenv("FACE_UPSAMPLE_TIMES", "2"))
    FACE_JITTER: int = int(os.getenv("FACE_JITTER", "3"))  # re-muestreos para el encoding

    # ── Aumentación de fotos de referencia ───────────────────────────────
    # Genera variantes sintéticas (volteo, brillo, contraste, rotación leve,
    # gafas/pendientes simulados) de CADA foto de referencia descargada de
    # Drive, para tolerar accesorios/iluminación distinta sin subir fotos
    # nuevas. Se puede desactivar con FACE_AUGMENTATION_ENABLED=false.
    FACE_AUGMENTATION_ENABLED: bool = (
        os.getenv("FACE_AUGMENTATION_ENABLED", "true").lower() == "true"
    )
    # Cuántas variantes generar por foto (incluida la original), máx. 8.
    # Más variantes = banco más robusto pero caché más lenta de reconstruir.
    FACE_AUGMENTATION_VARIANTS: int = int(os.getenv("FACE_AUGMENTATION_VARIANTS", "8"))

    # ── Caché local de referencias faciales ─────────────────────────────
    CACHE_DIR: Path = BASE_DIR / "data" / "cache"
    ENCODINGS_CACHE_FILE: Path = CACHE_DIR / "encodings_cache.pkl"
    REFERENCE_PHOTOS_DIR: Path = BASE_DIR / "data" / "reference_photos"
    CACHE_TTL_SECONDS: int = int(os.getenv("CACHE_TTL_SECONDS", "3600"))

    # ── Geolocalización ──────────────────────────────────────────────────
    GEOCODER_USER_AGENT: str = "sistema-asistencia-biometrico"

    # ── Logs ─────────────────────────────────────────────────────────────
    LOG_DIR: Path = BASE_DIR / "logs"
    LOG_FILE: Path = LOG_DIR / "app.log"

    def ensure_directories(self) -> None:
        for directory in (self.CACHE_DIR, self.REFERENCE_PHOTOS_DIR, self.LOG_DIR):
            directory.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
