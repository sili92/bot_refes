import os
import json
import html
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    CommandHandler,
    filters
)

# ============================================================
# CONFIGURACIÓN
# ============================================================

BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
DESTINATION_CHAT_ID = "-1003076802840"  # ID de tu canal/grupo de destino
DB_FILE = "refes.json"
SPAIN_TZ = ZoneInfo("Europe/Madrid")

# Cache temporal de álbumes en memoria
ALBUM_CACHE = {}

# ============================================================
# BASE DE DATOS Y UTILIDADES
# ============================================================

def mes_actual():
    """Devuelve el mes actual en horario español (Ej: 2026-08)."""
    return datetime.now(SPAIN_TZ).strftime("%Y-%m")

def cargar_datos():
    if not os.path.exists(DB_FILE):
        return {}
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Error leyendo {DB_FILE}: {e}")
        return {}

def guardar_datos(data):
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"❌ Error guardando {DB_FILE}: {e}")

def sumar_refes(user_id: str, username: str, cantidad: int = 1):
    """Suma 'cantidad' referencias al total del mes."""
    data = cargar_datos()
    mes = mes_actual()

    if "mensual" not in data:
        data["mensual"] = {}
    if mes not in data["mensual"]:
        data["mensual"][mes] = {}

    if user_id not in data["mensual"][mes]:
        data["mensual"][mes][user_id] = {
            "username": username,
            "count": 0
        }

    data["mensual"][mes][user_id]["username"] = username
    data["mensual"][mes][user_id]["count"] += cantidad
    guardar_datos(data)

    return data["mensual"][mes][user_id]["count"]

def obtener_refes_usuario(username_buscado: str):
    data = cargar_datos()
    mes = mes_actual()
    usuarios = data.get("mensual", {}).get(mes, {})
    
    clean_target = username_buscado.replace("@", "").strip().lower()

    for user_id, info in usuarios.items():
        uname = str(info.get("username", "")).replace("@", "").strip().lower()
        if uname == clean_target:
            return info.get("count", 0)

    return 0

# ============================================================
# REGISTRAR FOTOS EN CACHE
# ============================================================

async def guardar_foto_album(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Captura cada foto que entra si pertenece a un álbum."""
    message = update.message
    if not message or not message.photo or not message.media_group_id:
        return

    album_id = message.media_group_id

    if album_id not in ALBUM_CACHE:
        ALBUM_CACHE[album_id] = []

    # Evitamos duplicados
    if not any(msg.message_id == message.message_id for msg in ALBUM_CACHE[album_id]):
        ALBUM_CACHE[album_id].append(message)

# ============================================================
# COMANDO /REFE Y /REFES
# ============================================================

async def refe_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message:
        return

    # 1. Consulta por usuario: /refe @usuario o /refes @usuario
    if context.args:
        target_user = context.args[0]
        # Nos aseguramos de mantener o colocar la @ si no la incluye
        formatted_user = target_user if target_user.startswith("@") else f"@{target_user}"
        cantidad = obtener_refes_usuario(formatted_user)
        
        texto_consulta = f"(⑅˘͈ ᵕ ˘͈ )  el usuario {formatted_user} cuenta\ncon {cantidad} referencia(s) este mes. ¡sigue así!"
        await message.reply_text(texto_consulta)
        return

    # 2. Comprobar respuesta a un mensaje
    replied = message.reply_to_message
    if not replied or not replied.photo:
        await message.reply_text("(๑´`๑)  debes responder a una\nfoto o álbum para enviar tu refe.")
        return

    # Datos del usuario objetivo
    user = replied.from_user
    if not user:
        await message.reply_text("❌ No se pudo identificar al usuario de la foto.")
        return

    user_id = str(user.id)
    username = f"@{user.username}" if user.username else (user.first_name or "Usuario")
    fecha = replied.date.astimezone(SPAIN_TZ)
    hora = fecha.strftime("%H:%M:%S")

    # Identificar si es un álbum o una foto individual
    album_id = replied.media_group_id
    fotos_file_ids = []
    caption = replied.caption or ""

    if album_id:
        # Pausa ampliada para garantizar recepción completa del álbum
        await asyncio.sleep(2.0)
        album_messages = ALBUM_CACHE.get(album_id, [])
        
        # Si la lista no contenía la foto respondida (ej. tras un reinicio del bot), la agregamos
        if not any(m.message_id == replied.message_id for m in album_messages):
            album_messages.append(replied)

        album_messages.sort(key=lambda m: m.message_id)

        for msg in album_messages:
            fotos_file_ids.append(msg.photo[-1].file_id)
            if not caption and msg.caption:
                caption = msg.caption
    else:
        fotos_file_ids.append(replied.photo[-1].file_id)

    # Texto del mensaje o por defecto "No hay mensaje"
    mensaje_txt = html.escape(caption) if caption else "No hay mensaje"

    # Calcular cuántas fotos son en total
    total_fotos_nuevas = len(fotos_file_ids)

    # Obtenemos las refes acumuladas actualizadas
    refes_acumuladas = sumar_refes(user_id=user_id, username=username, cantidad=total_fotos_nuevas)

    # La primera foto publicada tendrá el número inicial del contador
    refes_inicio = refes_acumuladas - total_fotos_nuevas + 1

    botones = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("𝙄𝙉𝙁𝙊𝙍𝙈𝘼𝙏𝙄𝙊𝙉", url="https://t.me/infocherrys"),
            InlineKeyboardButton("𝙊𝙒𝙉𝙀𝙍", url="https://t.me/zilbato")
        ]
    ])

    # Enviar las fotos UNA POR UNA
    try:
        for idx, photo_id in enumerate(fotos_file_ids):
            refe_actual = refes_inicio + idx

            plantilla = (
                "命        <b>𝐂𝐇𝐄𝐑𝐑𝐘'𝐒 𝐑𝐄𝐅𝐄𝐑𝐄𝐍𝐂𝐄𝐒.</b>\n\n"
                " ︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶\n"
                f"୧   𝘂𝘀𝘂𝗮𝗿𝗶𝗼   :   {html.escape(username)}\n"
                f"୧   𝗶𝗱   :   {user.id}\n"
                f"୧   𝗵𝗼𝗿𝗮   :   {hora}\n"
                f"୧   𝗺𝗲𝗻𝘀𝗮𝗷𝗲   :   {mensaje_txt}\n"
                f"୧   𝗿𝗲𝗳𝗲𝘀   :   {refe_actual}\n\n"
                "︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶"
            )

            await context.bot.send_photo(
                chat_id=DESTINATION_CHAT_ID,
                photo=photo_id,
                caption=plantilla,
                parse_mode="HTML",
                reply_markup=botones
            )

            await asyncio.sleep(0.4)

        # Mensaje personalizado tras enviar la refe al canal
        await message.reply_text("٩(ˊᗜˋ*)و   ¡gracias por tus refes!\n se han enviado al canal. ♡")

        # Limpiar memoria del álbum
        if album_id:
            ALBUM_CACHE.pop(album_id, None)

    except Exception as e:
        print(f"❌ Error al enviar las fotos: {e}")
        await message.reply_text("❌ Ocurrió un error al enviar las fotos.")

# ============================================================
# INICIO DEL BOT
# ============================================================

def main():
    if not BOT_TOKEN:
        print("❌ ERROR: FALTA EL TELEGRAM_TOKEN")
        return

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(MessageHandler(filters.PHOTO, guardar_foto_album), group=0)
    app.add_handler(CommandHandler(["refe", "refes"], refe_handler), group=1)

    print("🚀 Bot listo y funcionando...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
