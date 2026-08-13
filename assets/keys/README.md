# Credenciales de Google — `credentials.json`

Este proyecto usa la **misma cuenta de servicio y el mismo Google Sheet /
carpeta de Drive** que ya usaba la app Flutter original. Por seguridad, el
archivo `credentials.json` **no se incluye** en este proyecto.

## Cómo obtenerlo

1. Ve a [Google Cloud Console](https://console.cloud.google.com/) → el
   proyecto donde creaste la cuenta de servicio original (la que usa la app
   Flutter para `assets/keys/credentials.json`).
2. Ve a **IAM y administración → Cuentas de servicio**.
3. Si ya tienes la cuenta de servicio de la app Flutter, entra a ella →
   pestaña **Claves** → **Agregar clave → Crear clave nueva → JSON**.
   Esto descarga un `.json`.
4. Renombra el archivo a `credentials.json` y colócalo en esta misma
   carpeta: `assets/keys/credentials.json`.
5. Verifica que esa cuenta de servicio (el `client_email` dentro del JSON)
   tenga permiso de **Editor** sobre el Google Sheet, y permiso de **Lector**
   sobre la carpeta de Drive con las fotos del personal — igual que ya
   estaba configurado para la app Flutter, ya que se reutiliza el mismo
   spreadsheet y la misma carpeta.

## Verificación rápida

```bash
python -c "import json; json.load(open('assets/keys/credentials.json')); print('JSON válido ✔')"
```

**Nunca subas este archivo a un repositorio público.** Ya está incluido en
`.gitignore`.
