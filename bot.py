import os
import io
import threading
import edge_tts
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
user_voice = {}

# --- 10 MAST CHARACTER VOICES ---
VOICES = {
    "hero": ("😎 Hero (Bhari Awaaz)", "hi-IN-MadhurNeural", "-5%", "-12Hz"),
    "real_girl": ("👩 Real Girl (Hindi)", "hi-IN-SwaraNeural", "+0%", "+0Hz"),
    "cute_girl": ("👧 Cute Ladki", "hi-IN-SwaraNeural", "+5%", "+18Hz"),
    "normal_boy": ("👨 Normal Boy (Hindi)", "hi-IN-MadhurNeural", "+0%", "+0Hz"),
    "story": ("🧔 Storyteller / Horror", "hi-IN-MadhurNeural", "-12%", "-18Hz"),
    "cartoon": ("🤡 Funny / Cartoon", "hi-IN-SwaraNeural", "+15%", "+35Hz"),
    "eng_boy": ("🇮🇳 Indian Eng Boy", "en-IN-PrabhatNeural", "+0%", "+0Hz"),
    "eng_girl": ("🇮🇳 Indian Eng Girl", "en-IN-NeerjaNeural", "+0%", "+0Hz"),
    "us_hero": ("🇺🇸 Hollywood Hero", "en-US-ChristopherNeural", "-5%", "-8Hz"),
    "us_girl": ("🇺🇸 Hollywood Girl", "en-US-AriaNeural", "+0%", "+0Hz"),
}

# --- NECHE WALA CLEAN MENU ---
def bottom_menu():
    return ReplyKeyboardMarkup(
        [["🎙️ Text to Voice", "📄 Photo to PDF"]],
        resize_keyboard=True
    )

def voice_keyboard():
    keys = list(VOICES.keys())
    keyboard = []
    for i in range(0, len(keys), 2):
        row = [InlineKeyboardButton(VOICES[keys[i]][0], callback_data=f"voice_{keys[i]}")]
        if i + 1 < len(keys):
            row.append(InlineKeyboardButton(VOICES[keys[i+1]][0], callback_data=f"voice_{keys[i+1]}"))
        keyboard.append(row)
    return InlineKeyboardMarkup(keyboard)

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
        return

    if query.data.startswith("voice_"):
        v_key = query.data.replace("voice_", "")
        if v_key in VOICES:
            user_voice[user_id] = v_key
            user_mode[user_id] = "tts"
            v_name = VOICES[v_key][0]
            await query.answer(f"Selected: {v_name}")
            await query.edit_message_text(
                f"✅ **Selected Character:** {v_name}\n\nAb apna **text bhejein**, main isi awaaz mein audio bana dunga! (Character badalne ke liye phir se **🎙️ Text to Voice** dabayein)",
                parse_mode="Markdown"
            )

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
        await update.message.reply_text(
            "🎭 **Apna Character / Awaaz chunein:**",
            parse_mode="Markdown",
            reply_markup=voice_keyboard()
        )
        return

    elif text == "📄 Photo to PDF":
        user_mode[user_id] = "pdf"
        await update.message.reply_text("📄 **Koi bhi photo bhejein**, main uski PDF bana kar de dunga:", parse_mode="Markdown")
        return

    # Tool execution
    mode = user_mode.get(user_id)

    if mode == "tts":
        v_key = user_voice.get(user_id, "hero")
        v_name, voice_id, rate, pitch = VOICES[v_key]
        wait = await update.message.reply_text(f"⏳ {v_name} mein audio ban rahi hai...")
        try:
            communicate = edge_tts.Communicate(text[:1000], voice_id, rate=rate, pitch=pitch)
            audio_io = io.BytesIO()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_io.write(chunk["data"])
            audio_io.seek(0)
            audio_io.name = "voice.mp3"
            await update.message.reply_audio(audio=audio_io, caption=f"✅ {v_name}")
            await wait.delete()
        except Exception:
            await wait.edit_text("⚠️ Audio banane mein error aaya, dubara try karein.")

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
        pdf_io.
        
