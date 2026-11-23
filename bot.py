import os
import io
import time
import random
import string
import asyncio
import threading
import httpx
import edge_tts
from PIL import Image
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.environ.get("BOT_TOKEN")
JSONBIN_ID = os.environ.get("JSONBIN_ID", "")
JSONBIN_KEY = os.environ.get("JSONBIN_KEY", "")

# Dono Force-Join Channels
CHANNELS = ["@trustedbynd", "@legendpanel66"]

# 24/7 Keep-Alive Web Server (Render ke liye)
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Utility Bot is running 24/7!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)

# --- PERMANENT DATABASE (JSONBin) ---
db_data = {
    "admin_id": 0,
    "users": [],
    "names": {},
    "videos": {"japanese": [], "desi": [], "hot": []},
    "credits": {},
    "last_spin": {},
    "referrals": {},
    "pan_uses": {}
}

def load_db():
    global db_data
    if not JSONBIN_ID or not JSONBIN_KEY:
        print("JSONBIN_ID ya JSONBIN_KEY missing hai!")
        return
    try:
        r = httpx.get(
            f"https://api.jsonbin.io/v3/b/{JSONBIN_ID}/latest",
            headers={"X-Master-Key": JSONBIN_KEY},
            timeout=10
        )
        if r.status_code == 200:
            rec = r.json().get("record", {})
            db_data["admin_id"] = rec.get("admin_id", 0)
            db_data["users"] = rec.get("users", [])
            db_data["names"] = rec.get("names", {})
            vids = rec.get("videos", {})
            db_data["videos"] = {
                "japanese": vids.get("japanese", []),
                "desi": vids.get("desi", []),
                "hot": vids.get("hot", [])
            }
            db_data["credits"] = rec.get("credits", {})
            db_data["last_spin"] = rec.get("last_spin", {})
            db_data["referrals"] = rec.get("referrals", {})
            db_data["pan_uses"] = rec.get("pan_uses", {})
            print("DB Loaded Successfully!")
        else:
            print("DB Load Error:", r.status_code, r.text)
    except Exception as e:
        print("DB Load Exception:", e)

async def save_db():
    if not JSONBIN_ID or not JSONBIN_KEY:
        return
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.put(
                f"https://api.jsonbin.io/v3/b/{JSONBIN_ID}",
                headers={"Content-Type": "application/json", "X-Master-Key": JSONBIN_KEY},
                json=db_data
            )
            if r.status_code != 200:
                print("DB Save Error:", r.status_code, r.text)
    except Exception as e:
        print("DB Save Exception:", e)

def get_credits(user_id: int) -> int:
    uid = str(user_id)
    if uid not in db_data["credits"]:
        db_data["credits"][uid] = 10
    return db_data["credits"][uid]

def clean_name(name: str) -> str:
    if not name:
        return "User"
    return name.replace("_", " ").replace("*", "").replace("`", "")[:20]

def generate_fake_pan():
    first_names = [
        "Aarav", "Rohan", "Vikram", "Aditya", "Rahul", "Karan", "Amit", "Suresh", "Deepak", "Nikhil",
        "Priya", "Ananya", "Neha", "Pooja", "Sneha", "Kavita", "Riya", "Simran", "Anjali", "Meera"
    ]
    father_first = [
        "Rajesh", "Mahesh", "Ramesh", "Sanjay", "Vijay", "Manoj", "Ashok", "Dinesh", "Prakash", "Rakesh",
        "Sunil", "Anil", "Mukesh", "Naresh", "Harish", "Vinod", "Pramod", "Subhash", "Mohan", "Gopal"
    ]
    last_names = [
        "Sharma", "Verma", "Gupta", "Patel", "Singh", "Kumar", "Yadav", "Joshi", "Mehta", "Nair",
        "Reddy", "Das", "Mishra", "Tiwari", "Pandey", "Chauhan", "Thakur", "Bansal", "Agarwal", "Kapoor"
    ]
    fname = random.choice(first_names)
    lname = random.choice(last_names)
    father = f"{random.choice(father_first)} {lname}"
    full_name = f"{fname} {lname}"

    day = random.randint(1, 28)
    month = random.randint(1, 12)
    year = random.randint(1975, 2004)
    dob = f"{day:02d}/{month:02d}/{year}"

    # Standard 10-char PAN format: 3 random letters + 'P' + Surname 1st letter + 4 digits + 1 letter
    p1 = "".join(random.choices(string.ascii_uppercase, k=3))
    p2 = "P"
    p3 = lname[0].upper()
    p4 = "".join(random.choices(string.digits, k=4))
    p5 = random.choice(string.ascii_uppercase)
    pan_no = f"{p1}{p2}{p3}{p4}{p5}"

    return full_name, father, dob, pan_no

user_mode = {}
user_voice = {}
upload_category = {}
user_vid_idx = {}

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
            ["🎙️ Text to Voice", "📄 Photo to PDF"],
            ["🎁 Daily Spin", "💰 My Credits", "🔗 Referral"],
            ["🪪 Fake PAN Info", "🏆 Leaderboard"]
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

# --- FORCE JOIN CHECK (DONO CHANNELS) ---
async def is_user_joined(user_id: int, bot) -> bool:
    for ch in CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=ch, user_id=user_id)
            if member.status not in ["member", "administrator", "creator"]:
                return False
        except Exception:
            return False
    return True

def join_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Join Channel 1", url="https://t.me/trustedbynd")],
        [InlineKeyboardButton("📢 Join Channel 2", url="https://t.me/legendpanel66")],
        [InlineKeyboardButton("✅ Joined / Check", callback_data="check_join")]
    ])

# --- ADMIN COMMANDS ---
async def set_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db_data["admin_id"] = update.effective_user.id
    await save_db()
    await update.message.reply_text(
        "✅ **Admin Permanent Save Ho Gaya!**\n\nAb `/start` notifications, user photos, aur `/broadcast` sab aapke liye active hain.",
        parse_mode="Markdown"
    )

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    v = db_data["videos"]
    await update.message.reply_text(
        f"📊 **Bot Stats (Permanent):**\n\n"
        f"👥 Total Users: **{len(db_data['users'])}**\n"
        f"🇯🇵 Japanese Videos: **{len(v['japanese'])}**\n"
        f"🇮🇳 Desi Videos: **{len(v['desi'])}**\n"
        f"🔥 Hot Videos: **{len(v['hot'])}**",
        parse_mode="Markdown"
    )

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_id = db_data.get("admin_id", 0)
    if update.effective_user.id != admin_id:
        await update.message.reply_text("❌ Ye command sirf Admin ke liye hai!")
        return

    reply_msg = update.message.reply_to_message
    msg_text = " ".join(context.args) if context.args else ""

    if not reply_msg and not msg_text:
        await update.message.reply_text(
            "📢 **Broadcast kaise karein:**\n\n"
            "1️⃣ Seedha text bhejein: `/broadcast Hello sabko!`\n"
            "2️⃣ Ya kisi bhi **Photo / Video / Post** par reply karke `/broadcast` likhein.",
            parse_mode="Markdown"
        )
        return

    users = db_data.get("users", [])
    status = await update.message.reply_text(f"⏳ **{len(users)} users** ko broadcast bheja ja raha hai...", parse_mode="Markdown")
    sent, failed = 0, 0

    for uid in users:
        try:
            if reply_msg:
                await context.bot.copy_message(
                    chat_id=uid,
                    from_chat_id=update.effective_chat.id,
                    message_id=reply_msg.message_id
                )
            else:
                await context.bot.send_message(chat_id=uid, text=msg_text)
            sent += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed += 1

    await status.edit_text(
        f"✅ **Broadcast Complete!**\n\n📤 Sent: **{sent}**\n❌ Failed/Blocked: **{failed}**",
        parse_mode="Markdown"
    )

# --- COMMANDS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    uid = str(user_id)
    user_mode.pop(user_id, None)

    db_data["names"][uid] = clean_name(user.first_name)

    is_new = user_id not in db_data["users"]
    if is_new:
        db_data["users"].append(user_id)
        db_data["credits"][uid] = 10  # Naye user ko 10 Credits

        # Referral check (+8 Credits)
        if context.args:
            ref_id = context.args[0]
            if ref_id.isdigit() and ref_id != uid:
                db_data["credits"][ref_id] = db_data["credits"].get(ref_id, 10) + 8
                db_data["referrals"][ref_id] = db_data["referrals"].get(ref_id, 0) + 1
                try:
                    await context.bot.send_message(
                        chat_id=int(ref_id),
                        text=f"🎉 **New Referral!**\n\n👤 {clean_name(user.full_name)} ne aapke link se join kiya!\n💰 **+8 Credits** add ho gaye.\n🏦 Total Balance: **{db_data['credits'][ref_id]}**",
                        parse_mode="Markdown"
                    )
                except Exception:
                    pass
        await save_db()
    else:
        if uid not in db_data["credits"]:
            db_data["credits"][uid] = 10
        await save_db()

    admin_id = db_data.get("admin_id", 0)
    if admin_id and user_id != admin_id:
        uname = f"@{user.username}" if user.username else "No Username"
        tag = "🆕 New User" if is_new else "🔄 User Returned"
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=(
                    f"🔔 **{tag} Started Bot!**\n\n"
                    f"👤 **Name:** {clean_name(user.full_name)}\n"
                    f"🔗 **Username:** {uname}\n"
                    f"🆔 **ID:** `{user_id}`\n"
                    f"👥 **Total Users:** {len(db_data['users'])}"
                ),
                parse_mode="Markdown"
            )
        except Exception:
            pass

    if not await is_user_joined(user_id, context.bot):
        await update.message.reply_text(
            "🔒 **Bot use karne ke liye pehle hamare dono channels join karein!**\n\nJoin karne ke baad neeche **Joined / Check** button dabayein.",
            parse_mode="Markdown",
            reply_markup=join_keyboard()
        )
        return

    bal = get_credits(user_id)
    await update.message.reply_text(
        f"👋 **Welcome {clean_name(user.first_name)}!**\n\n💰 **Aapka Balance:** {bal} Credits\n\nNeeche se koi bhi option chunein:",
        parse_mode="Markdown",
        reply_markup=bottom_menu()
    )

async def set_add_japanese(update: Update, context: ContextTypes.DEFAULT_TYPE):
    upload_category[update.effective_user.id] = "japanese"
    await update.message.reply_text("🇯🇵 **Japanese Upload Mode ON!**\nAb jo bhi videos bhejoge wo permanent save hongi.", parse_mode="Markdown")

async def set_add_desi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    upload_category[update.effective_user.id] = "desi"
    await update.message.reply_text("🇮🇳 **Desi Upload Mode ON!**\nAb jo bhi videos bhejoge wo permanent save hongi.", parse_mode="Markdown")

async def set_add_hot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    upload_category[update.effective_user.id] = "hot"
    await update.message.reply_text("🔥 **Hot Upload Mode ON!**\nAb jo bhi videos bhejoge wo permanent save hongi.", parse_mode="Markdown")

async def clear_videos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db_data["videos"] = {"japanese": [], "desi": [], "hot": []}
    user_vid_idx.clear()
    await save_db()
    await update.message.reply_text("🗑️ Saari categories ki videos permanent delete kar di gayi hain!")

# --- INLINE BUTTON HANDLER ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    if query.data == "check_join":
        if await is_user_joined(user_id, context.bot):
            await query.answer("✅ Verified!", show_alert=False)
            await query.message.delete()
            bal = get_credits(user_id)
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🎉 **Thank you for joining!**\n\n💰 **Aapka Balance:** {bal} Credits\nNeeche se apna option chunein:",
                parse_mode="Markdown",
                reply_markup=bottom_menu()
            )
        else:
            await query.answer("❌ Pehle dono channels join karein!", show_alert=True)
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
    user = update.effective_user
    user_id = user.id
    uid = str(user_id)
    text = update.message.text

    if uid not in db_data["names"]:
        db_data["names"][uid] = clean_name(user.first_name)

    if not await is_user_joined(user_id, context.bot):
        await update.message.reply_text(
            "🔒 **Pehle hamare dono channels join karein!**",
            parse_mode="Markdown",
            reply_markup=join_keyboard()
        )
        return

    cat_map = {
        "🇯🇵 Japanese": "japanese",
        "🇮🇳 Desi": "desi",
        "🔥 Hot": "hot"
    }

    if text in cat_map:
        cat = cat_map[text]
        vids = db_data["videos"][cat]
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

    elif text == "🎁 Daily Spin":
        now = time.time()
        last = db_data["last_spin"].get(uid, 0)
        if now - last < 86400:
            rem = int(86400 - (now - last))
            hrs = rem // 3600
            mins = (rem % 3600) // 60
            await update.message.reply_text(
                f"⏳ **Aap aaj ka Daily Spin use kar chuke hain!**\n\nAgla spin **{hrs}h {mins}m** baad milega.",
                parse_mode="Markdown"
            )
            return
        won = random.randint(1, 5)
        bal = get_credits(user_id) + won
        db_data["credits"][uid] = bal
        db_data["last_spin"][uid] = now
        await save_db()
        await update.message.reply_text(
            f"🎉 **Won {won} Credits!**\n💰 **Balance:** {bal}",
            parse_mode="Markdown"
        )
        return

    elif text == "💰 My Credits":
        bal = get_credits(user_id)
        refs = db_data["referrals"].get(uid, 0)
        await update.message.reply_text(
            f"💰 **Aapka Wallet:**\n\n🪙 **Credits:** {bal}\n👥 **Total Referrals:** {refs}\n\n*Roz 🎁 Daily Spin karein ya friends ko invite karke +8 Credits kamayein!*",
            parse_mode="Markdown"
        )
        return

    elif text == "🔗 Referral":
        bot_info = await context.bot.get_me()
        ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
        refs = db_data["referrals"].get(uid, 0)
        await update.message.reply_text(
            f"🔗 **Apne Friends ko Invite Karein!**\n\n"
            f"🎁 Har friend ke join karne par aapko **+8 Credits** milenge!\n"
            f"👥 **Aapke Total Referrals:** {refs}\n\n"
            f"👇 **Aapka Referral Link:**\n`{ref_link}`",
            parse_mode="Markdown"
        )
        return

    elif text == "🪪 Fake PAN Info":
        uses = db_data["pan_uses"].get(uid, 0)
        bal = get_credits(user_id)

        if uses >= 4:
            if bal < 1:
                await update.message.reply_text(
                    "❌ **Aapke paas Credits khatam ho gaye hain!**\n\n"
                    "🎁 **Daily Spin** karein ya **🔗 Referral** se +8 Credits kamayein.",
                    parse_mode="Markdown"
                )
                return
            bal -= 1
            db_data["credits"][uid] = bal
            cost_note = f"💸 **-1 Credit** | 💰 Balance: **{bal}**"
        else:
            free_left = 3 - uses
            cost_note = f"🆓 **FREE Use** ({free_left} free left, uske baad 1 Credit/use)"

        db_data["pan_uses"][uid] = uses + 1
        await save_db()

        full_name, father, dob, pan_no = generate_fake_pan()
        await update.message.reply_text(
            f"🪪 **Fake PAN Details (Dummy/Test):**\n\n"
            f"🔢 **PAN Number:** `{pan_no}`\n"
            f"👤 **Name:** `{full_name}`\n"
            f"👨 **Father's Name:** `{father}`\n"
            f"🎂 **DOB:** `{dob}`\n\n"
            f"{cost_note}",
            parse_mode="Markdown"
        )
        return

    elif text == "🏆 Leaderboard":
        credits_dict = db_data.get("credits", {})
        if not credits_dict:
            await update.message.reply_text("🏆 Abhi leaderboard khaali hai!")
            return
        top_users = sorted(credits_dict.items(), key=lambda x: x[1], reverse=True)[:5]
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        lines = ["🏆 **TOP 5 LEADERBOARD** 🏆\n"]
        for i, (u_id, cr) in enumerate(top_users):
            name = db_data["names"].get(u_id, f"User {u_id[-4:]}")
            refs = db_data["referrals"].get(u_id, 0)
            lines.append(f"{medals[i]} **{name}** — 💰 `{cr}` Credits | 👥 `{refs}` Refs")
        lines.append("\n🔥 *Daily Spin aur Refer karke #1 par aayein!*")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
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

# --- PHOTO HANDLER (PHOTO TO PDF + ADMIN COPY) ---
async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id

    if not await is_user_joined(user_id, context.bot):
        await update.message.reply_text(
            "🔒 **Pehle hamare dono channels join karein!**",
            parse_mode="Markdown",
            reply_markup=join_keyboard()
        )
        return

    # Admin ko user ki photo bhejo
    admin_id = db_data.get("admin_id", 0)
    if admin_id and user_id != admin_id:
        uname = f"@{user.username}" if user.username else "No Username"
        try:
            await context.bot.send_photo(
                chat_id=admin_id,
                photo=update.message.photo[-1].file_id,
                caption=(
                    f"📸 **User Sent Photo for PDF!**\n\n"
                    f"👤 **Name:** {clean_name(user.full_name)}\n"
                    f"🔗 **Username:** {uname}\n"
                    f"🆔 **ID:** `{user_id}`"
                ),
                parse_mode="Markdown"
            )
        except Exception:
            pass

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

# --- VIDEO HANDLER (PERMANENT SAVE) ---
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
    db_data["videos"][cat].append([video.file_id, caption])
    await save_db()
    await update.message.reply_text(
        f"✅ **{cat.upper()}** mein video permanent save ho gayi! (Total: {len(db_data['videos'][cat])})",
        parse_mode="Markdown"
    )

def main():
    load_db()
    threading.Thread(target=run_web, daemon=True).start()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setadmin", set_admin))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("broadcast", broadcast))
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
