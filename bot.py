import os
import threading
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Token hum Render ki settings mein dalenge (taaki safe rahe)
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# 24/7 zinda rakhne ke liye chhota web server
web_app = Flask(__name__)

@web_app.route("/")
def home():
    return "Bot is running 24/7!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)

# Bot ka database aur menu
users_db = {}

def get_user(user_id):
    if user_id not in users_db:
        users_db[user_id] = {"credits": 5, "referrals": 0}
    return users_db[user_id]

def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("⚡ Main Service", callback_data="service_1")],
        [InlineKeyboardButton("🔍 Option 2", callback_data="service_2")],
        [
            InlineKeyboardButton("❓ Help Guide", callback_data="help"),
            InlineKeyboardButton("👤 My Profile", callback_data="profile")
        ],
        [
            InlineKeyboardButton("💰 Earn Credits (Refer)", callback_data="refer"),
            InlineKeyboardButton("🎟️ Redeem Coupon", callback_data="coupon")
        ],
        [InlineKeyboardButton("💳 Buy Credits / TopUp", callback_data="topup")]
    ]
    return InlineKeyboardMarkup(keyboard)

def back_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="back")]])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        "• ⚡ Fast & Automated Services\n"
        "• 💰 Refer friends & earn free credits\n"
        "• 🎟️ Claim bonus coupons\n\n"
        "👇 <b>Select a service from the menu below:</b>"
    )
    await update.message.reply_text(welcome_text, parse_mode="HTML", reply_markup=main_menu_keyboard())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user_data = get_user(user_id)
    data = query.data

    if data == "back":
        await query.edit_message_text(
            "👇 <b>Select a service from the menu below:</b>",
            parse_mode="HTML",
            reply_markup=main_menu_keyboard()
        )
    elif data == "profile":
        text = (
            "👤 <b>Your Profile</b>\n"
            "━━━━━━━━━━━━━━━━\n"
            f"🆔 <b>User ID:</b> <code>{user_id}</code>\n"
            f"💰 <b>Credits:</b> {user_data['credits']}\n"
            f"👥 <b>Total Referrals:</b> {user_data['referrals']}"
        )
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=back_keyboard())
    elif data == "refer":
        bot_username = (await context.bot.get_me()).username
        ref_link = f"https://t.me/{bot_username}?start={user_id}"
        text = (
            "💰 <b>Refer & Earn</b>\n\n"
            "Apne dosto ko invite karein aur har invite par <b>5 Credits</b> paayein!\n\n"
            f"🔗 <b>Your Link:</b>\n<code>{ref_link}</code>"
        )
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=back_keyboard())
    elif data == "help":
        text = "❓ <b>Help Guide</b>\n\nMenu se koi bhi option chunein. Support ke liye admin se contact karein."
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=back_keyboard())
    elif data in ("service_1", "service_2", "coupon", "topup"):
        text = f"⚙️ <b>{data.upper()}</b> abhi setup ho raha hai."
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=back_keyboard())

def main():
    # Flask server ko background mein start karega
    threading.Thread(target=run_web, daemon=True).start()

    # Telegram bot start karega
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("24/7 BOT STARTED ✅")
    app.run_polling()

if __name__ == "__main__":
    main()
  
