"""
exceptions.py
─────────────────────────────────────────────────────────────────────────────
Jerarquía de excepciones propias del dominio. Permite manejar errores de
forma específica y devolver respuestas HTTP claras desde los controladores.
"""


class AppException(Exception):
    """Excepción base de la aplicación."""

    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class GoogleAuthError(AppException):
    """Error autenticando contra la API de Google (Sheets/Drive)."""

    def __init__(self, message: str = "Error de autenticación con Google API"):
        super().__init__(message, status_code=500)


class SheetsReadError(AppException):
    """Error leyendo datos de Google Sheets."""

    def __init__(self, message: str = "Error leyendo datos de Google Sheets"):
        super().__init__(message, status_code=502)


class SheetsWriteError(AppException):
    """Error escribiendo datos en Google Sheets."""

    def __init__(self, message: str = "Error escribiendo en Google Sheets"):
        super().__init__(message, status_code=502)


class NoFaceDetectedError(AppException):
    """No se detectó ningún rostro en la imagen capturada."""

    def __init__(self, message: str = "No se detectó un rostro en la imagen"):
        super().__init__(message, status_code=422)


class FaceNotRecognizedError(AppException):
    """El rostro capturado no coincide con ningún registro del personal."""

    def __init__(self, message: str = "Rostro no reconocido", best_score: float = 0.0):
        self.best_score = best_score
        super().__init__(message, status_code=404)


class DuplicateRegistrationError(AppException):
    """Ya existe un registro de ese tipo para hoy."""

    def __init__(self, message: str = "Ya existe un registro de este tipo hoy"):
        super().__init__(message, status_code=409)


class InvalidImageError(AppException):
    """La imagen recibida no es válida o no pudo decodificarse."""

    def __init__(self, message: str = "La imagen enviada no es válida"):
        super().__init__(message, status_code=400)


class PersonnelNotFoundError(AppException):
    """No hay personal registrado en la hoja PERSONAL."""

    def __init__(self, message: str = "No hay personal registrado"):
        super().__init__(message, status_code=404)
