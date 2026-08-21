import os
import json
import html
import asyncio
from datetime import datetime, timedelta

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto
)

from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
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

# Guarda temporalmente los álbumes
ALBUM_CACHE = {}


# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def mes_actual():
    return datetime.now().strftime("%Y-%m")


def semana_actual():
    """
    Devuelve el identificador de la semana actual.
    Ejemplo: 2026-W34
    """
    return datetime.now().strftime("%G-W%V")


def cargar_datos():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    return {}


def guardar_datos(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2
        )


# ============================================================
# GUARDAR ÁLBUMES
# ============================================================

async def guardar_album(update: Update, context: ContextTypes.DEFAULT_TYPE):

    message = update.message

    if not message:
        return

    if not message.photo:
        return

    media_group_id = message.media_group_id

    # Foto individual
    if not media_group_id:
        return

    photo_id = message.photo[-1].file_id

    if media_group_id not in ALBUM_CACHE:

        ALBUM_CACHE[media_group_id] = {
            "photos": [],
            "caption": message.caption or "",
            "date": message.date
        }

    album = ALBUM_CACHE[media_group_id]

    if photo_id not in album["photos"]:
        album["photos"].append(photo_id)


# ============================================================
# COMANDO /REFE
# ============================================================

async def refe(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "✅ ¡Comando recibido!"
    )

    # ========================================================
    # COMPROBAR RESPUESTA
    # ========================================================

    if not update.message.reply_to_message:

        await update.message.reply_text(
            "❗ Responde a una imagen para referenciarla."
        )

        return

    replied_message = update.message.reply_to_message

    # ========================================================
    # COMPROBAR FOTO
    # ========================================================

    if not replied_message.photo:

        await update.message.reply_text(
            "⚠️ Solo se permiten imágenes."
        )

        return

    # ========================================================
    # USUARIO
    # ========================================================

    img_user = replied_message.from_user

    if not img_user:
        return

    img_user_id = str(img_user.id)

    if img_user.username:
        img_username = "@" + img_user.username
    else:
        img_username = img_user.first_name


    # ========================================================
    # DETECTAR ÁLBUM
    # ========================================================

    media_group_id = replied_message.media_group_id

    if media_group_id:

        # Esperamos para asegurarnos de que todas las
        # fotos del álbum hayan llegado al bot.
        await asyncio.sleep(2)


    # ========================================================
    # OBTENER FOTOS
    # ========================================================

    album_photos = []

    if media_group_id:

        album = ALBUM_CACHE.get(media_group_id)

        if album:
            album_photos = album["photos"].copy()


    # Si no encontramos el álbum, usamos la foto respondida.
    if not album_photos:

        album_photos = [
            replied_message.photo[-1].file_id
        ]


    # ========================================================
    # NÚMERO DE REFERENCIAS
    # ========================================================

    # FOTO SOLA = 1
    # ÁLBUM DE 8 FOTOS = 8
    numero_refes = len(album_photos)


    # ========================================================
    # BASE DE DATOS
    # ========================================================

    data = cargar_datos()

    mes = mes_actual()
    semana = semana_actual()


    # ========================================================
    # ESTRUCTURA MENSUAL
    # ========================================================

    if "mensual" not in data:
        data["mensual"] = {}

    if mes not in data["mensual"]:
        data["mensual"][mes] = {}


    if img_user_id not in data["mensual"][mes]:

        data["mensual"][mes][img_user_id] = {
            "username": img_username,
            "count": 0
        }


    # Sumar TODAS las fotos
    data["mensual"][mes][img_user_id]["count"] += numero_refes

    # Actualizar username por si ha cambiado
    data["mensual"][mes][img_user_id]["username"] = img_username


    # ========================================================
    # ESTRUCTURA SEMANAL
    # ========================================================

    if "semanal" not in data:
        data["semanal"] = {}

    if semana not in data["semanal"]:
        data["semanal"][semana] = {}


    if img_user_id not in data["semanal"][semana]:

        data["semanal"][semana][img_user_id] = {
            "username": img_username,
            "count": 0
        }


    # Sumar TODAS las fotos también semanalmente
    data["semanal"][semana][img_user_id]["count"] += numero_refes

    data["semanal"][semana][img_user_id]["username"] = img_username


    # Guardar
    guardar_datos(data)


    # ========================================================
    # DATOS DE LA REFERENCIA
    # ========================================================

    time = replied_message.date.strftime(
        "%I:%M:%S %p"
    )

    original_message = html.escape(
        replied_message.caption or ""
    )


    # ========================================================
    # REFES MENSUALES DEL USUARIO
    # ========================================================

    refes_mensuales = data["mensual"][mes][img_user_id]["count"]


    # ========================================================
    # PLANTILLA
    # ========================================================

    formatted_message = (
        "命         <b>𝐂𝐇𝐄𝐑𝐑𝐘'𝐒 𝐑𝐄𝐅𝐄𝐑𝐄𝐍𝐂𝐄𝐒.</b>\n"
        "︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶\n"
        f"୧   <b>𝘂𝘀𝘂𝗮𝗿𝗶𝗼</b>   :   "
        f"{html.escape(img_username)}\n"
        f"୧   <b>𝗶𝗱</b>   :   "
        f"{img_user.id}\n"
        f"୧   <b>𝗵𝗼𝗿𝗮</b>   :   "
        f"{time}\n"
        f"୧   <b>𝗺𝗲𝗻𝘀𝗮𝗷𝗲</b>   :   "
        f"{original_message}\n"
        f"୧   <b>𝗿𝗲𝗳𝗲𝘀</b>   :   "
        f"{refes_mensuales}\n"
        "︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶"
    )


    # ========================================================
    # BOTONES
    # ========================================================

    buttons = [
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

    keyboard = InlineKeyboardMarkup(buttons)


    # ========================================================
    # ENVIAR REFERENCIA
    # ========================================================

    try:

        # ====================================================
        # ÁLBUM
        # ====================================================

        if media_group_id and len(album_photos) > 1:

            media = []

            for index, photo_id in enumerate(album_photos):

                # La plantilla solo aparece en la primera foto
                if index == 0:

                    media.append(
                        InputMediaPhoto(
                            media=photo_id,
                            caption=formatted_message,
                            parse_mode="HTML"
                        )
                    )

                else:

                    media.append(
                        InputMediaPhoto(
                            media=photo_id
                        )
                    )


            # Telegram lo envía como álbum
            await context.bot.send_media_group(
                chat_id=DESTINATION_CHAT_ID,
                media=media
            )


            # Botones debajo del álbum
            await context.bot.send_message(
                chat_id=DESTINATION_CHAT_ID,
                text="ㅤ",
                reply_markup=keyboard
            )


        # ====================================================
        # FOTO INDIVIDUAL
        # ====================================================

        else:

            await context.bot.send_photo(
                chat_id=DESTINATION_CHAT_ID,
                photo=album_photos[0],
                caption=formatted_message,
                parse_mode="HTML",
                reply_markup=keyboard
            )


        # Limpiar álbum
        if media_group_id:

            ALBUM_CACHE.pop(
                media_group_id,
                None
            )


    except Exception as e:

        print(
            f"❌ Error al enviar referencia: {e}"
        )

        await update.message.reply_text(
            "❌ Error al enviar al canal."
        )


# ============================================================
# BUSCAR USUARIO PARA /REFES
# ============================================================

def buscar_usuario(data, argumento):

    argumento = argumento.strip()

    # Quitar @
    if argumento.startswith("@"):
        argumento = argumento[1:]

    argumento_lower = argumento.lower()

    # Buscar en las semanas guardadas
    for semana_data in data.get("semanal", {}).values():

        for user_id, user_data in semana_data.items():

            username = str(
                user_data.get("username", "")
            ).replace("@", "").lower()

            if username == argumento_lower:
                return user_id

            if str(user_id) == argumento:
                return user_id

    # Buscar también en mensual
    for mes_data in data.get("mensual", {}).values():

        for user_id, user_data in mes_data.items():

            username = str(
                user_data.get("username", "")
            ).replace("@", "").lower()

            if username == argumento_lower:
                return user_id

            if str(user_id) == argumento:
                return user_id

    return None


# ============================================================
# /REFES
# ============================================================

async def refes(update: Update, context: ContextTypes.DEFAULT_TYPE):

    data = cargar_datos()

    semana = semana_actual()

    user_id = None
    username = None


    # ========================================================
    # OPCIÓN 1: /refes @usuario
    # ========================================================

    if context.args:

        argumento = context.args[0]

        user_id = buscar_usuario(
            data,
            argumento
        )

        if user_id:

            # Buscar nombre
            if semana in data.get("semanal", {}):

                user_data = data["semanal"][semana].get(
                    user_id
                )

                if user_data:
                    username = user_data.get(
                        "username",
                        argumento
                    )


    # ========================================================
    # OPCIÓN 2: RESPONDER A UN USUARIO
    # ========================================================

    elif update.message.reply_to_message:

        replied = update.message.reply_to_message

        if replied.from_user:

            user_id = str(
                replied.from_user.id
            )

            if replied.from_user.username:

                username = (
                    "@"
                    + replied.from_user.username
                )

            else:

                username = (
                    replied.from_user.first_name
                )


    # ========================================================
    # SI NO ENCUENTRA USUARIO
    # ========================================================

    if not user_id:

        await update.message.reply_text(
            "❗ Usa /refes @usuario o responde a un mensaje del usuario."
        )

        return


    # ========================================================
    # OBTENER REFES SEMANALES
    # ========================================================

    semanal_data = data.get(
        "semanal",
        {}
    )

    user_data = semanal_data.get(
        semana,
        {}
    ).get(
        user_id,
        {}
    )

    cantidad = user_data.get(
        "count",
        0
    )


    # Si no tenemos username todavía
    if not username:

        username = user_data.get(
            "username",
            f"ID {user_id}"
        )


    # ========================================================
    # RESPUESTA
    # ========================================================

    await update.message.reply_text(
        f"🍒 <b>REFES SEMANALES</b>\n\n"
        f"୧   <b>𝘂𝘀𝘂𝗮𝗿𝗶𝗼</b> : "
        f"{html.escape(username)}\n"
        f"୧   <b>𝗶𝗱</b> : "
        f"{user_id}\n"
        f"୧   <b>𝗿𝗲𝗳𝗲𝘀</b> : "
        f"{cantidad}",
        parse_mode="HTML"
    )


# ============================================================
# /TOPREFE
# ============================================================

async def toprefe(update: Update, context: ContextTypes.DEFAULT_TYPE):

    data = cargar_datos()

    mes = mes_actual()

    mensual_data = data.get(
        "mensual",
        {}
    )

    if mes not in mensual_data or not mensual_data[mes]:

        await update.message.reply_text(
            "¡Aún no hay referencias este mes!"
        )

        return


    top = sorted(
        mensual_data[mes].values(),
        key=lambda x: x["count"],
        reverse=True
    )


    mensaje = (
        f"🏆 <b>𝗧𝗢𝗣 𝗥𝗘𝗙𝗘𝗥𝗘𝗡𝗖𝗜𝗔𝗦 - {mes}</b>\n\n"
    )


    for i, user in enumerate(top[:10], 1):

        mensaje += (
            f"{i}. "
            f"{html.escape(user['username'])}: "
            f"{user['count']} refes\n"
        )


    await update.message.reply_text(
        mensaje,
        parse_mode="HTML"
    )


# ============================================================
# INICIO DEL BOT
# ============================================================

def main():

    print(
        "✅ Bot iniciándose correctamente..."
    )

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .build()
    )


    # Detectar álbumes
    app.add_handler(
        MessageHandler(
            filters.PHOTO,
            guardar_album
        )
    )


    # /refe
    app.add_handler(
        CommandHandler(
            "refe",
            refe
        )
    )


    # /refes
    app.add_handler(
        CommandHandler(
            "refes",
            refes
        )
    )


    # /toprefe
    app.add_handler(
        CommandHandler(
            "toprefe",
            toprefe
        )
    )


    # Iniciar
    app.run_polling()


# ============================================================
# EJECUTAR
# ============================================================

if __name__ == "__main__":
    main()
