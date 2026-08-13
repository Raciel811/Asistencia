"""
image_utils.py
─────────────────────────────────────────────────────────────────────────────
Utilidades puras para manipulación de imágenes: decodificar base64 recibido
desde el navegador, validar tamaño/formato y normalizar orientación.
"""

from __future__ import annotations

import base64
import binascii
import re

import numpy as np
from PIL import Image, ImageOps, ImageEnhance
import io

from app.utils.exceptions import InvalidImageError

_DATA_URL_PATTERN = re.compile(r"^data:image/(png|jpe?g|webp);base64,", re.IGNORECASE)

MAX_IMAGE_BYTES = 8 * 1024 * 1024  # 8 MB
MAX_DIMENSION = 1600

# Umbral de luminancia promedio (0-255) por debajo del cual se considera que
# la imagen viene de un ambiente con poca luz (típico en webcams de noche).
DARK_IMAGE_THRESHOLD = 90
# Límite superior de brillo relativo aplicable, para no "quemar" la imagen
# ni introducir ruido excesivo al forzar demasiado una foto casi negra.
MAX_BRIGHTNESS_FACTOR = 2.2


class ImageCodec:
    """Responsable único: convertir entre base64 (data URL) y arreglos numpy RGB."""

    @staticmethod
    def data_url_to_rgb_array(data_url: str) -> np.ndarray:
        """
        Convierte una data URL (formato enviado por <canvas>.toDataURL()) en un
        arreglo numpy RGB (H, W, 3), listo para el motor de reconocimiento facial.
        """
        if not data_url:
            raise InvalidImageError("No se recibió ninguna imagen")

        match = _DATA_URL_PATTERN.match(data_url)
        raw_b64 = _DATA_URL_PATTERN.sub("", data_url) if match else data_url

        try:
            image_bytes = base64.b64decode(raw_b64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise InvalidImageError("La imagen no pudo decodificarse (base64 inválido)") from exc

        if len(image_bytes) == 0:
            raise InvalidImageError("La imagen recibida está vacía")
        if len(image_bytes) > MAX_IMAGE_BYTES:
            raise InvalidImageError("La imagen supera el tamaño máximo permitido (8 MB)")

        try:
            pil_image = Image.open(io.BytesIO(image_bytes))
            pil_image = ImageOps.exif_transpose(pil_image)  # corrige orientación EXIF
            pil_image = pil_image.convert("RGB")
        except Exception as exc:  # noqa: BLE001 - cualquier error de PIL es "imagen inválida"
            raise InvalidImageError("El formato de la imagen no es soportado") from exc

        pil_image = ImageCodec._downscale_if_needed(pil_image)
        pil_image = ImageCodec._auto_correct_exposure(pil_image)
        return np.array(pil_image)

    @staticmethod
    def _auto_correct_exposure(pil_image: Image.Image) -> Image.Image:
        """
        Si la imagen viene muy oscura (webcam con poca luz), aplica una
        corrección de brillo y contraste proporcional al déficit de luz.
        dlib necesita contraste suficiente en los rasgos faciales (ojos,
        nariz, boca) para poder detectar el rostro; sin esto, fotos tomadas
        de noche o en cuartos oscuros suelen no detectar ninguna cara.
        """
        # Luminancia promedio aproximada (ITU-R BT.601)
        grayscale = pil_image.convert("L")
        mean_brightness = np.array(grayscale).mean()

        if mean_brightness >= DARK_IMAGE_THRESHOLD or mean_brightness == 0:
            return pil_image

        # Factor de corrección: entre más oscura la imagen, más se sube el
        # brillo, pero limitado por MAX_BRIGHTNESS_FACTOR para no saturar.
        factor = min(DARK_IMAGE_THRESHOLD / mean_brightness, MAX_BRIGHTNESS_FACTOR)

        brightened = ImageEnhance.Brightness(pil_image).enhance(factor)
        # Subimos también el contraste un poco, ya que aclarar sin más deja
        # la imagen "lavada"; esto ayuda a que los bordes faciales sean
        # más nítidos para el detector.
        corrected = ImageEnhance.Contrast(brightened).enhance(1.15)
        return corrected

    @staticmethod
    def _downscale_if_needed(pil_image: Image.Image) -> Image.Image:
        """Reduce imágenes muy grandes para acelerar la detección sin perder precisión útil."""
        width, height = pil_image.size
        largest_side = max(width, height)
        if largest_side <= MAX_DIMENSION:
            return pil_image
        scale = MAX_DIMENSION / largest_side
        new_size = (int(width * scale), int(height * scale))
        return pil_image.resize(new_size, Image.LANCZOS)

    @staticmethod
    def file_bytes_to_rgb_array(file_bytes: bytes) -> np.ndarray:
        """Convierte bytes crudos de un archivo (ej. descargado de Drive) a RGB numpy array."""
        try:
            pil_image = Image.open(io.BytesIO(file_bytes))
            pil_image = ImageOps.exif_transpose(pil_image)
            pil_image = pil_image.convert("RGB")
        except Exception as exc:  # noqa: BLE001
            raise InvalidImageError("No se pudo procesar la foto de referencia") from exc
        pil_image = ImageCodec._downscale_if_needed(pil_image)
        pil_image = ImageCodec._auto_correct_exposure(pil_image)
        return np.array(pil_image)