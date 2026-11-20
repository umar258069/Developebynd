import os
import re
import random
import string
import asyncio
import threading
import httpx
from bs4 import BeautifulSoup
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL = "@trustedbynd"

# 24/7 Keep-Alive Web Server (Render ke liye)
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Bot is running 24/7!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)

user_mails = {}
user_sms_tasks = {}

MAIL_API = "https://api.mail.tm"
SMS_BASE_URL = "https://receive-smss.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# --- NECHE WALA CLEAN MENU (Swiggy Bot jaisa) ---
def bottom_menu():
    return ReplyKeyboardMarkup(
        [["📧 Temp Mail", "📱 New Number"]],
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

# --- TEMP MAIL (AUTO OTP) ---
async def create_temp_mail():
    async with httpx.AsyncClient(timeout=15) as client:
        dom_res = await client.get(f"{MAIL_API}/domains")
        domains = dom_res.json().get("hydra:member", [])
        if not domains:
            return None, None
        domain = domains[0]["domain"]

        username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        email = f"{username}@{domain}"
        password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))

        acc_res = await client.post(f"{MAIL_API}/accounts", json={"address": email, "password": password})
        if acc_res.status_code not in (200, 201):
            return None, None

        tok_res = await client.post(f"{MAIL_API}/token", json={"address": email, "password": password})
        token = tok_res.json().get("token")
        return email, token

async def auto_check_inbox(user_id: int, app_bot):
    for _ in range(180):
        await asyncio.sleep(10)
        data = user_mails.get(user_id)
        if not data:
            break
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                headers = {"Authorization": f"Bearer {data['token']}"}
                res = await client.get(f"{MAIL_API}/messages", headers=headers)
                if res.status_code != 200:
                    continue

                messages = res.json().get("hydra:member", [])
                for msg in messages:
                    msg_id = msg["id"]
                    if msg_id not in data["seen_ids"]:
                        data["seen_ids"].add(msg_id)
                        full_res = await client.get(f"{MAIL_API}/messages/{msg_id}", headers=headers)
                        full_msg = full_res.json()

                        sender = full_msg.get("from", {}).get("address", "Unknown")
                        subject = full_msg.get("subject", "No Subject")
                        body = full_msg.get("text", "") or "No text content"
                        if len(body) > 1500:
                            body = body[:1500] + "..."

                        otp_match = re.search(r'\b\d{4,8}\b', f"{subject} {body}")
                        otp_line = f"🔑 **OTP:** `{otp_match.group(0)}`\n\n" if otp_match else ""

                        text = (
                            f"📩 **New Mail OTP!**\n\n"
                            f"{otp_line}"
                            f"📧 **To:** `{data['email']}`\n"
                            f"👤 **From:** `{sender}`\n"
                            f"📝 **Message:**\n{body}"
                        )
                        await app_bot.send_message(chat_id=user_id, text=text, parse_mode="Markdown")
        except Exception:
            continue

# --- FREE SMS NUMBERS (AUTO OTP) ---
async def fetch_free_numbers():
    numbers = []
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=15, follow_redirects=True) as client:
            res = await client.get(SMS_BASE_URL)
            if res.status_code != 200:
                return []
            soup = BeautifulSoup(res.text, "html.parser")
            seen = set()
            for a in soup.find_all("a", href=True):
                match = re.search(r"/sms/(\d+)/?", a["href"])
                if match:
                    num = match.group(1)
                    if num not in seen and len(num) >= 10:
                        seen.add(num)
                        numbers.append(num)
    except Exception:
        return []
    return numbers

async def fetch_sms_messages(number: str):
    msgs = []
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=15, follow_redirects=True) as client:
            res = await client.get(f"{SMS_BASE_URL}/sms/{number}/")
            if res.status_code != 200:
                return []
            soup = BeautifulSoup(res.text, "html.parser")
            rows = soup.select("div.row.message_details")
            for row in rows[:5]:
                sender = row.select_one("div.col-md-3.senderr")
                msg_text = row.select_one("div.col-md-6.msgg")
                s_txt = sender.get_text(strip=True).replace("Sender", "") if sender else "Unknown"
                m_txt = msg_text.get_text(strip=True).replace("Message", "") if msg_text else ""
                if m_txt:
                    msgs.append((s_txt, m_txt))
    except Exception:
        return []
    return msgs

async def auto_check_sms(user_id: int, number: str, seen_msgs: set, app_bot):
    for _ in range(30):
        await asyncio.sleep(10)
        try:
            msgs = await fetch_sms_messages(number)
            for sender, m_txt in msgs:
                if m_txt not in seen_msgs:
                    seen_msgs.add(m_txt)
                    otp_match = re.search(r'\b\d{4,8}\b', m_txt)
                    otp_line = f"🔑 **OTP:** `{otp_match.group(0)}`\n\n" if otp_match else ""
                    text = (
                        f"📩 **New SMS OTP!**\n\n"
                        f"{otp_line}"
                        f"📱 **Number:** `+{number}`\n"
                        f"👤 **From:** {sender}\n"
                        f"💬 **Message:** `{m_txt}`"
                    )
                    await app_bot.send_message(chat_id=user_id, text=text, parse_mode="Markdown")
        except Exception:
            continue

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await is_user_joined(user_id, context.bot):
        await update.message.reply_text(
            "🔒 **Bot use karne ke liye pehle hamara channel join karein!**\n\nJoin karne ke baad neeche **Joined / Check** button dabayein.",
            parse_mode="Markdown",
            reply_markup=join_keyboard()
        )
        return

    await update.message.reply_text(
        "👋 **Welcome!**\n\nNeeche se **📧 Temp Mail** ya **📱 New Number** dabayein — OTP seedha screen par aayega:",
        parse_mode="Markdown",
        reply_markup=bottom_menu()
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    if query.data == "check_join":
        if await is_user_joined(user_id, context.bot):
            await query.answer("✅ Verified!", show_alert=False)
            await query.message.delete()
            await context.bot.send_message(
                chat_id=user_id,
                text="🎉 **Thank you for joining!**\n\nNeeche se **📧 Temp Mail** ya **📱 New Number** dabayein:",
                parse_mode="Markdown",
                reply_markup=bottom_menu()
            )
        else:
            await query.answer("❌ Pehle hamara channel join karein!", show_alert=True)

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

    if text == "📧 Temp Mail":
        wait = await update.message.reply_text("⏳ Email ban raha hai...")
        if user_id in user_mails and user_mails[user_id].get("task"):
            user_mails[user_id]["task"].cancel()

        email, token = await create_temp_mail()
        if not email or not token:
            await wait.edit_text("⚠️ Server busy hai, 5 second baad dubara dabayein.")
            return

        task = asyncio.create_task(auto_check_inbox(user_id, context.bot))
        user_mails[user_id] = {"email": email, "token": token, "seen_ids": set(), "task": task}

        await wait.edit_text(
            f"📧 **Temp Mail:**\n`{email}` *(Tap to copy)*\n\n🔔 **Auto-OTP ON:** OTP aate hi seedha yahan aa jayega.",
            parse_mode="Markdown"
        )

    elif text == "📱 New Number":
        wait = await update.message.reply_text("⏳ Naya number nikal raha hai...")
        nums = await fetch_free_numbers()
        if not nums:
            await wait.edit_text("⚠️ Free SMS server abhi busy hai. Thodi der baad try karein.")
            return

        num = random.choice(nums)
        if user_id in user_sms_tasks:
            user_sms_tasks[user_id].cancel()

        initial_msgs = await fetch_sms_messages(num)
        seen_msgs = {m_txt for _, m_txt in initial_msgs}
        user_sms_tasks[user_id] = asyncio.create_task(auto_check_sms(user_id, num, seen_msgs, context.bot))

        await wait.edit_text(
            f"📱 **New Number:**\n`+{num}` *(Tap to copy)*\n\n🔔 **Auto-OTP ON:** Is par OTP bhejein, aate hi seedha yahan aa jayega.",
            parse_mode="Markdown"
        )

def main():
    threading.Thread(target=run_web, daemon=True).start()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
    
