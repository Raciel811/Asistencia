"""
geolocation_service.py
─────────────────────────────────────────────────────────────────────────────
En la app Flutter la ubicación se obtenía con el GPS del teléfono
(Geolocator + geocoding). En un PC no hay GPS: el navegador expone la
Geolocation API de HTML5 (navigator.geolocation), que en laptops/desktops se
resuelve por Wi-Fi/IP con precisión de barrio/ciudad. El frontend captura
lat/lng en el navegador y los envía aquí; este servicio se limita a hacer el
reverse-geocoding (coordenadas -> dirección legible) usando Nominatim
(OpenStreetMap), sin necesidad de API key.
"""

from __future__ import annotations

from dataclasses import dataclass

from geopy.geocoders import Nominatim
from geopy.exc import GeocoderServiceError, GeocoderTimedOut

from app.config import get_settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Ubicacion:
    latitud: float
    longitud: float
    direccion: str

    @property
    def coordenadas_str(self) -> str:
        return f"{self.latitud},{self.longitud}"


class GeolocationService:
    """Traduce coordenadas del navegador a una dirección legible."""

    def __init__(self) -> None:
        settings = get_settings()
        self._geocoder = Nominatim(user_agent=settings.GEOCODER_USER_AGENT, timeout=5)

    def resolver_direccion(self, latitud: float, longitud: float) -> Ubicacion:
        direccion = "Dirección no disponible"
        try:
            resultado = self._geocoder.reverse((latitud, longitud), language="es", exactly_one=True)
            if resultado is not None:
                direccion = resultado.address
        except (GeocoderTimedOut, GeocoderServiceError) as exc:
            logger.warning("No se pudo resolver la dirección (%s, %s): %s", latitud, longitud, exc)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Error inesperado en reverse geocoding: %s", exc)

        return Ubicacion(latitud=latitud, longitud=longitud, direccion=direccion)
