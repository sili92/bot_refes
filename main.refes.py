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

SPAIN_TZ = ZoneInfo("Europe/Madrid")

# Guardamos temporalmente las fotos de los álbumes
ALBUM_CACHE = {}


# ============================================================
# FUNCIONES
# ============================================================

def mes_actual():
    return datetime.now(SPAIN_TZ).strftime("%Y-%m")


def cargar_datos():

    if not os.path.exists(DB_FILE):
        return {}

    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    except Exception as e:
        print(f"❌ Error leyendo base de datos: {e}")
        return {}


def guardar_datos(data):

    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(
                data,
                f,
                ensure_ascii=False,
                indent=2
            )

    except Exception as e:
        print(f"❌ Error guardando base de datos: {e}")


# ============================================================
# GUARDAR FOTOS DE LOS ÁLBUMES
# ============================================================

async def recibir_fotos(update: Update, context: ContextTypes.DEFAULT_TYPE):

    message = update.message

    if not message:
        return

    if not message.photo:
        return

    # --------------------------------------------------------
    # FOTO QUE NO ES ÁLBUM
    # --------------------------------------------------------

    if not message.media_group_id:
        print(
            f"📷 Foto individual recibida: "
            f"{message.message_id}"
        )
        return

    # --------------------------------------------------------
    # ÁLBUM
    # --------------------------------------------------------

    album_id = message.media_group_id

    photo_id = message.photo[-1].file_id

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
    if photo_id not in album["photos"]:

        album["photos"].append(photo_id)

        print(
            f"📸 ÁLBUM {album_id} → "
            f"{len(album['photos'])} foto(s)"
        )


# ============================================================
# SUMAR REFES
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

    data["mensual"][mes][user_id]["username"] = username

    data["mensual"][mes][user_id]["count"] += cantidad

    guardar_datos(data)

    return data["mensual"][mes][user_id]["count"]


# ============================================================
# OBTENER REFES
# ============================================================

def buscar_usuario(username):

    data = cargar_datos()

    mes = mes_actual()

    usuarios = (
        data
        .get("mensual", {})
        .get(mes, {})
    )

    username = username.replace("@", "").lower()

    for user_id, info in usuarios.items():

        guardado = str(
            info.get("username", "")
        ).replace("@", "").lower()

        if guardado == username:
            return user_id, info

    return None, None


# ============================================================
# /REFE
# ============================================================

async def refe(update: Update, context: ContextTypes.DEFAULT_TYPE):

    message = update.message

    if not message:
        return

    print(
        f"🟢 /refe recibido | "
        f"message_id={message.message_id}"
    )


    # ========================================================
    # /REFE @USUARIO
    # ========================================================

    if context.args:

        argumento = context.args[0]

        if argumento.startswith("@"):
            argumento = argumento[1:]

        user_id, info = buscar_usuario(argumento)

        if info:

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
    # /REFE RESPONDIENDO A UNA FOTO
    # ========================================================

    if not message.reply_to_message:

        await message.reply_text(
            "❗ Responde a una imagen con /refe."
        )

        return

    foto_original = message.reply_to_message


    # ========================================================
    # COMPROBAR FOTO
    # ========================================================

    if not foto_original.photo:

        await message.reply_text(
            "⚠️ Solo puedes referenciar imágenes."
        )

        return


    # ========================================================
    # USUARIO QUE MANDÓ LA FOTO
    # ========================================================

    usuario = foto_original.from_user

    if not usuario:
        await message.reply_text(
            "❌ No se pudo identificar al usuario."
        )
        return

    user_id = str(usuario.id)

    if usuario.username:

        username = "@" + usuario.username

    else:

        username = usuario.first_name


    # ========================================================
    # HORA ESPAÑOLA
    # ========================================================

    hora = foto_original.date.astimezone(
        SPAIN_TZ
    ).strftime("%H:%M:%S")


    # ========================================================
    # BUSCAR FOTOS
    # ========================================================

    fotos = []

    album_id = foto_original.media_group_id


    # ========================================================
    # SI ES ÁLBUM
    # ========================================================

    if album_id:

        print(
            f"🔎 /refe pertenece al álbum {album_id}"
        )

        # Esperamos a que Telegram entregue
        # todas las fotos del álbum.
        for intento in range(10):

            await asyncio.sleep(0.5)

            if album_id in ALBUM_CACHE:

                fotos = ALBUM_CACHE[
                    album_id
                ]["photos"].copy()

                print(
                    f"🔎 Intento {intento + 1}: "
                    f"{len(fotos)} foto(s)"
                )

            # Si ya tenemos fotos y han pasado
            # al menos unos intentos, seguimos.
            if intento >= 3 and fotos:
                break


    # ========================================================
    # SI ES FOTO SOLA
    # ========================================================

    if not fotos:

        fotos = [
            foto_original.photo[-1].file_id
        ]

        print(
            "📷 Es una foto individual."
        )


    # ========================================================
    # MENSAJE
    # ========================================================

    mensaje = foto_original.caption

    # Si es álbum, el caption normalmente
    # está solamente en la primera foto.
    if not mensaje and album_id:

        album = ALBUM_CACHE.get(
            album_id
        )

        if album:

            mensaje = album.get(
                "caption"
            )


    if mensaje:

        mensaje = html.escape(
            mensaje
        )

    else:

        mensaje = "No hay mensaje"


    # ========================================================
    # SUMAR REFES
    #
    # 1 FOTO = 1
    # 8 FOTOS = 8
    # ========================================================

    cantidad = len(fotos)

    total_refes = sumar_refes(
        user_id,
        username,
        cantidad
    )

    print(
        f"🍒 {username}: "
        f"+{cantidad} refes | "
        f"TOTAL: {total_refes}"
    )


    # ========================================================
    # PLANTILLA
    # ========================================================

    plantilla = (
        "命         <b>𝐂𝐇𝐄𝐑𝐑𝐘'𝐒 𝐑𝐄𝐅𝐄𝐑𝐄𝐍𝐂𝐄𝐒.</b>\n"
        "\n"
        "︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶\n"
        f"୧   <b>𝘂𝘀𝘂𝗮𝗿𝗶𝗼</b>   :   "
        f"{html.escape(username)}\n"
        f"୧   <b>𝗶𝗱</b>   :   "
        f"{usuario.id}\n"
        f"୧   <b>𝗵𝗼𝗿𝗮</b>   :   "
        f"{hora}\n"
        f"୧   <b>𝗺𝗲𝗻𝘀𝗮𝗷𝗲</b>   :   "
        f"{mensaje}\n"
        f"୧   <b>𝗿𝗲𝗳𝗲𝘀</b>   :   "
        f"{total_refes}\n"
        "︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶"
    )


    # ========================================================
    # BOTONES
    # ========================================================

    botones = InlineKeyboardMarkup([
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
    # ENVIAR LAS FOTOS
    #
    # SI ES ÁLBUM:
    # FOTO 1
    # FOTO 2
    # FOTO 3
    # ...
    #
    # UNA POR UNA
    # ========================================================

    try:

        print(
            f"📤 Enviando {len(fotos)} foto(s)..."
        )

        for numero, photo_id in enumerate(
            fotos,
            start=1
        ):

            print(
                f"📤 Enviando foto "
                f"{numero}/{len(fotos)}"
            )

            await context.bot.send_photo(
                chat_id=DESTINATION_CHAT_ID,
                photo=photo_id,
                caption=plantilla,
                parse_mode="HTML",
                reply_markup=botones
            )

            await asyncio.sleep(0.4)


        print(
            "✅ REFERENCIA ENVIADA CORRECTAMENTE"
        )


        # Limpiar álbum
        if album_id:

            ALBUM_CACHE.pop(
                album_id,
                None
            )


    except Exception as e:

        print(
            f"❌ ERROR ENVIANDO FOTO: {e}"
        )

        await message.reply_text(
            f"❌ Error al enviar la referencia:\n{e}"
        )


# ============================================================
# INICIO
# ============================================================

def main():

    print(
        "================================"
    )

    print(
        "🍒 CHERRY'S REFES"
    )

    print(
        "🤖 Bot iniciándose..."
    )

    print(
        "================================"
    )


    if not BOT_TOKEN:

        print(
            "❌ NO EXISTE TELEGRAM_TOKEN"
        )

        return


    print(
        "✅ TELEGRAM_TOKEN encontrado"
    )


    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .build()
    )


    # ========================================================
    # MUY IMPORTANTE:
    # Este handler recibe las fotos de los álbumes.
    # ========================================================

    app.add_handler(
        MessageHandler(
            filters.PHOTO,
            recibir_fotos
        )
    )


    # ========================================================
    # /REFE
    # ========================================================

    app.add_handler(
        CommandHandler(
            "refe",
            refe
        )
    )


    print(
        "✅ Handlers cargados"
    )

    print(
        "🚀 BOT ONLINE"
    )


    app.run_polling(
        drop_pending_updates=True
    )


# ============================================================
# EJECUTAR
# ============================================================

if __name__ == "__main__":
    main()
