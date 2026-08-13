"""
test_face_recognition.py
─────────────────────────────────────────────────────────────────────────────
Pruebas unitarias del motor de reconocimiento facial y utilidades de imagen.
Ejecutar con: pytest -v
"""

import base64
import io

import numpy as np
import pytest
from PIL import Image

from app.services.face_recognition_service import FaceRecognitionService
from app.utils.exceptions import InvalidImageError
from app.utils.image_utils import ImageCodec


def _imagen_solida_a_data_url(color=(120, 120, 120), size=(200, 200)) -> str:
    """Genera una data URL de una imagen sólida (sin rostro) para pruebas."""
    img = Image.new("RGB", size, color)
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG")
    b64 = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/jpeg;base64,{b64}"


class TestImageCodec:
    def test_decodifica_data_url_valida(self):
        data_url = _imagen_solida_a_data_url()
        arr = ImageCodec.data_url_to_rgb_array(data_url)
        assert isinstance(arr, np.ndarray)
        assert arr.shape[2] == 3

    def test_rechaza_data_url_vacia(self):
        with pytest.raises(InvalidImageError):
            ImageCodec.data_url_to_rgb_array("")

    def test_rechaza_base64_invalido(self):
        with pytest.raises(InvalidImageError):
            ImageCodec.data_url_to_rgb_array("data:image/jpeg;base64,***no-valido***")


class TestFaceRecognitionService:
    def setup_method(self):
        self.service = FaceRecognitionService()

    def test_imagen_sin_rostro_devuelve_none(self):
        data_url = _imagen_solida_a_data_url()
        arr = ImageCodec.data_url_to_rgb_array(data_url)
        encoding = self.service.obtener_encoding(arr)
        assert encoding is None

    def test_comparar_encodings_identicos_da_similitud_maxima(self):
        vector = np.random.rand(128)
        similitud = self.service.comparar(vector, vector)
        assert similitud == pytest.approx(1.0, abs=1e-6)

    def test_es_coincidencia_respeta_umbral(self):
        assert self.service.es_coincidencia(0.99) is True
        assert self.service.es_coincidencia(0.10) is False
