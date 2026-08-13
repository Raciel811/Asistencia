"""
contracts.py
─────────────────────────────────────────────────────────────────────────────
Contratos (interfaces) que desacoplan los controladores de las
implementaciones concretas, siguiendo el Principio de Inversión de
Dependencias (SOLID) e Interface Segregation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

import numpy as np

from app.models.persona import Persona
from app.models.registro import RegistroAsistencia


class ISheetsRepository(ABC):
    """Contrato para lectura/escritura de datos en Google Sheets."""

    @abstractmethod
    def leer_personal(self) -> list[Persona]:
        ...

    @abstractmethod
    def existe_registro_hoy(self, cedula: str, tipo: str) -> bool:
        ...

    @abstractmethod
    def guardar_registro(self, registro: RegistroAsistencia) -> None:
        ...


class IDriveRepository(ABC):
    """Contrato para descarga de fotos de referencia desde Google Drive."""

    @abstractmethod
    def descargar_foto(self, cedula: str) -> Optional[bytes]:
        ...

    @abstractmethod
    def descargar_fotos(self, cedula: str) -> list[bytes]:
        ...


class IFaceRecognitionService(ABC):
    """Contrato del motor de reconocimiento facial."""

    @abstractmethod
    def obtener_encoding(self, image_rgb: np.ndarray) -> Optional[np.ndarray]:
        ...

    @abstractmethod
    def comparar(self, encoding_a: np.ndarray, encoding_b: np.ndarray) -> float:
        ...

    @abstractmethod
    def comparar_multiple(self, encoding_capturado: np.ndarray, encodings_referencia: list[np.ndarray]) -> float:
        ...

    @abstractmethod
    def generar_encodings_aumentados(self, image_rgb: np.ndarray) -> list[np.ndarray]:
        ...
