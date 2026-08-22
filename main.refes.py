import os
import json
import html
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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

# Zona horaria española
SPAIN_TZ = ZoneInfo("Europe/Madrid")

# Aquí se guardan temporalmente los álbumes recibidos
ALBUM_CACHE = {}


# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def ahora_españa():
    return datetime.now(SPAIN_TZ)


def mes_actual():
    return ahora_españa().strftime("%Y-%m")


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
# RECIBIR FOTOS DE LOS ÁLBUMES
# ============================================================

async def guardar_album(update: Update, context: ContextTypes.DEFAULT_TYPE):

    message = update.message

    if not message:
        return

    if not message.photo:
        return

    media_group_id = message.media_group_id

    # Si no pertenece a un álbum, no hay nada que guardar aquí
    if not media_group_id:
        return

    photo_id = message.photo[-1].file_id

    # Crear el álbum si todavía no existe
    if media_group_id not in ALBUM_CACHE:

        ALBUM_CACHE[media_group_id] = {
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

    album = ALBUM_CACHE[media_group_id]

    # Evitar duplicados
    if photo_id not in album["photos"]:
        album["photos"].append(photo_id)

        print(
            f"📸 Álbum {media_group_id}: "
            f"{len(album['photos'])} imagen(es)"
        )


# ============================================================
# SUMAR REFERENCIAS
# ============================================================

def sumar_refes(user_id, username, cantidad):

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

    # Actualizar username
    data["mensual"][mes][user_id]["username"] = username

    # Sumar todas las imágenes
    data["mensual"][mes][user_id]["count"] += cantidad

    guardar_datos(data)

    return data["mensual"][mes][user_id]["count"]


# ============================================================
# OBTENER REFES DE UN USUARIO
# ============================================================

def obtener_refes(user_id):

    data = cargar_datos()
    mes = mes_actual()

    return (
        data
        .get("mensual", {})
        .get(mes, {})
        .get(str(user_id), {})
        .get("count", 0)
    )


# ============================================================
# /REFE
# ============================================================

async def refe(update: Update, context: ContextTypes.DEFAULT_TYPE):

    message = update.message

    if not message:
        return


    # ========================================================
    # SI ES /REFE @USUARIO
    # ========================================================

    if context.args:

        argumento = context.args[0].strip()

        if argumento.startswith("@"):
            argumento = argumento[1:]

        argumento = argumento.lower()

        data = cargar_datos()
        mes = mes_actual()

        usuarios = (
            data
            .get("mensual", {})
            .get(mes, {})
        )

        encontrado = None

        for user_id, info in usuarios.items():

            username = str(
                info.get("username", "")
            ).replace("@", "").lower()

            if username == argumento:

                encontrado = (
                    user_id,
                    info
                )

                break

        if encontrado:

            user_id, info = encontrado

            username = info.get(
                "username",
                "@" + argumento
            )

            cantidad = info.get(
                "count",
                0
            )

            await message.reply_text(
                f"{username} tiene {cantidad} referencias."
            )

        else:

            await message.reply_text(
                f"@{argumento} tiene 0 referencias."
            )

        return


    # ========================================================
    # /REFE NORMAL
    # ========================================================

    if not message.reply_to_message:

        await message.reply_text(
            "❗ Responde a una imagen para referenciarla."
        )

        return

    replied = message.reply_to_message


    # ========================================================
    # COMPROBAR QUE SEA IMAGEN
    # ========================================================

    if not replied.photo:

        await message.reply_text(
            "⚠️ Solo se permiten imágenes."
        )

        return


    # ========================================================
    # USUARIO QUE MANDÓ LA FOTO
    # ========================================================

    user = replied.from_user

    if not user:
        return

    user_id = str(user.id)

    if user.username:
        username = "@" + user.username
    else:
        username = user.first_name


    # ========================================================
    # OBTENER HORA ESPAÑOLA
    # ========================================================

    hora = replied.date.astimezone(
        SPAIN_TZ
    ).strftime("%H:%M:%S")


    # ========================================================
    # DETECTAR ÁLBUM
    # ========================================================

    media_group_id = replied.media_group_id

    photos = []


    if media_group_id:

        print(
            f"🔎 Detectado álbum: {media_group_id}"
        )

        # Esperamos a que lleguen todas las imágenes
        # del álbum al bot.
        for _ in range(5):

            await asyncio.sleep(1)

            album = ALBUM_CACHE.get(
                media_group_id
            )

            if album:

                photos = album["photos"].copy()

                print(
                    f"📸 Fotos encontradas: "
                    f"{len(photos)}"
                )


    # ========================================================
    # FOTO INDIVIDUAL
    # ========================================================

    if not photos:

        photos = [
            replied.photo[-1].file_id
        ]


    # ========================================================
    # MENSAJE / CAPTION
    # ========================================================

    mensaje = replied.caption

    if not mensaje and media_group_id:

        album = ALBUM_CACHE.get(
            media_group_id
        )

        if album:
            mensaje = album.get(
                "caption"
            )


    if mensaje:
        mensaje = html.escape(mensaje)
    else:
        mensaje = "No hay mensaje"


    # ========================================================
    # SUMAR REFES
    #
    # 1 FOTO = 1 REFE
    # 8 FOTOS = 8 REFES
    # ========================================================

    cantidad = len(photos)

    refes_totales = sumar_refes(
        user_id,
        username,
        cantidad
    )


    print(
        f"🍒 {username} → "
        f"+{cantidad} refes | "
        f"total mensual: {refes_totales}"
    )


    # ========================================================
    # PLANTILLA
    # ========================================================

    plantilla = (
        "命         <b>𝐂𝐇𝐄𝐑𝐑𝐘'𝐒 𝐑𝐄𝐅𝐄𝐑𝐄𝐍𝐂𝐄𝐒.</b>\n"
        "\n"
        " ︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶\n"
        f"୧   <b>𝘂𝘀𝘂𝗮𝗿𝗶𝗼</b>   :   "
        f"{html.escape(username)}\n"
        f"୧   <b>𝗶𝗱</b>   :   "
        f"{user.id}\n"
        f"୧   <b>𝗵𝗼𝗿𝗮</b>   :   "
        f"{hora}\n"
        f"୧   <b>𝗺𝗲𝗻𝘀𝗮𝗷𝗲</b>   :   "
        f"{mensaje}\n"
        f"୧   <b>𝗿𝗲𝗳𝗲𝘀</b>   :   "
        f"{refes_totales}\n"
        "\n"
        "︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶"
    )


    # ========================================================
    # BOTONES
    # ========================================================

    keyboard = InlineKeyboardMarkup([
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
    ])


    # ========================================================
    # ENVIAR AL OTRO CANAL
    #
    # IMPORTANTE:
    # Las imágenes se envían UNA POR UNA.
    # ========================================================

    try:

        for index, photo_id in enumerate(photos):

            # Cada imagen se manda individualmente
            await context.bot.send_photo(
                chat_id=DESTINATION_CHAT_ID,
                photo=photo_id,
                caption=plantilla,
                parse_mode="HTML",
                reply_markup=keyboard
            )

            # Pequeña pausa para evitar problemas de flood
            if index < len(photos) - 1:
                await asyncio.sleep(0.3)


        print(
            f"✅ Enviadas {len(photos)} imagen(es)"
        )


        # ====================================================
        # LIMPIAR ÁLBUM
        # ====================================================

        if media_group_id:

            ALBUM_CACHE.pop(
                media_group_id,
                None
            )


    except Exception as e:

        print(
            f"❌ Error al enviar referencia: {e}"
        )

        await message.reply_text(
            "❌ Error al enviar al canal."
        )


# ============================================================
# INICIO
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


    # --------------------------------------------------------
    # RECIBIR FOTOS DE ÁLBUMES
    # --------------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.PHOTO,
            guardar_album
        )
    )


    # --------------------------------------------------------
    # /REFE
    # --------------------------------------------------------

    app.add_handler(
        CommandHandler(
            "refe",
            refe
        )
    )


    # --------------------------------------------------------
    # INICIAR
    # --------------------------------------------------------

    app.run_polling()


if __name__ == "__main__":
    main()
