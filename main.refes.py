# main.py
import os
import html
import json
import logging
import threading
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ---- Logging ----
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger(__name__)

# ---- Config desde entorno ----
BOT_TOKEN = os.getenv("BOT_TOKEN")
DESTINATION_CHAT_ID = os.getenv("DESTINATION_CHAT_ID")  # puede ser string o entero
DB_FILE = os.getenv("DB_FILE", "refes.json")  # nombre del archivo JSON (por defecto refes.json)

if not BOT_TOKEN:
    log.error("❌ No se encontró BOT_TOKEN en las variables de entorno. Añádelo y reinicia.")
    raise SystemExit(1)

if not DESTINATION_CHAT_ID:
    log.error("❌ No se encontró DESTINATION_CHAT_ID en las variables de entorno. Añádelo y reinicia.")
    raise SystemExit(1)

try:
    # intentar convertir a int si viene como string
    DESTINATION_CHAT_ID = int(DESTINATION_CHAT_ID)
except Exception:
    # si no es convertible, dejar como está (puede ser canal con @username)
    pass

# Lock para evitar accesos concurrentes al archivo
FILE_LOCK = threading.Lock()

# ---- Helpers ----
def mes_actual():
    return datetime.now().strftime("%Y-%m")

def cargar_datos():
    """Carga el JSON del disco de forma segura (devuelve dict)."""
    with FILE_LOCK:
        if not os.path.exists(DB_FILE):
            return {}
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            log.warning("El archivo JSON está corrupto o vacío. Se inicializa uno nuevo.")
            return {}
        except Exception as e:
            log.exception("Error leyendo el archivo JSON: %s", e)
            return {}

def guardar_datos(data):
    """Guarda el JSON en disco de forma segura."""
    with FILE_LOCK:
        try:
            with open(DB_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            log.exception("Error guardando datos en JSON: %s", e)

# ---- Comandos ----
async def refe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /refe. Debe responderse a una imagen."""
    try:
        await update.message.reply_text("✅ 𝗖𝗼𝗺𝗮𝗻𝗱𝗼 𝗿𝗲𝗰𝗶𝗯𝗶𝗱𝗼!")
    except Exception:
        # si no puede responder (por permisos) seguimos intentando el resto
        pass

    if not update.message.reply_to_message:
        await update.message.reply_text("❗ Por favor, responde a una imagen para referenciarla.")
        return

    replied = update.message.reply_to_message
    if not replied.photo:
        await update.message.reply_text("⚠️ Solo se permiten imágenes. Por favor, responde a una imagen.")
        return

    # Autor de la imagen (no el que usa /refe)
    img_user = replied.from_user
    img_user_id = str(img_user.id)
    img_username = img_user.username or img_user.first_name

    # Actualizar conteo
    data = cargar_datos()
    mes = mes_actual()
    if mes not in data:
        data[mes] = {}

    if img_user_id not in data[mes]:
        data[mes][img_user_id] = {"username": img_username, "count": 0}

    data[mes][img_user_id]["count"] += 1
    data[mes][img_user_id]["username"] = img_username
    guardar_datos(data)

    # Preparar mensaje a enviar al canal
    user = img_username
    user_id = img_user.id
    time = replied.date.strftime('%I:%M:%S %p')
    original_message = replied.caption or ""
    original_message = html.escape(original_message)
    photo_file = replied.photo[-1].file_id

    formatted_message = (
        f"🍒 <a href='https://t.me/+FmV2e23GHJA3NjE0'>𝗖𝗛𝗘𝗥𝗥𝗬'𝗦 𝗥𝗘𝗙𝗘𝗥𝗘𝗡𝗖𝗜𝗔𝗦</a>\n"
        f"︶︶︶︶︶︶︶︶︶︶︶︶︶︶\n"
        f"<a href='https://x.com/cheerryspriv'>✮</a> 𝗨𝘀𝘂𝗮𝗿𝗶𝗼 → @{user}\n"
        f"<a href='https://x.com/cheerryspriv'>✮</a> 𝗜𝗗 → {user_id}\n"
        f"<a href='https://x.com/cheerryspriv'>✮</a> 𝗛𝗼𝗿𝗮 → {time}\n"
        f"<a href='https://t.me/+FmV2e23GHJA3NjE0'>✮</a> 𝗠𝗲𝗻𝘀𝗮𝗷𝗲 → {original_message}\n"
        f"- - - - - - - - - - - - - - - - - - - - - - - - - -"
    )

    buttons = [
        [InlineKeyboardButton("𝙄𝙉𝙁𝙊𝙍𝙈𝘼𝙏𝙄𝙊𝙉", url="https://x.com/cheerryspriv"),
         InlineKeyboardButton("𝙊𝙒𝙉𝙀𝙍", url="https://t.me/zilbato")]
    ]
    keyboard = InlineKeyboardMarkup(buttons)

    try:
        await context.bot.send_photo(
            chat_id=DESTINATION_CHAT_ID,
            photo=photo_file,
            caption=formatted_message,
            parse_mode="HTML",
            reply_markup=keyboard
        )
        log.info("Imagen reenviada al canal %s (autor=%s)", DESTINATION_CHAT_ID, user)
    except Exception as e:
        log.exception("Error al enviar la foto al canal: %s", e)
        await update.message.reply_text("❌ Error al enviar al canal.")

async def toprefe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = cargar_datos()
    mes = mes_actual()

    if mes not in data or not data[mes]:
        await update.message.reply_text("¡Aún no hay referencias este mes!")
        return

    top = sorted(data[mes].values(), key=lambda x: x["count"], reverse=True)
    mensaje = f"🏆 <b>𝗧𝗢𝗣 𝗥𝗘𝗙𝗘𝗥𝗘𝗡𝗖𝗜𝗔𝗦 - {mes}</b>\n\n"
    for i, user in enumerate(top[:10], 1):
        username = user.get("username", "desconocido")
        mensaje += f"{i}. @{username}: {user.get('count', 0)} 𝗋𝖾𝖿𝖾𝗌\n"

    await update.message.reply_text(mensaje, parse_mode="HTML")

# ---- Main ----
def main() -> None:
    log.info("Iniciando bot de referencias...")
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("refe", refe))
    app.add_handler(CommandHandler("toprefe", toprefe))

    log.info("Bot listo. Ejecutando polling...")
    app.run_polling()

if __name__ == "__main__":
    main()
