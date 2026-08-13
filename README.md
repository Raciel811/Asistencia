# Sistema de Asistencia Biométrico (versión web)

Migración de la app Flutter/Android original a una **aplicación web en
Python**, conservando exactamente la misma lógica de negocio:

- Reconocimiento facial contra las fotos del personal.
- Lectura/escritura sobre el **mismo Google Sheet** (`PERSONAL` / `DATOS`).
- Descarga de fotos de referencia desde la **misma carpeta de Google Drive**.
- Prevención de doble marcación el mismo día para el mismo tipo.
- Captura de ubicación en el momento de marcar.
- Interfaz oscura, moderna, con la misma paleta de colores y flujo de UX
  (reloj, tarjeta de logo, grid de 4 botones, cámara con cuenta regresiva de
  3 segundos, overlay de carga, modal de resultado).

## Diferencias clave frente a la app Flutter (y por qué)

| Aspecto | App Flutter (móvil) | App web (Python) |
|---|---|---|
| Reconocimiento facial | Google ML Kit + MobileFaceNet (TFLite) | `face_recognition` (dlib ResNet-34, 128-d) — mayor precisión (~99.38% LFW) |
| Cámara | `camera` (nativo Android/iOS) | `getUserMedia` del navegador (webcam del PC) |
| Ubicación | GPS del teléfono (`Geolocator`) | Geolocation API del navegador (Wi-Fi/IP), con reverse geocoding en el backend |
| Fotos de referencia | Se descargaban de Drive en cada marcación | Se descargan una vez y se **cachean** (memoria + disco) — evita minutos de espera con muchos empleados |
| Backend | Ninguno (todo en el cliente) | FastAPI, arquitectura limpia por capas |

## Arquitectura

Arquitectura en capas (Clean Architecture) + patrones Singleton, Repository
y Dependency Inversion:

```
asistencia_web/
├── app/
│   ├── main.py                     # Punto de entrada FastAPI
│   ├── config.py                   # Configuración (Singleton)
│   ├── controllers/                # Routers HTTP (capa de presentación)
│   │   ├── asistencia_controller.py
│   │   └── pages_controller.py
│   ├── interfaces/
│   │   └── contracts.py            # Contratos ABC (Dependency Inversion)
│   ├── models/
│   │   ├── persona.py              # Entidad Persona
│   │   ├── registro.py             # Entidad RegistroAsistencia + Enum
│   │   └── schemas.py              # DTOs Pydantic (request/response)
│   ├── repositories/
│   │   ├── sheets_repository.py    # Acceso a Google Sheets
│   │   └── drive_repository.py     # Acceso a Google Drive
│   ├── services/
│   │   ├── google_auth_service.py      # Autenticación (Singleton)
│   │   ├── face_recognition_service.py # Motor de reconocimiento facial
│   │   ├── reference_cache_service.py  # Caché de encodings (Singleton)
│   │   ├── geolocation_service.py      # Reverse geocoding
│   │   └── asistencia_service.py       # Caso de uso principal (orquestador)
│   └── utils/
│       ├── exceptions.py           # Jerarquía de excepciones del dominio
│       ├── image_utils.py          # Decodificación/validación de imágenes
│       └── logger.py               # Logger centralizado
├── static/
│   ├── css/style.css               # Tema oscuro (misma paleta que Flutter)
│   ├── js/app.js                   # Reloj, geolocalización, cámara, API
│   └── img/logo.svg                # Logo (reemplázalo por el tuyo)
├── templates/
│   └── index.html                  # Dashboard principal (Jinja2)
├── assets/keys/                    # credentials.json (NO incluido, ver abajo)
├── data/
│   ├── cache/                      # Caché de encodings en disco
│   └── reference_photos/           # (uso interno, opcional)
├── tests/
├── requirements.txt
├── .env.example
├── Dockerfile
├── run.py
└── README.md
```

## Instalación paso a paso

### 1. Requisitos previos

- **Python 3.12+** — [python.org/downloads](https://www.python.org/downloads/)
- Un compilador de C++ y **CMake** (los necesita `dlib`):
  - **Windows**: instala "Build Tools for Visual Studio" (componente
    *Desktop development with C++*) y luego `pip install cmake`.
  - **macOS**: `xcode-select --install` y `brew install cmake`.
  - **Linux (Debian/Ubuntu)**:
    ```bash
    sudo apt-get update
    sudo apt-get install -y build-essential cmake libopenblas-dev liblapack-dev
    ```

### 2. Clonar / copiar el proyecto y crear entorno virtual

```bash
cd asistencia_web
python -m venv venv

# Activar entorno virtual
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate
```

### 3. Instalar dependencias

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

> La instalación de `dlib` puede tardar varios minutos porque compila código
> C++. Si falla, revisa que CMake y el compilador del paso 1 estén
> correctamente instalados y en el PATH.

### 4. Configurar credenciales de Google

Sigue las instrucciones de `assets/keys/README.md` para colocar tu
`credentials.json` (la misma cuenta de servicio que ya usaba la app Flutter).

### 5. Configurar variables de entorno

```bash
cp .env.example .env
```

Los valores por defecto ya apuntan al mismo `SPREADSHEET_ID` y
`DRIVE_FOLDER_ID` que usaba la app Flutter, así que normalmente no necesitas
cambiar nada salvo `GOOGLE_CREDENTIALS_PATH` si moviste el archivo.

### 6. Ejecutar en desarrollo

```bash
python run.py
```

Abre tu navegador en **http://localhost:8000**. La primera vez que alguien
marca asistencia, el sistema descargará y calculará los encodings de todo el
personal (puede tardar según la cantidad de empleados); las siguientes
marcaciones usan la caché y son casi instantáneas.

La documentación interactiva de la API (Swagger) queda disponible en
**http://localhost:8000/docs**.

### 7. Ejecutar en producción

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
```

O con Docker:

```bash
docker build -t asistencia-web .
docker run -p 8000:8000 \
  -v $(pwd)/assets/keys:/app/assets/keys \
  -v $(pwd)/data:/app/data \
  --env-file .env \
  asistencia-web
```

### 8. Ejecutar pruebas

```bash
pytest -v
```

## Permisos del navegador

La app necesita dos permisos, que el navegador solicitará automáticamente:

1. **Cámara** — para capturar la foto biométrica.
2. **Ubicación** — para registrar dónde se hizo la marcación. En un PC de
   escritorio la precisión depende de la geolocalización por IP/Wi-Fi
   (normalmente a nivel de ciudad/barrio, no exacta como el GPS de un
   celular). Si el usuario deniega el permiso, la marcación igual se
   registra, indicando "Ubicación no disponible".

## Ajustar la precisión del reconocimiento facial

En `.env`, el parámetro `FACE_MATCH_TOLERANCE` controla qué tan estricta es
la coincidencia (distancia euclidiana máxima entre encodings de 128-d):

- `0.6` → tolerancia estándar de la librería (más permisivo).
- `0.45` → valor por defecto de este proyecto (más estricto, menos falsos positivos).
- `0.35` o menos → muy estricto, útil en entornos con iluminación controlada.

Si el sistema no reconoce a alguien correctamente, sube ligeramente el
valor; si reconoce a la persona equivocada, bájalo.

## Refrescar la caché de personal

Si agregas empleados nuevos o cambias una foto en Drive, puedes forzar la
reconstrucción de la caché sin reiniciar el servidor:

```bash
curl -X POST http://localhost:8000/api/asistencia/refrescar-cache
```

## Endpoints principales

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/` | Dashboard principal |
| POST | `/api/asistencia/registrar` | Registra una marcación (foto + tipo + ubicación) |
| GET | `/api/asistencia/ubicacion` | Reverse geocoding de coordenadas |
| GET | `/api/asistencia/estado` | Estado de la caché de personal |
| POST | `/api/asistencia/refrescar-cache` | Fuerza recarga de encodings |
| GET | `/health` | Health check |
