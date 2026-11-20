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

# Sirf ek channel (Force Join ke liye)
CHANNEL = "@trustedbynd"

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
                        full_res = await client.get(
                        
