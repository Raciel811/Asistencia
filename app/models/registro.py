"""
registro.py
─────────────────────────────────────────────────────────────────────────────
Modelo de dominio para un registro de asistencia (una fila de la hoja DATOS).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class TipoRegistro(str, Enum):
    """Tipos de marcación soportados, replicando los cuatro botones de la app."""

    INGRESO = "INGRESO"
    SALIDA = "SALIDA"
    INICIO_ALMUERZO = "INICIO ALMUERZO"
    FIN_ALMUERZO = "FIN ALMUERZO"

    @classmethod
    def values(cls) -> list[str]:
        return [item.value for item in cls]


@dataclass(slots=True)
class RegistroAsistencia:
    """Una marcación de asistencia lista para persistirse en Google Sheets."""

    cedula: str
    tipo: TipoRegistro
    nombre: str
    cargo: str
    area: str
    sede: str
    ubicacion: str
    timestamp: datetime

    @property
    def fecha_str(self) -> str:
        return f"{self.timestamp.day}/{self.timestamp.month}/{self.timestamp.year}"

    @property
    def hora_str(self) -> str:
        return self.timestamp.strftime("%H:%M")

    def to_row(self) -> list[str]:
        """Serializa el registro al mismo orden de columnas usado en la app Flutter."""
        return [
            self.cedula,
            f"{self.fecha_str} {self.hora_str}",
            self.tipo.value,
            self.nombre,
            self.cargo,
            self.area,
            self.sede,
            self.ubicacion,
        ]
