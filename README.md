# bot_refes

Bot desarrollado con `python-telegram-bot==20.7` para:
- Registrar referencias de imágenes.
- Contabilizarlas por mes.
- Enviar formato personalizado a un canal.
- Mostrar el top del mes con `/toprefe`.

## 🚀 Deploy en Railway

### Archivos necesarios:
- `main.py`
- `requirements.txt`
- `.python-version` (opcional)

### Variables de entorno:
- `BOT_TOKEN` → Token del bot
- `DESTINATION_CHAT_ID` → ID del canal donde se enviarán las referencias
- `DB_FILE` → Opcional, nombre del archivo JSON (por defecto: `refes.json`)

### Start Command:
