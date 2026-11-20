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
            await query.answer("❌ Pehle hamara channel join karein
                               
