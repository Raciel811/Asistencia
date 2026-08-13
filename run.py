"""
run.py
─────────────────────────────────────────────────────────────────────────────
Punto de entrada para ejecutar la aplicación en desarrollo con HTTPS.
"""

import uvicorn

from app.config import get_settings

if __name__ == "__main__":
    settings = get_settings()

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        ssl_keyfile="certs/local-key.pem",
        ssl_certfile="certs/local-cert.pem",
    )