import os
import json
import html
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
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
DESTINATION_CHAT_ID = "-1003076802840"  # Asegúrate de que el Bot sea ADMIN en este chat
DB_FILE = "refes.json"
SPAIN_TZ = ZoneInfo("Europe/Madrid")

# Cache temporal de álbumes: { media_group_id: [message1, message2, ...] }
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
    """
    Suma 1 punto por cada PUBLICACIÓN de referencias enviada (o la cantidad pasada).
    Se resetea automáticamente cada mes al usar 'mes_actual()' como clave.
    """
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
# REGISTRAR FOTOS Y ÁLBUMES EN CACHE
# ============================================================

async def guardar_foto_album(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Guarda fotos que formen parte de un álbum en la memoria temporal."""
    message = update.message
    if not message or not message.photo or not message.media_group_id:
        return

    album_id = message.media_group_id

    if album_id not in ALBUM_CACHE:
        ALBUM_CACHE[album_id] = []

    # Evitar duplicados por mensaje id
    if not any(msg.message_id == message.message_id for msg in ALBUM_CACHE[album_id]):
        ALBUM_CACHE[album_id].append(message)

# ============================================================
# COMANDO /REFE Y /REFES
# ============================================================

async def refe_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message:
        return

    # Si se pasa un argumento: /refe @usuario o /refes @usuario
    if context.args:
        target_user = context.args[0]
        cantidad = obtener_refes_usuario(target_user)
        await message.reply_text(f"🍒 El usuario {target_user} tiene **{cantidad}** referencia(s) este mes.", parse_mode="Markdown")
        return

    # Si NO es respuesta a un mensaje
    replied = message.reply_to_message
    if not replied:
        await message.reply_text("❗ Debes responder a una imagen/álbum con `/refe` o usar `/refe @usuario` para consultar sus referencias.", parse_mode="Markdown")
        return

    if not replied.photo:
        await message.reply_text("⚠️ El mensaje al que respondes debe contener una imagen.")
        return

    # Datos del autor de la foto original
    user = replied.from_user
    if not user:
        await message.reply_text("❌ No se pudo identificar al usuario de la foto.")
        return

    user_id = str(user.id)
    username = f"@{user.username}" if user.username else (user.first_name or "Usuario")
    fecha = replied.date.astimezone(SPAIN_TZ)
    hora = fecha.strftime("%H:%M:%S")

    # Contar como 1 referencia subida
    refes_totales = sumar_refes(user_id=user_id, username=username, cantidad=1)

    # Identificar fotos (individual o álbum)
    album_id = replied.media_group_id
    fotos_file_ids = []
    caption = replied.caption or ""

    if album_id:
        # Pausa para asegurar que lleguen todas las fotos del grupo
        await asyncio.sleep(1.2)
        album_messages = ALBUM_CACHE.get(album_id, [replied])
        # Ordenar por el id de mensaje
        album_messages.sort(key=lambda m: m.message_id)

        for msg in album_messages:
            fotos_file_ids.append(msg.photo[-1].file_id)
            if not caption and msg.caption:
                caption = msg.caption
    else:
        fotos_file_ids.append(replied.photo[-1].file_id)

    mensaje_txt = html.escape(caption) if caption else "Sin descripción"

    # Plantilla
    plantilla = (
        "命        <b>𝐂𝐇𝐄𝐑𝐑𝐘'𝐒 𝐑𝐄𝐅𝐄𝐑𝐄𝐍𝐂𝐄𝐒.</b>\n\n"
        " ︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶\n"
        f"୧   𝘂𝘀𝘂𝗮𝗿𝗶𝗼   :   {html.escape(username)}\n"
        f"୧   𝗶𝗱   :   {user.id}\n"
        f"୧   𝗵𝗼𝗿𝗮   :   {hora}\n"
        f"୧   𝗺𝗲𝗻𝘀𝗮𝗷𝗲   :   {mensaje_txt}\n"
        f"୧   𝗿𝗲𝗳𝗲𝘀   :   {refes_totales}\n\n"
        "︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶"
    )

    botones = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("𝙄𝙉𝙁𝙊𝙍𝙈𝘼𝙏𝙄𝙊𝙉", url="https://x.com/cheerryspriv"),
            InlineKeyboardButton("𝙊𝙒𝙉𝙀𝙍", url="https://t.me/zilbato")
        ]
    ])

    try:
        # ENVIAR AL CHAT DE DESTINO
        if len(fotos_file_ids) > 1:
            # Es un álbum: construimos un MediaGroup
            media_group = []
            for idx, file_id in enumerate(fotos_file_ids):
                # Solo agregamos la plantilla al primer elemento del álbum
                if idx == 0:
                    media_group.append(InputMediaPhoto(media=file_id, caption=plantilla, parse_mode="HTML"))
                else:
                    media_group.append(InputMediaPhoto(media=file_id))

            await context.bot.send_media_group(
                chat_id=DESTINATION_CHAT_ID,
                media=media_group
            )
        else:
            # Foto individual
            await context.bot.send_photo(
                chat_id=DESTINATION_CHAT_ID,
                photo=fotos_file_ids[0],
                caption=plantilla,
                parse_mode="HTML",
                reply_markup=botones
            )

        # Confirmación en el chat original
        await message.reply_text("✅ Referencia publicada con éxito en el canal.")

        # Limpiar cache si era un álbum
        if album_id:
            ALBUM_CACHE.pop(album_id, None)

    except Exception as e:
        print(f"❌ Error al enviar la referencia: {e}")
        await message.reply_text("❌ Hubo un error al reenviar la referencia.")


# ============================================================
# INICIO DEL BOT
# ============================================================

def main():
    if not BOT_TOKEN:
        print("❌ ERROR: FALTA EL TELEGRAM_TOKEN")
        return

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # 1. Escuchar fotos para guardarlas en memoria en caso de álbumes
    app.add_handler(MessageHandler(filters.PHOTO, guardar_foto_album), group=0)

    # 2. Comandos para activar la referencia (/refe y /refes)
    app.add_handler(CommandHandler(["refe", "refes"], refe_handler), group=1)

    print("🚀 Bot de Referencias Cherry listo y corriendo...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
