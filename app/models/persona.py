"""
persona.py
─────────────────────────────────────────────────────────────────────────────
Modelo de dominio para un miembro del personal, tal como se lee de la hoja
"PERSONAL" del Google Sheet (columnas: cedula, nombre, cargo, area, sede).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np


@dataclass(slots=True)
class Persona:
    """Representa un empleado registrado en la hoja PERSONAL."""

    cedula: str
    nombre: str = ""
    cargo: str = ""
    area: str = ""
    sede: str = ""
    # Lista de encodings de 128-d, uno por cada foto de referencia disponible
    # (ej. con lentes, sin lentes, distintos ángulos). Se compara contra
    # todas y se toma la mejor coincidencia, para tolerar variaciones
    # naturales de apariencia de la misma persona.
    encodings: list[np.ndarray] = field(default_factory=list)

    @classmethod
    def from_row(cls, row: list) -> "Persona":
        """Construye una Persona a partir de una fila cruda de Google Sheets."""

        def _get(index: int) -> str:
            return str(row[index]).strip() if len(row) > index and row[index] is not None else ""

        return cls(
            cedula=_get(0),
            nombre=_get(1),
            cargo=_get(2),
            area=_get(3),
            sede=_get(4),
        )

    @property
    def is_valid(self) -> bool:
        return bool(self.cedula)

    @property
    def tiene_encoding(self) -> bool:
        return len(self.encodings) > 0