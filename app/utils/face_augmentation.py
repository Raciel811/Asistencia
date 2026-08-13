"""
face_augmentation.py
─────────────────────────────────────────────────────────────────────────────
Generador de variantes sintéticas de UNA foto de referencia, para que el
banco de encodings de una persona sea más tolerante a condiciones que no
aparecen en la foto original (lentes, pendientes, iluminación distinta,
ligera rotación de cabeza) sin necesidad de subir fotos adicionales.

IMPORTANTE — alcance honesto de esta técnica:
Esto NO "inventa" cómo se vería la persona con lentes reales; son
transformaciones fotométricas/geométricas y oclusiones parciales simuladas
sobre la MISMA foto. Lo que logran es:
  1) Hacer el banco de referencia robusto a variaciones de luz/ángulo, que
     en la práctica es la causa más común de falsos negativos.
  2) Reducir la sensibilidad del comparador a oclusiones parciales típicas
     de gafas normales (no oscuras) y pendientes, ya que el modelo dlib
     ResNet-34 ya es razonablemente robusto a lentes claros de por sí; el
     banco ampliado ayuda en los casos límite.
Para lentes OSCUROS que tapan los ojos por completo, ninguna técnica sin una
foto real con ese accesorio puede garantizar el reconocimiento — en ese caso
lo correcto sigue siendo pedir que se retire el accesorio al marcar.

Aplica el patrón Strategy internamente: cada transformación es un método
independiente y `generar_banco()` las orquesta.
"""

from __future__ import annotations

import io
from typing import Optional

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter


class FaceAugmentor:
    """Transformaciones puras de imagen (sin dependencia del motor de ML)."""

    # ── Transformaciones fotométricas / geométricas ─────────────────────────

    @staticmethod
    def flip_horizontal(imagen_rgb: np.ndarray) -> np.ndarray:
        pil_img = Image.fromarray(imagen_rgb)
        return np.array(pil_img.transpose(Image.FLIP_LEFT_RIGHT))

    @staticmethod
    def ajustar_brillo(imagen_rgb: np.ndarray, factor: float) -> np.ndarray:
        pil_img = Image.fromarray(imagen_rgb)
        return np.array(ImageEnhance.Brightness(pil_img).enhance(factor))

    @staticmethod
    def ajustar_contraste(imagen_rgb: np.ndarray, factor: float) -> np.ndarray:
        pil_img = Image.fromarray(imagen_rgb)
        return np.array(ImageEnhance.Contrast(pil_img).enhance(factor))

    @staticmethod
    def rotar(imagen_rgb: np.ndarray, grados: float) -> np.ndarray:
        pil_img = Image.fromarray(imagen_rgb)
        rotada = pil_img.rotate(
            grados, resample=Image.BICUBIC, expand=False, fillcolor=(128, 128, 128)
        )
        return np.array(rotada)

    @staticmethod
    def desenfocar(imagen_rgb: np.ndarray, radio: float) -> np.ndarray:
        pil_img = Image.fromarray(imagen_rgb)
        return np.array(pil_img.filter(ImageFilter.GaussianBlur(radius=radio)))

    # ── Oclusiones simuladas (gafas / pendientes) ───────────────────────────

    @staticmethod
    def simular_gafas(
        imagen_rgb: np.ndarray, landmarks: Optional[dict] = None
    ) -> np.ndarray:
        """
        Dibuja una banda semitransparente sobre la zona de los ojos, imitando
        el efecto visual de una montura de gafas clara (no oscura), para que
        el banco de referencia incluya una variante con esa oclusión parcial.
        """
        pil_img = Image.fromarray(imagen_rgb).convert("RGBA")
        overlay = Image.new("RGBA", pil_img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        caja = FaceAugmentor._zona_ojos(pil_img.size, landmarks)
        left, top, right, bottom = caja

        # Banda translúcida (simula el cristal/montura) + dos líneas más
        # oscuras arriba y abajo (simulan el borde de la montura).
        draw.rectangle([left, top, right, bottom], fill=(20, 20, 20, 70))
        draw.line([(left, top), (right, top)], fill=(10, 10, 10, 160), width=3)
        draw.line([(left, bottom), (right, bottom)], fill=(10, 10, 10, 160), width=3)

        compuesta = Image.alpha_composite(pil_img, overlay).convert("RGB")
        return np.array(compuesta)

    @staticmethod
    def simular_pendientes(
        imagen_rgb: np.ndarray, landmarks: Optional[dict] = None
    ) -> np.ndarray:
        """
        Dibuja pequeñas sombras/óvalos junto a la zona de las orejas,
        imitando el efecto visual de pendientes, sin depender de una foto
        real con ese accesorio.
        """
        pil_img = Image.fromarray(imagen_rgb).convert("RGBA")
        overlay = Image.new("RGBA", pil_img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        for cx, cy in FaceAugmentor._puntos_orejas(pil_img.size, landmarks):
            radio = max(3, pil_img.size[0] // 60)
            draw.ellipse(
                [cx - radio, cy - radio, cx + radio, cy + radio],
                fill=(15, 15, 15, 150),
            )

        compuesta = Image.alpha_composite(pil_img, overlay).convert("RGB")
        return np.array(compuesta)

    # ── Estimación de zonas cuando no hay landmarks disponibles ─────────────

    @staticmethod
    def _zona_ojos(tamano: tuple[int, int], landmarks: Optional[dict]) -> tuple[int, int, int, int]:
        ancho, alto = tamano
        if landmarks and landmarks.get("left_eye") and landmarks.get("right_eye"):
            puntos = landmarks["left_eye"] + landmarks["right_eye"]
            xs = [p[0] for p in puntos]
            ys = [p[1] for p in puntos]
            padding_x = int((max(xs) - min(xs)) * 0.35)
            padding_y = int((max(ys) - min(ys)) * 1.2)
            return (
                max(0, min(xs) - padding_x),
                max(0, min(ys) - padding_y),
                min(ancho, max(xs) + padding_x),
                min(alto, max(ys) + padding_y),
            )
        # Heurística genérica: banda horizontal a ~35%-50% de la altura.
        return (
            int(ancho * 0.15),
            int(alto * 0.35),
            int(ancho * 0.85),
            int(alto * 0.50),
        )

    @staticmethod
    def _puntos_orejas(tamano: tuple[int, int], landmarks: Optional[dict]) -> list[tuple[int, int]]:
        ancho, alto = tamano
        if landmarks and landmarks.get("chin") and len(landmarks["chin"]) >= 17:
            mandibula = landmarks["chin"]
            izquierda = mandibula[0]
            derecha = mandibula[16]
            return [
                (max(0, izquierda[0] - 4), izquierda[1]),
                (min(ancho - 1, derecha[0] + 4), derecha[1]),
            ]
        # Heurística genérica: bordes laterales a media altura del rostro.
        return [
            (int(ancho * 0.12), int(alto * 0.55)),
            (int(ancho * 0.88), int(alto * 0.55)),
        ]

    # ── Orquestador ──────────────────────────────────────────────────────────

    @classmethod
    def generar_banco(
        cls,
        imagen_rgb: np.ndarray,
        landmarks: Optional[dict] = None,
        cantidad: int = 8,
    ) -> list[np.ndarray]:
        """
        Devuelve una lista de variantes de la imagen original (la primera
        siempre es la imagen sin modificar). `cantidad` limita cuántas
        variantes totales se generan (incluida la original), para controlar
        el costo de cómputo al reconstruir la caché de referencias.
        """
        pipeline = [
            lambda img: img,  # original, sin cambios
            cls.flip_horizontal,
            lambda img: cls.ajustar_brillo(img, 1.25),
            lambda img: cls.ajustar_brillo(img, 0.78),
            lambda img: cls.ajustar_contraste(cls.rotar(img, 6), 1.15),
            lambda img: cls.desenfocar(cls.simular_gafas(img, landmarks), 0.6),
            lambda img: cls.ajustar_brillo(cls.simular_pendientes(img, landmarks), 0.9),
            lambda img: cls.ajustar_contraste(cls.rotar(img, -6), 0.9),
        ]

        cantidad = max(1, min(cantidad, len(pipeline)))
        variantes: list[np.ndarray] = []
        for transformar in pipeline[:cantidad]:
            try:
                variantes.append(transformar(imagen_rgb))
            except Exception:  # noqa: BLE001 - una variante fallida no debe tumbar el resto
                continue
        return variantes
