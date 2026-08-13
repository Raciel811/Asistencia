"""
face_recognition_service.py
─────────────────────────────────────────────────────────────────────────────
Motor de reconocimiento facial. Usa la librería `face_recognition` (basada en
dlib ResNet-34, entrenada sobre ~3 millones de rostros, ~99.38% de precisión
en el benchmark LFW) para generar encodings de 128 dimensiones y compararlos
por distancia euclidiana — el mismo enfoque de similitud por embeddings que
usaba el modelo MobileFaceNet de la app Flutter, pero con un backbone más
preciso y sin depender de TensorFlow Lite.
"""

from __future__ import annotations

from typing import Optional

import face_recognition
import numpy as np

from app.config import get_settings
from app.interfaces.contracts import IFaceRecognitionService
from app.utils.face_augmentation import FaceAugmentor
from app.utils.logger import get_logger

logger = get_logger(__name__)


class FaceRecognitionService(IFaceRecognitionService):
    """Detección, extracción de encodings y comparación de rostros."""

    def __init__(self) -> None:
        self._settings = get_settings()

    def _detectar_mejor_ubicacion(self, image_rgb: np.ndarray) -> Optional[list]:
        """
        Detecta todos los rostros de la imagen y devuelve, envuelta en una
        lista (formato que espera face_recognition), la ubicación del de
        mayor área — igual que hacía la app Flutter al ordenar por bbox.
        """
        try:
            ubicaciones = face_recognition.face_locations(
                image_rgb,
                number_of_times_to_upsample=self._settings.FACE_UPSAMPLE_TIMES,
                model=self._settings.FACE_DETECTION_MODEL,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Error detectando rostros: %s", exc)
            return None

        if not ubicaciones:
            return None

        # face_locations devuelve (top, right, bottom, left); ordenamos por área
        ubicaciones.sort(
            key=lambda box: (box[2] - box[0]) * (box[1] - box[3]), reverse=True
        )
        return [ubicaciones[0]]

    def obtener_encoding(self, image_rgb: np.ndarray) -> Optional[np.ndarray]:
        """
        Detecta el rostro más grande de la imagen y devuelve su encoding de
        128-d.
        """
        mejor_ubicacion = self._detectar_mejor_ubicacion(image_rgb)
        if mejor_ubicacion is None:
            return None

        try:
            encodings = face_recognition.face_encodings(
                image_rgb,
                known_face_locations=mejor_ubicacion,
                num_jitters=self._settings.FACE_JITTER,
                model="large",
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Error generando encoding: %s", exc)
            return None

        if not encodings:
            return None
        return encodings[0]

    def generar_encodings_aumentados(self, image_rgb: np.ndarray) -> list[np.ndarray]:
        """
        A partir de UNA sola foto de referencia, genera un banco de encodings
        provenientes de variantes sintéticas de esa misma foto (volteo,
        brillo, contraste, rotación leve, gafas/pendientes simulados), para
        que el reconocimiento tolere accesorios e iluminación distinta sin
        necesidad de subir fotos adicionales. Si la aumentación está
        deshabilitada por configuración, se comporta igual que antes (un
        único encoding de la foto original).
        """
        if not self._settings.FACE_AUGMENTATION_ENABLED:
            encoding = self.obtener_encoding(image_rgb)
            return [encoding] if encoding is not None else []

        mejor_ubicacion = self._detectar_mejor_ubicacion(image_rgb)
        if mejor_ubicacion is None:
            return []

        landmarks_por_rostro = None
        try:
            landmarks_lista = face_recognition.face_landmarks(
                image_rgb, face_locations=mejor_ubicacion
            )
            if landmarks_lista:
                landmarks_por_rostro = landmarks_lista[0]
        except Exception as exc:  # noqa: BLE001
            logger.warning("No se pudieron obtener landmarks faciales: %s", exc)

        variantes = FaceAugmentor.generar_banco(
            image_rgb,
            landmarks=landmarks_por_rostro,
            cantidad=self._settings.FACE_AUGMENTATION_VARIANTS,
        )

        encodings: list[np.ndarray] = []
        for variante in variantes:
            encoding = self.obtener_encoding(variante)
            if encoding is not None:
                encodings.append(encoding)

        if not encodings:
            logger.warning(
                "Ninguna variante aumentada produjo un encoding válido; "
                "se usará solo la foto original si es detectable."
            )
            encoding_original = self.obtener_encoding(image_rgb)
            if encoding_original is not None:
                encodings.append(encoding_original)

        return encodings

    def comparar(self, encoding_a: np.ndarray, encoding_b: np.ndarray) -> float:
        """
        Devuelve un puntaje de similitud entre 0 y 1 (1 = idéntico), derivado
        de la distancia euclidiana entre encodings. Se usa 1 - distancia para
        mantener la misma semántica "mayor score = más parecido" del cosine
        similarity original en Dart.
        """
        distancia = np.linalg.norm(encoding_a - encoding_b)
        similitud = max(0.0, 1.0 - distancia)
        return float(similitud)

    def comparar_multiple(
        self, encoding_capturado: np.ndarray, encodings_referencia: list[np.ndarray]
    ) -> float:
        """
        Compara contra TODAS las fotos de referencia de una persona (ej. una
        con lentes, otra sin lentes) y devuelve la MEJOR similitud obtenida.
        Esto permite que una sola condición de apariencia coincidente sea
        suficiente para el match, sin necesidad de que todas las fotos de
        referencia sean parecidas entre sí.
        """
        if not encodings_referencia:
            return 0.0
        return max(self.comparar(encoding_capturado, enc) for enc in encodings_referencia)

    def es_coincidencia(self, distancia_o_similitud: float) -> bool:
        """Determina si una similitud supera el umbral configurado."""
        distancia = 1.0 - distancia_o_similitud
        return distancia <= self._settings.FACE_MATCH_TOLERANCE
