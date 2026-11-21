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
upload_category = {}
user_vid_idx = {}

# Category-wise saved videos
saved_videos = {
    "japanese": [],
    "desi": [],
    "hot": []
}

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
        [
            ["🇯🇵 Japanese", "🇮🇳 Desi", "🔥 Hot"],
            ["🎙️ Text to Voice", "📄 Photo to PDF"]
        ],
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

# --- COMMANDS ---
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
        "👋 **Welcome!**\n\nNeeche se koi bhi option chunein:",
        parse_mode="Markdown",
        reply_markup=bottom_menu()
    )

async def set_add_japanese(update: Update, context: ContextTypes.DEFAULT_TYPE):
    upload_category[update.effective_user.id] = "japanese"
    await update.message.reply_text("🇯🇵 **Japanese Upload Mode ON!**\nAb jo bhi videos bhejoge wo **Japanese** mein save hongi.", parse_mode="Markdown")

async def set_add_desi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    upload_category[update.effective_user.id] = "desi"
    await update.message.reply_text("🇮🇳 **Desi Upload Mode ON!**\nAb jo bhi videos bhejoge wo **Desi** mein save hongi.", parse_mode="Markdown")

async def set_add_hot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    upload_category[update.effective_user.id] = "hot"
    await update.message.reply_text("🔥 **Hot Upload Mode ON!**\nAb jo bhi videos bhejoge wo **Hot** mein save hongi.", parse_mode="Markdown")

async def clear_videos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for cat in saved_videos:
        saved_videos[cat].clear()
    user_vid_idx.clear()
    await update.message.reply_text("🗑️ Saari categories ki videos delete kar di gayi hain!")

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
                text="🎉 **Thank you for joining!**\n\nNeeche se apna option chunein:",
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
                f"✅ **Selected Character:** {v_name}\n\nAb apna **text bhejein**, main isi awaaz mein audio bana dunga!",
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

    # Video Category Buttons
    cat_map = {
        "🇯🇵 Japanese": "japanese",
        "🇮🇳 Desi": "desi",
        "🔥 Hot": "hot"
    }

    if text in cat_map:
        cat = cat_map[text]
        vids = saved_videos[cat]
        if not vids:
            await update.message.reply_text(f"⚠️ Abhi **{text}** mein koi video nahi hai!", parse_mode="Markdown")
            return
        key = (user_id, cat)
        idx = user_vid_idx.get(key, 0)
        if idx >= len(vids):
            idx = 0
        vid_id, caption = vids[idx]
        user_vid_idx[key] = idx + 1
        await update.message.reply_video(video=vid_id, caption=caption)
        return

    elif text == "🎙️ Text to Voice":
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
        await update.message.reply_text("👇 Pehle neeche se koi option chunein:", reply_markup=bottom_menu())

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

# --- VIDEO HANDLER (SAVE TO SELECTED CATEGORY) ---
async def video_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cat = upload_category.get(user_id)

    if not cat:
        await update.message.reply_text(
            "👇 Pehle category select karein:\n\n`/add_japanese`\n`/add_desi`\n`/add_hot`\n\nUske baad video bhejein!",
            parse_mode="Markdown"
        )
        return

    video = update.message.video
    caption = update.message.caption or ""
    saved_videos[cat].append((video.file_id, caption))
    await update.message.reply_text(
        f"✅ **{cat.upper()}** mein video save ho gayi! (Total: {len(saved_videos[cat])})",
        parse_mode="Markdown"
    )

def main():
    threading.Thread(target=run_web, daemon=True).start()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add_japanese", set_add_japanese))
    app.add_handler(CommandHandler("add_desi", set_add_desi))
    app.add_handler(CommandHandler("add_hot", set_add_hot))
    app.add_handler(CommandHandler("clearvideos", clear_videos))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app.add_handler(MessageHandler(filters.VIDEO, video_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
    
