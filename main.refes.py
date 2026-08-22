import os
import json
import html
import asyncio
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    filters
)


# ============================================================
# CONFIGURACIÓN
# ============================================================

BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")

DESTINATION_CHAT_ID = "-1003076802840"

DB_FILE = "refes.json"

# Hora española
SPAIN_TZ = ZoneInfo("Europe/Madrid")


# ============================================================
# MEMORIA TEMPORAL DE ÁLBUMES
# ============================================================

# Ejemplo:
#
# {
#   "123456789": {
#       "photos": [...],
#       "caption": "...",
#       "user_id": 123,
#       "username": "usuario",
#       "first_name": "Nombre",
#       "date": ...
#   }
# }
#
ALBUM_CACHE = {}


# ============================================================
# BASE DE DATOS
# ============================================================

def mes_actual():
    """
    Devuelve el mes actual en horario español.
    Ejemplo: 2026-08
    """
    return datetime.now(SPAIN_TZ).strftime("%Y-%m")


def cargar_datos():
    """
    Carga refes.json.
    """
    if not os.path.exists(DB_FILE):
        return {}

    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    except Exception as e:
        print(f"❌ Error leyendo {DB_FILE}: {e}")
        return {}


def guardar_datos(data):
    """
    Guarda refes.json.
    """
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(
                data,
                f,
                ensure_ascii=False,
                indent=2
            )

    except Exception as e:
        print(f"❌ Error guardando {DB_FILE}: {e}")


# ============================================================
# REGISTRAR FOTO DE ÁLBUM
# ============================================================

async def guardar_foto_album(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    message = update.message

    if not message:
        return

    # Solo fotos
    if not message.photo:
        return

    # Si no tiene media_group_id, es una foto individual
    if not message.media_group_id:
        return

    album_id = message.media_group_id

    # Foto en máxima calidad disponible
    photo_file_id = message.photo[-1].file_id

    # Crear álbum en memoria
    if album_id not in ALBUM_CACHE:

        ALBUM_CACHE[album_id] = {
            "photos": [],
            "caption": message.caption,
            "date": message.date,
            "user_id": (
                message.from_user.id
                if message.from_user
                else None
            ),
            "username": (
                message.from_user.username
                if message.from_user
                else None
            ),
            "first_name": (
                message.from_user.first_name
                if message.from_user
                else "Usuario"
            )
        }

    album = ALBUM_CACHE[album_id]

    # Evitar duplicados
    existe = any(
        item["message_id"] == message.message_id
        for item in album["photos"]
    )

    if not existe:

        album["photos"].append({
            "message_id": message.message_id,
            "file_id": photo_file_id
        })

    # Si esta foto tiene caption, guardarlo
    if message.caption:

        album["caption"] = message.caption

    print(
        f"📚 Álbum {album_id}: "
        f"{len(album['photos'])} foto(s) recibidas"
    )


# ============================================================
# SUMAR REFERENCIAS
# ============================================================

def sumar_refes(
    user_id: str,
    username: str,
    cantidad: int
):

    data = cargar_datos()

    mes = mes_actual()

    # Estructura:
    #
    # {
    #   "mensual": {
    #       "2026-08": {
    #           "123456": {
    #               "username": "usuario",
    #               "count": 8
    #           }
    #       }
    #   }
    # }

    if "mensual" not in data:
        data["mensual"] = {}

    if mes not in data["mensual"]:
        data["mensual"][mes] = {}

    if user_id not in data["mensual"][mes]:

        data["mensual"][mes][user_id] = {
            "username": username,
            "count": 0
        }

    # Actualizar username por si ha cambiado
    data["mensual"][mes][user_id]["username"] = username

    # SUMAR todas las fotos
    data["mensual"][mes][user_id]["count"] += cantidad

    guardar_datos(data)

    return data["mensual"][mes][user_id]["count"]


# ============================================================
# BUSCAR REFES DE UN USUARIO
# ============================================================

def obtener_refes_usuario(username_buscado):

    data = cargar_datos()

    mes = mes_actual()

    usuarios = (
        data
        .get("mensual", {})
        .get(mes, {})
    )

    username_buscado = (
        username_buscado
        .replace("@", "")
        .strip()
        .lower()
    )

    for user_id, info in usuarios.items():

        username = str(
            info.get("username", "")
        )

        username = (
            username
            .replace("@", "")
            .strip()
            .lower()
        )

        if username == username_buscado:

            return info.get("count", 0)

    return 0


# ============================================================
# COMANDO /REFE
# ============================================================

async def refe(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    print("")
    print("==========================================")
    print("🔥 /REFE DETECTADO")
    print("==========================================")

    message = update.message

    if not message:
        print("❌ No existe update.message")
        return

    texto = message.text or ""

    print(f"📝 Texto: {texto}")

    # ========================================================
    # /refe @usuario
    # ========================================================

    # Quitamos /refe y opcionalmente @nombrebot
    partes = texto.split()

    argumentos = partes[1:]

    if argumentos:

        usuario_buscado = argumentos[0]

        usuario_buscado = (
            usuario_buscado
            .replace("@", "")
            .strip()
        )

        if not usuario_buscado:

            await message.reply_text(
                "❗ Escribe un usuario después de /refe."
            )

            return

        cantidad = obtener_refes_usuario(
            usuario_buscado
        )

        await message.reply_text(
            f"@{usuario_buscado} tiene {cantidad} referencias."
        )

        print(
            f"🔎 Consulta: @{usuario_buscado} "
            f"→ {cantidad} refes"
        )

        return

    # ========================================================
    # /REFE RESPONDIENDO A UNA FOTO
    # ========================================================

    replied = message.reply_to_message

    if not replied:

        print("❌ /refe no es respuesta a ningún mensaje")

        await message.reply_text(
            "❗ Responde a una imagen con /refe."
        )

        return

    print(
        f"↩️ Responde al mensaje: {replied.message_id}"
    )

    # ========================================================
    # COMPROBAR QUE SEA FOTO
    # ========================================================

    if not replied.photo:

        print("❌ El mensaje respondido no es una foto")

        await message.reply_text(
            "⚠️ Tienes que responder a una imagen."
        )

        return

    # ========================================================
    # USUARIO QUE MANDÓ LA FOTO
    # ========================================================

    user = replied.from_user

    if not user:

        await message.reply_text(
            "❌ No se pudo identificar al usuario."
        )

        return

    user_id = str(user.id)

    if user.username:

        username = "@" + user.username

    else:

        username = user.first_name or "Usuario"

    print(
        f"👤 Usuario: {username}"
    )

    print(
        f"🆔 ID: {user_id}"
    )

    # ========================================================
    # HORA ESPAÑOLA
    # ========================================================

    fecha = replied.date.astimezone(
        SPAIN_TZ
    )

    hora = fecha.strftime(
        "%H:%M:%S"
    )

    # ========================================================
    # OBTENER FOTOS
    # ========================================================

    album_id = replied.media_group_id

    fotos = []

    caption = replied.caption

    # ========================================================
    # SI ES ÁLBUM
    # ========================================================

    if album_id:

        print(
            f"📚 ES UN ÁLBUM → {album_id}"
        )

        # Esperamos un poco para que Telegram
        # termine de entregar todas las fotos.
        await asyncio.sleep(1.5)

        album = ALBUM_CACHE.get(album_id)

        if album:

            # Ordenar por message_id
            album["photos"].sort(
                key=lambda x: x["message_id"]
            )

            fotos = [
                item["file_id"]
                for item in album["photos"]
            ]

            if not caption:

                caption = album.get(
                    "caption"
                )

        print(
            f"📸 Fotos encontradas en álbum: {len(fotos)}"
        )

    # ========================================================
    # SI ES FOTO INDIVIDUAL
    # ========================================================

    if not fotos:

        print(
            "📷 FOTO INDIVIDUAL"
        )

        fotos = [
            replied.photo[-1].file_id
        ]

    # ========================================================
    # MENSAJE
    # ========================================================

    if caption:

        mensaje = html.escape(
            caption
        )

    else:

        mensaje = "No hay mensaje"

    # ========================================================
    # SUMAR REFES
    # ========================================================

    cantidad_fotos = len(fotos)

    refes_totales = sumar_refes(
        user_id=user_id,
        username=username,
        cantidad=cantidad_fotos
    )

    print(
        f"🍒 +{cantidad_fotos} REFES"
    )

    print(
        f"🏆 TOTAL MENSUAL: {refes_totales}"
    )

    # ========================================================
    # PLANTILLA
    # ========================================================

    plantilla = (
        "命         <b>𝐂𝐇𝐄𝐑𝐑𝐘'𝐒 𝐑𝐄𝐅𝐄𝐑𝐄𝐍𝐂𝐄𝐒.</b>\n"
        "\n"
        " ︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶\n"
        f"୧   𝘂𝘀𝘂𝗮𝗿𝗶𝗼   :   {html.escape(username)}\n"
        f"୧   𝗶𝗱   :   {user.id}\n"
        f"୧   𝗵𝗼𝗿𝗮   :   {hora}\n"
        f"୧   𝗺𝗲𝗻𝘀𝗮𝗷𝗲   :   {mensaje}\n"
        f"୧   𝗿𝗲𝗳𝗲𝘀   :   {refes_totales}\n"
        "\n"
        "︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶"
    )

    # ========================================================
    # BOTONES
    # ========================================================

    botones = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "𝙄𝙉𝙁𝙊𝙍𝙈𝘼𝙏𝙄𝙊𝙉",
                    url="https://x.com/cheerryspriv"
                ),
                InlineKeyboardButton(
                    "𝙊𝙒𝙉𝙀𝙍",
                    url="https://t.me/zilbato"
                )
            ]
        ]
    )

    # ========================================================
    # ENVIAR TODAS LAS FOTOS UNA POR UNA
    # ========================================================

    print(
        f"📤 ENVIANDO {cantidad_fotos} FOTO(S)"
    )

    try:

        for numero, foto in enumerate(
            fotos,
            start=1
        ):

            print(
                f"📤 Enviando "
                f"{numero}/{cantidad_fotos}"
            )

            await context.bot.send_photo(
                chat_id=DESTINATION_CHAT_ID,
                photo=foto,
                caption=plantilla,
                parse_mode="HTML",
                reply_markup=botones
            )

            # Pequeña pausa para evitar enviar
            # demasiadas peticiones seguidas.
            await asyncio.sleep(0.4)

        print(
            "=========================================="
        )

        print(
            "✅ REFERENCIA ENVIADA CORRECTAMENTE"
        )

        print(
            "=========================================="
        )

        # Limpiar álbum después de enviarlo
        if album_id:

            ALBUM_CACHE.pop(
                album_id,
                None
            )

    except Exception as e:

        print(
            f"❌ ERROR ENVIANDO REFERENCIA: {e}"
        )

        await message.reply_text(
            "❌ Ha ocurrido un error al enviar la referencia."
        )


# ============================================================
# INICIO DEL BOT
# ============================================================

def main():

    print("")
    print("==========================================")
    print("🍒 CHERRY'S REFES")
    print("==========================================")
    print("🚀 Bot iniciándose...")
    print("")

    # Comprobar token

    if not BOT_TOKEN:

        print(
            "❌ ERROR: NO EXISTE TELEGRAM_TOKEN"
        )

        print(
            "Añade TELEGRAM_TOKEN en Railway."
        )

        return

    print(
        "🔑 TELEGRAM_TOKEN encontrado"
    )

    # ========================================================
    # CREAR APLICACIÓN
    # ========================================================

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .build()
    )

    # ========================================================
    # RECIBIR FOTOS
    # ========================================================

    app.add_handler(
        MessageHandler(
            filters.PHOTO,
            guardar_foto_album
        ),
        group=0
    )

    # ========================================================
    # DETECTAR /REFE
    #
    # Usamos MessageHandler en vez de CommandHandler
    # para que /refe sea detectado directamente.
    # ========================================================

    app.add_handler(
        MessageHandler(
            filters.Regex(
                r"^/refe(?:@\w+)?(?:\s+.*)?$"
            ),
            refe
        ),
        group=1
    )

    print(
        "📷 Fotos individuales: ACTIVADO"
    )

    print(
        "📚 Álbumes: ACTIVADO"
    )

    print(
        "🍒 /refe: ACTIVADO"
    )

    print(
        "🔎 /refe @usuario: ACTIVADO"
    )

    print("")
    print(
        "=========================================="
    )
    print(
        "✅ BOT LISTO"
    )
    print(
        "=========================================="
    )

    # ========================================================
    # INICIAR POLLING
    # ========================================================

    app.run_polling(
        drop_pending_updates=False
    )


# ============================================================
# EJECUTAR
# ============================================================

if __name__ == "__main__":
    main()
