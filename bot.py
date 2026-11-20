import os
import random
import string
import threading
import urllib.parse
import httpx
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

BOT_TOKEN = os.environ.get("BOT_TOKEN")

# 24/7 Web Server (Render ke liye)
web_app = Flask(__name__)

@web_app.route("/")
def home():
    return "Bot is running 24/7!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)

# Database (RAM)
users_db = {}

def get_user(user_id):
    if user_id not in users_db:
        users_db[user_id] = {
            "credits": 5,
            "referrals": 0,
            "tempmail": None,
        }
    return users_db[user_id]

# Neeche wale Permanent Buttons (Reply Keyboard)
def permanent_keyboard():
    buttons = [
        ["🎨 AI Image", "📧 Temp Mail"],
        ["📥 Check Inbox", "👤 My Profile"],
        ["💰 Refer & Earn", "❓ Help Guide"],
        ["🏠 Main Menu"],
    ]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["waiting_for_prompt"] = False
    user = update.effective_user
    user_id = user.id

    if user_id not in users_db:
        get_user(user_id)
        if context.args:
            try:
                ref_id = int(context.args[0])
                if ref_id != user_id and ref_id in users_db:
                    users_db[ref_id]["credits"] += 5
                    users_db[ref_id]["referrals"] += 1
            except ValueError:
                pass

    welcome_text = (
        f"👋 <b>Welcome {user.first_name}!</b>\n\n"
        "• 🎨 <b>AI Image:</b> Prompt bhejein aur HD photo paayein\n"
        "• 📧 <b>Temp Mail:</b> 1-click mein free email aur OTP\n"
        "• 💰 <b>Refer & Earn:</b> Har invite par 5 free credits\n\n"
        "👇 <b>Neeche diye gaye buttons par click karein:</b>"
    )
    await update.message.reply_text(
        welcome_text, parse_mode="HTML", reply_markup=permanent_keyboard()
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = update.effective_user.id
    user_data = get_user(user_id)

    # 1. Main Menu
    if text == "🏠 Main Menu":
        context.user_data["waiting_for_prompt"] = False
        await update.message.reply_text(
            "🏠 <b>Main Menu</b>\n\nNeeche se koi bhi service select karein:",
            parse_mode="HTML",
            reply_markup=permanent_keyboard(),
        )
        return

    # 2. Temp Mail (1-Click Generate)
    if text == "📧 Temp Mail":
        context.user_data["waiting_for_prompt"] = False
        wait_msg = await update.message.reply_text("⏳ Naya Temp Mail ban raha hai...")
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                dom_res = await client.get("https://api.mail.tm/domains")
                domain = dom_res.json()["hydra:member"][0]["domain"]

                rand_user = "".join(random.choices(string.ascii_lowercase + string.digits, k=9))
                email = f"{rand_user}@{domain}"
                password = "".join(random.choices(string.ascii_letters + string.digits, k=12))

                await client.post(
                    "https://api.mail.tm/accounts",
                    json={"address": email, "password": password},
                )
                tok_res = await client.post(
                    "https://api.mail.tm/token",
                    json={"address": email, "password": password},
                )
                token = tok_res.json()["token"]
                user_data["tempmail"] = {"email": email, "token": token}

            await wait_msg.edit_text(
                "✅ <b>Naya Temp Mail Ready Hai!</b>\n\n"
                f"📧 <b>Email:</b> <code>{email}</code>\n"
                "<i>(Tap karke copy karein)</i>\n\n"
                "OTP aane ke baad neeche <b>📥 Check Inbox</b> par click karein.",
                parse_mode="HTML",
            )
        except Exception:
            await wait_msg.edit_text("⚠️ Temp Mail server busy hai. Dobara click karein.")
        return

    # 3. Check Inbox (1-Click)
    if text == "📥 Check Inbox":
        context.user_data["waiting_for_prompt"] = False
        if not user_data["tempmail"]:
            await update.message.reply_text(
                "⚠️ Pehle <b>📧 Temp Mail</b> par click karke email banayein!",
                parse_mode="HTML",
                reply_markup=permanent_keyboard(),
            )
            return

        wait_msg = await update.message.reply_text("🔄 Inbox check ho raha hai...")
        try:
            token = user_data["tempmail"]["token"]
            email = user_data["tempmail"]["email"]
            async with httpx.AsyncClient(timeout=15) as client:
                res = await client.get(
                    "https://api.mail.tm/messages",
                    headers={"Authorization": f"Bearer {token}"},
                )
                messages = res.json().get("hydra:member", [])

            if not messages:
                msg_text = (
                    f"📭 <b>Inbox Khali Hai</b>\n\n"
                    f"📧 <code>{email}</code>\n\n"
                    "Abhi tak koi mail nahi aaya hai. Thodi der baad phir check karein."
                )
            else:
                msg_text = f"📥 <b>Inbox ({email})</b>\n━━━━━━━━━━━━━━━━\n"
                for msg in messages[:3]:
                    sender = msg.get("from", {}).get("address", "Unknown")
                    subject = msg.get("subject", "No Subject")
                    intro = msg.get("intro", "")
                    msg_text += (
                        f"👤 <b>From:</b> {sender}\n"
                        f"📌 <b>Sub:</b> {subject}\n"
                        f"💬 {intro}\n━━━━━━━━━━━━━━━━\n"
                    )
            await wait_msg.edit_text(msg_text, parse_mode="HTML")
        except Exception:
            await wait_msg.edit_text("⚠️ Inbox load nahi ho paya. Dobara try karein.")
        return

    # 4. AI Image Button
    if text == "🎨 AI Image":
        if user_data["credits"] < 1:
            context.user_data["waiting_for_prompt"] = False
            await update.message.reply_text(
                "❌ <b>Credits khatam ho gaye hain!</b>\n\n"
                "<b>💰 Refer & Earn</b> par click karke free credits kamayein.",
                parse_mode="HTML",
                reply_markup=permanent_keyboard(),
            )
            return
        context.user_data["waiting_for_prompt"] = True
        await update.message.reply_text(
            "🎨 <b>AI Image Generator</b>\n\n"
            "Jo photo banwani hai uska prompt English mein likh kar bhejein.\n"
            "<i>Example: 3D cartoon boy in Indian village, sunset, HD</i>\n\n"
            "💰 <b>Cost:</b> 1 Credit per image",
            parse_mode="HTML",
            reply_markup=permanent_keyboard(),
        )
        return

    # 5. Profile
    if text == "👤 My Profile":
        context.user_data["waiting_for_prompt"] = False
        await update.message.reply_text(
            "👤 <b>Your Profile</b>\n"
            "━━━━━━━━━━━━━━━━\n"
            f"🆔 <b>User ID:</b> <code>{user_id}</code>\n"
            f"💰 <b>Credits:</b> {user_data['credits']}\n"
            f"👥 <b>Total Referrals:</b> {user_data['referrals']}",
            parse_mode="HTML",
            reply_markup=permanent_keyboard(),
        )
        return

    # 6. Refer & Earn
    if text == "💰 Refer & Earn":
        context.user_data["waiting_for_prompt"] = False
        bot_username = (await context.bot.get_me()).username
        ref_link = f"https://t.me/{bot_username}?start={user_id}"
        await update.message.reply_text(
            "💰 <b>Refer & Earn</b>\n\n"
            "Apne dosto ko invite karein aur har invite par <b>5 Credits</b> paayein!\n\n"
            f"🔗 <b>Your Link:</b>\n<code>{ref_link}</code>",
            parse_mode="HTML",
            reply_markup=permanent_keyboard(),
        )
        return

    # 7. Help Guide
    if text == "❓ Help Guide":
        context.user_data["waiting_for_prompt"] = False
        await update.message.reply_text(
            "❓ <b>Help Guide</b>\n\n"
            "• <b>🎨 AI Image:</b> Click karein, prompt bhejein, HD photo paayein (1 Credit).\n"
            "• <b>📧 Temp Mail:</b> Click karte hi naya free email mil jayega.\n"
            "• <b>📥 Check Inbox:</b> Email par aaye hue OTP aur messages dekhein.\n"
            "• <b>💰 Refer & Earn:</b> Dosto ko jod kar free credits kamayein.",
            parse_mode="HTML",
            reply_markup=permanent_keyboard(),
        )
        return

    # 8. Agar user ne AI Image ke liye prompt bheja hai
    if context.user_data.get("waiting_for_prompt"):
        if user_data["credits"] < 1:
            context.user_data["waiting_for_prompt"] = False
            await update.message.reply_text(
                "❌ Credits khatam ho gaye hain!", reply_markup=permanent_keyboard()
            )
            return

        context.user_data["waiting_for_prompt"] = False
        user_data["credits"] -= 1
        wait_msg = await update.message.reply_text(
            "🎨 <b>Image ban rahi hai...</b> (5-10 second wait karein)",
            parse_mode="HTML",
        )

        try:
            encoded_prompt = urllib.parse.quote(text)
            seed = random.randint(1, 999999)
            img_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&seed={seed}&nologo=true"

            async with httpx.AsyncClient(timeout=45, follow_redirects=True) as client:
                res = await client.get(img_url)
                res.raise_for_status()
                img_bytes = res.content

            await wait_msg.delete()
            await update.message.reply_photo(
                photo=img_bytes,
                caption=f"✅ <b>Prompt:</b> {text}\n💰 <b>Remaining Credits:</b> {user_data['credits']}",
                parse_mode="HTML",
                reply_markup=permanent_keyboard(),
            )
        except Exception:
            user_data["credits"] += 1
            await wait_msg.edit_text(
                "⚠️ Image generate nahi ho payi. Aapka 1 credit wapas kar diya gaya hai. Dobara try karein!"
            )

def main():
    threading.Thread(target=run_web, daemon=True).start()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("24/7 BOT STARTED ✅")
    app.run_polling()

if __name__ == "__main__":
    main()
        
