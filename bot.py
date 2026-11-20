import os
import re
import random
import string
import asyncio
import threading
import httpx
from bs4 import BeautifulSoup
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

BOT_TOKEN = os.environ.get("BOT_TOKEN")

# Dono channels (Force Join ke liye)
CHANNELS = ["@trustedbynd", "@legendpanel66"]

# 24/7 Keep-Alive Web Server (Render ke liye)
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Temp Mail & Free SMS Bot is running 24/7!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)

user_mails = {}
MAIL_API = "https://api.mail.tm"
SMS_BASE_URL = "https://receive-smss.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# --- FORCE JOIN CHECK ---
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

def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📧 Temp Mail (Auto OTP)", callback_data="new_mail")],
        [InlineKeyboardButton("📱 Free SMS Numbers", callback_data="sms_menu")]
    ])

# --- TEMP MAIL FUNCTIONS ---
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

def email_buttons():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Create New Email", callback_data="new_mail")],
        [InlineKeyboardButton("🗑️ Delete Email", callback_data="delete_mail")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
    ])

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
                        otp_line = f"🔑 **OTP / Code:** `{otp_match.group(0)}`\n" if otp_match else ""

                        text = (
                            f"📩 **New Email Received!**\n\n"
                            f"{otp_line}"
                            f"📧 **To:** `{data['email']}`\n"
                            f"👤 **From:** `{sender}`\n"
                            f"📌 **Subject:** {subject}\n\n"
                            f"📝 **Message:**\n{body}"
                        )
                        await app_bot.send_message(chat_id=user_id, text=text, parse_mode="Markdown")
        except Exception:
            continue

async def generate_and_send(chat_id: int, context: ContextTypes.DEFAULT_TYPE, edit_msg=None):
    if chat_id in user_mails and user_mails[chat_id].get("task"):
        user_mails[chat_id]["task"].cancel()

    email, token = await create_temp_mail()
    if not email or not token:
        err_text = "⚠️ Mail server thoda busy hai, 5 second baad try karein."
        if edit_msg:
            await edit_msg.edit_text(err_text, reply_markup=main_menu_keyboard())
        else:
            await context.bot.send_message(chat_id=chat_id, text=err_text, reply_markup=main_menu_keyboard())
        return

    task = asyncio.create_task(auto_check_inbox(chat_id, context.bot))
    user_mails[chat_id] = {"email": email, "token": token, "seen_ids": set(), "task": task}

    text = (
        f"✅ **Your Temporary Email:**\n`{email}`\n*(Tap to copy)*\n\n"
        f"🔔 **Auto-Inbox ON:** Jaise hi koi OTP ya mail aayega, yahan direct aa jayega."
    )
    if edit_msg:
        await edit_msg.edit_text(text, parse_mode="Markdown", reply_markup=email_buttons())
    else:
        await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown", reply_markup=email_buttons())

# --- FREE PUBLIC SMS SCRAPER ---
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
            for row in rows[:5]:  # Latest 5 SMS
                sender = row.select_one("div.col-md-3.senderr")
                msg_text = row.select_one("div.col-md-6.msgg")
                time_ago = row.select_one("div.col-md-3.time")
                s_txt = sender.get_text(strip=True).replace("Sender", "") if sender else "Unknown"
                m_txt = msg_text.get_text(strip=True).replace("Message", "") if msg_text else ""
                t_txt = time_ago.get_text(strip=True).replace("Time", "") if time_ago else ""
                if m_txt:
                    msgs.append((s_txt, m_txt, t_txt))
    except Exception:
        return []
    return msgs

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await is_user_joined(user_id, context.bot):
        await update.message.reply_text(
            "🔒 **Bot use karne ke liye pehle hamare dono channels join karein!**\n\nJoin karne ke baad neeche **Joined / Check** button dabayein.",
            parse_mode="Markdown",
            reply_markup=join_keyboard()
        )
        return

    await update.message.reply_text(
        "👋 **Welcome!**\n\nNeeche se apna tool chunein:",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard()
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    if query.data == "check_join":
        if await is_user_joined(user_id, context.bot):
            await query.answer("✅ Verified!", show_alert=False)
            await query.edit_message_text(
                "🎉 **Thank you for joining!**\n\nNeeche se apna tool chunein:",
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard()
            )
        else:
            await query.answer("❌ Pehle dono channels join karein!", show_alert=True)
        return

    await query.answer()

    if not await is_user_joined(user_id, context.bot):
        await query.edit_message_text(
            "🔒 **Bot use karne ke liye pehle hamare dono channels join karein!**",
            parse_mode="Markdown",
            reply_markup=join_keyboard()
        )
        return

    if query.data == "main_menu":
        await query.edit_message_text(
            "🏠 **Main Menu**\n\nApna tool chunein:",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )

    elif query.data == "new_mail":
        await query.edit_message_text("⏳ Creating a new temporary email...")
        await generate_and_send(user_id, context, edit_msg=query.message)

    elif query.data == "delete_mail":
        if user_id in user_mails:
            if user_mails[user_id].get("task"):
                user_mails[user_id]["task"].cancel()
            del user_mails[user_id]
        await query.edit_message_text(
            "🗑️ **Email deleted successfully!**",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )

    elif query.data == "sms_menu":
        await query.edit_message_text("⏳ Free SMS numbers load ho rahe hain...")
        nums = await fetch_free_numbers()
        if not nums:
            await query.edit_message_text(
                "⚠️ Free SMS server abhi busy hai. Thodi der baad try karein ya Temp Mail use karein.",
                reply_markup=main_menu_keyboard()
            )
            return

        sample_nums = random.sample(nums, min(10, len(nums)))
        keyboard = []
        for i in range(0, len(sample_nums), 2):
            row = [InlineKeyboardButton(f"📱 +{sample_nums[i]}", callback_data=f"sms_num_{sample_nums[i]}")]
            if i + 1 < len(sample_nums):
                row.append(InlineKeyboardButton(f"📱 +{sample_nums[i+1]}", callback_data=f"sms_num_{sample_nums[i+1]}"))
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("🔄 Shuffle / More Numbers", callback_data="sms_menu")])
        keyboard.append([InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")])

        await query.edit_message_text(
            f"📱 **Free Public SMS Numbers ({len(nums)} Active)**\n\nKisi bhi number par tap karke uske live OTP dekhein:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data.startswith("sms_num_"):
        num = query.data.replace("sms_num_", "")
        await query.edit_message_text(f"⏳ `+{num}` ke latest SMS load ho rahe hain...", parse_mode="Markdown")
        msgs = await fetch_sms_messages(num)

        text = f"📱 **Number:** `+{num}` *(Tap to copy)*\n\n"
        if not msgs:
            text += "📭 Abhi koi recent SMS nahi dikh raha. OTP bhej kar neeche **Refresh OTP** dabayein."
        else:
            text += "📩 **Latest SMS / OTPs:**\n\n"
            for sender, m_txt, t_txt in msgs:
                text += f"👤 **{sender}** ({t_txt})\n💬 `{m_txt}`\n\n"

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh OTP", callback_data=f"sms_num_{num}")],
            [InlineKeyboardButton("⬅️ Back to Numbers", callback_data="sms_menu")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
        ])
        await query.edit_message_text(text[:4000], parse_mode="Markdown", reply_markup=kb)

def main():
    threading.Thread(target=run_web, daemon=True).start()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
        
