import logging
import sqlite3
import time
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes
)

# ---------------------- تنظیمات لاگ ----------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# ---------------------- توکن ربات ----------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")  # توکن رو از Environment Variable بخون

# ---------------------- نرخ ماینینگ ----------------------
MINING_RATE = 0.01  # ۱ سنت به ازای هر ضربه

# ---------------------- دیتابیس ----------------------
conn = sqlite3.connect("mining_bot.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    total_taps INTEGER DEFAULT 0,
    total_mined REAL DEFAULT 0,
    last_tap_time INTEGER DEFAULT 0,
    referral_code TEXT,
    referred_by INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    amount REAL,
    type TEXT,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")
conn.commit()


# ---------------------- start ----------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username
    first_name = update.effective_user.first_name
    last_name = update.effective_user.last_name

    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()

    if not user:
        referral_code = context.args[0] if context.args else None
        referred_by = int(referral_code) if referral_code else None

        cursor.execute("""
        INSERT INTO users (user_id, username, first_name, last_name, referral_code, referred_by)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, username, first_name, last_name, str(user_id), referred_by))

        if referred_by:
            cursor.execute("UPDATE users SET total_mined = total_mined + 0.5 WHERE user_id = ?", (referred_by,))
            cursor.execute("""
            INSERT INTO transactions (user_id, amount, type, description)
            VALUES (?, ?, ?, ?)
            """, (referred_by, 0.5, "referral", f"پاداش دعوت کاربر {user_id}"))

        conn.commit()

        welcome_text = (
            f"👋 سلام {first_name}!\n\n"
            "به ربات ماینینگ MHD Coin خوش اومدی! 🎯\n\n"
            f"با هر ضربه {MINING_RATE} سنت دریافت می‌کنی.\n"
            "هر ۱ ساعت می‌تونی ۱۰۰ ضربه بزنی! 🕒\n\n"
            "دوستات رو دعوت کن تا پاداش بیشتری بگیری! 💰"
        )
    else:
        welcome_text = (
            f"👋 سلام {first_name}!\n\n"
            "دوباره برگشتی! آماده‌ای برای ماین بیشتر؟ ⛏️"
        )

    cursor.execute("SELECT total_taps, total_mined FROM users WHERE user_id = ?", (user_id,))
    user_data = cursor.fetchone()
    total_taps, total_mined = user_data if user_data else (0, 0)

    keyboard = [
        [InlineKeyboardButton("⛏️ ضربه بزن", callback_data="mine")],
        [InlineKeyboardButton("💰 موجودی من", callback_data="balance"),
         InlineKeyboardButton("👥 دعوت دوستان", callback_data="referral")],
        [InlineKeyboardButton("🏆 لیدربرد", callback_data="leaderboard"),
         InlineKeyboardButton("ℹ️ اطلاعات پروژه", callback_data="info")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"{welcome_text}\n\n"
        f"📊 آمار تو:\n"
        f"• ضربه‌ها: {total_taps}\n"
        f"• ماین شده: {total_mined:.2f} سنت",
        reply_markup=reply_markup
    )


# ---------------------- مدیریت دکمه‌ها ----------------------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    await query.answer()

    message = ""

    if query.data == "mine":
        cursor.execute("SELECT last_tap_time FROM users WHERE user_id = ?", (user_id,))
        last_tap_time = cursor.fetchone()[0] or 0
        current_time = int(time.time())

        if current_time - last_tap_time < 3:
            await query.edit_message_text("⏳ لطفاً ۳ ثانیه صبر کن!", reply_markup=query.message.reply_markup)
            return

        cursor.execute("""
        UPDATE users
        SET total_taps = total_taps + 1,
            total_mined = total_mined + ?,
            last_tap_time = ?
        WHERE user_id = ?
        """, (MINING_RATE, current_time, user_id))

        cursor.execute("""
        INSERT INTO transactions (user_id, amount, type, description)
        VALUES (?, ?, ?, ?)
        """, (user_id, MINING_RATE, "mining", "ماینینگ با ضربه"))
        conn.commit()

        cursor.execute("SELECT total_taps, total_mined FROM users WHERE user_id = ?", (user_id,))
        total_taps, total_mined = cursor.fetchone()

        message = (
            f"✅ ضربه ثبت شد! +{MINING_RATE}\n\n"
            f"📊 آمار تو:\n"
            f"• ضربه‌ها: {total_taps}\n"
            f"• ماین شده: {total_mined:.2f} سنت"
        )

    elif query.data == "balance":
        cursor.execute("SELECT total_taps, total_mined FROM users WHERE user_id = ?", (user_id,))
        total_taps, total_mined = cursor.fetchone()
        message = (
            f"💰 موجودی:\n"
            f"• ضربه‌ها: {total_taps}\n"
            f"• ماین شده: {total_mined:.2f} سنت"
        )

    elif query.data == "referral":
        invite_link = f"https://t.me/{(await context.bot.get_me()).username}?start={user_id}"
        message = (
            "👥 دوستانت رو دعوت کن و جایزه بگیر!\n"
            "هر دعوت = 0.5 سنت 🎁\n\n"
            f"لینک تو:\n{invite_link}"
        )

    elif query.data == "leaderboard":
        cursor.execute("""
        SELECT first_name, total_mined FROM users
        ORDER BY total_mined DESC
        LIMIT 10
        """)
        top_users = cursor.fetchall()

        leaderboard = "🏆 لیدربرد:\n\n"
        for i, (name, mined) in enumerate(top_users):
            leaderboard += f"{i+1}. {name} — {mined:.2f} سنت\n"
        message = leaderboard

    elif query.data == "info":
        message = (
            "ℹ️ MHD Coin یک پروژه نوین بلاکچینی است.\n\n"
            "📊 مشخصات:\n"
            "• شبکه: ERC-20\n"
            "• عرضه: 100M\n"
            "• ماینینگ: 10%\n\n"
            "🌐 وبسایت: https://mhdcoin.com"
        )

    keyboard = [
        [InlineKeyboardButton("⛏️ ضربه بزن", callback_data="mine")],
        [InlineKeyboardButton("💰 موجودی من", callback_data="balance"),
         InlineKeyboardButton("👥 دعوت دوستان", callback_data="referral")],
        [InlineKeyboardButton("🏆 لیدربرد", callback_data="leaderboard"),
         InlineKeyboardButton("ℹ️ اطلاعات پروژه", callback_data="info")]
    ]

    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))


# ---------------------- stats ----------------------
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]

    cursor.execute("SELECT SUM(total_taps), SUM(total_mined) FROM users")
    total_taps, total_mined = cursor.fetchone()
    total_taps, total_mined = total_taps or 0, total_mined or 0

    await update.message.reply_text(
        f"📊 آمار کلی:\n"
        f"• کاربران: {total_users}\n"
        f"• ضربه‌ها: {total_taps}\n"
        f"• ماین شده: {total_mined:.2f} سنت"
    )


# ---------------------- main ----------------------
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.run_polling()


if __name__ == "__main__":
    main()
