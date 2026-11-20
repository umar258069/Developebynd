import os
import io
import threading
import qrcode
from gtts import gTTS
from PIL import Image
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL = "@trustedbynd"

# 24/7 Keep-Alive Web Server (Render ke liye)
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Utility Bot is running 24/7!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)

user_mode = {}

# --- NECHE WALA CLEAN MENU ---
def bottom_menu():
    return ReplyKeyboardMarkup(
        [
            ["🎙️ Text to Voice", "📱 QR Code"],
            ["📄 Photo to PDF"]
        ],
        resize_keyboard=True
    )

# --- FORCE JOIN CHECK ---
async def is_user_joined(user_id: int, bot) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception:
        return False

def join_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Join Our Channel", url="https://t.me/trustedbynd")],
        [InlineKeyboardButton("✅ Joined / Check", callback_data="check_join")]
    ])

# --- START COMMAND ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_mode.pop(user_id, None)

    if not await is_user_joined(user_id, context.bot):
        await update.message.reply_text(
            "🔒 **Bot use karne ke liye pehle hamara channel join karein!**\n\nJoin karne ke baad neeche **Joined / Check** button dabayein.",
            parse_mode="Markdown",
            reply_markup=join_keyboard()
        )
        return

    await update.message.reply_text(
        "👋 **Welcome!**\n\nNeeche se koi bhi tool chunein:",
        parse_mode="Markdown",
        reply_markup=bottom_menu()
    )

# --- INLINE BUTTON HANDLER ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    if query.data == "check_join":
        if await is_user_joined(user_id, context.bot):
            await query.answer("✅ Verified!", show_alert=False)
            await query.message.delete()
            await context.bot.send_message(
                chat_id=user_id,
                text="🎉 **Thank you for joining!**\n\nNeeche se apna tool chunein:",
                parse_mode="Markdown",
                reply_markup=bottom_menu()
            )
        else:
            await query.answer("❌ Pehle hamara channel join karein!", show_alert=True)

# --- TEXT HANDLER ---
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if not await is_user_joined(user_id, context.bot):
        await update.message.reply_text(
            "🔒 **Pehle hamara channel join karein!**",
            parse_mode="Markdown",
            reply_markup=join_keyboard()
        )
        return

    # Menu selection
    if text == "🎙️ Text to Voice":
        user_mode[user_id] = "tts"
        await update.message.reply_text("🎙️ **Koi bhi Hindi ya English text bhejein**, main uski audio bana dunga:", parse_mode="Markdown")
        return

    elif text == "📱 QR Code":
        user_mode[user_id] = "qr"
        await update.message.reply_text("📱 **Koi bhi link, UPI ID ya text bhejein**, main uska QR Code bana dunga:", parse_mode="Markdown")
        return

    elif text == "📄 Photo to PDF":
        user_mode[user_id] = "pdf"
        await update.message.reply_text("📄 **Koi bhi photo bhejein**, main uski PDF bana kar de dunga:", parse_mode="Markdown")
        return

    # Tool execution
    mode = user_mode.get(user_id)

    if mode == "tts":
        wait = await update.message.reply_text("⏳ Audio ban rahi hai...")
        try:
            tts = gTTS(text=text[:1000], lang="hi")
            audio_io = io.BytesIO()
            tts.write_to_fp(audio_io)
            audio_io.seek(0)
            audio_io.name = "voice.mp3"
            await update.message.reply_audio(audio=audio_io, caption="✅ Ye lo aapki audio!")
            await wait.delete()
        except Exception:
            await wait.edit_text("⚠️ Audio banane mein error aaya, dubara try karein.")

    elif mode == "qr":
        wait = await update.message.reply_text("⏳ QR Code ban raha hai...")
        try:
            qr = qrcode.make(text)
            bio = io.BytesIO()
            qr.save(bio, format="PNG")
            bio.seek(0)
            await update.message.reply_photo(photo=bio, caption="✅ Ye lo aapka QR Code!")
            await wait.delete()
        except Exception:
            await wait.edit_text("⚠️ QR Code banane mein error aaya, dubara try karein.")

    else:
        await update.message.reply_text("👇 Pehle neeche se koi tool chunein:", reply_markup=bottom_menu())

# --- PHOTO HANDLER (PHOTO TO PDF) ---
async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not await is_user_joined(user_id, context.bot):
        await update.message.reply_text(
            "🔒 **Pehle hamara channel join karein!**",
            parse_mode="Markdown",
            reply_markup=join_keyboard()
        )
        return

    wait = await update.message.reply_text("⏳ PDF ban rahi hai...")
    try:
        photo_file = await update.message.photo[-1].get_file()
        img_bytes = await photo_file.download_as_bytearray()
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")

        pdf_io = io.BytesIO()
        img.save(pdf_io, format="PDF")
        pdf_io.seek(0)
        pdf_io.name = "document.pdf"

        await update.message.reply_document(document=pdf_io, caption="✅ Ye lo aapki PDF file!")
        await wait.delete()
    except Exception:
        await wait.edit_text("⚠️ PDF banane mein error aaya, dubara photo bhejein.")

def main():
    threading.Thread(target=run_web, daemon=True).start()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
            
