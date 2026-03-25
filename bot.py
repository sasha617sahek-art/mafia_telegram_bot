import os
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

TOKEN = os.environ.get("BOT_TOKEN")
games = {}  # chat_id : список гравців


# ================== /start ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привіт 👋 Це проста гра 'Бутилочка'. Напиши /game у групі щоб почати!")


# ================== /game ==================
async def game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in games:
        await update.message.reply_text("Ігра вже йде!")
        return

    games[chat_id] = []
    keyboard = [[InlineKeyboardButton("➕ Приєднатися", callback_data="join")]]
    await update.message.reply_text(
        "🎮 Нова гра! Натисни кнопку щоб приєднатися.",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ================== Приєднання ==================
async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat.id
    user = query.from_user

    if chat_id not in games:
        return

    if user.id not in [p["id"] for p in games[chat_id]]:
        name = user.first_name or f"@{user.username}"
        games[chat_id].append({"id": user.id, "name": name})

        # повідомлення у приватному чаті
        try:
            await context.bot.send_message(user.id, f"✅ Ти приєднався до гри в групі {query.message.chat.title}!")
        except Exception:
            await query.message.reply_text(f"{name}, спочатку відкрий бота приватно і натисни Start!")

    players_text = "\n".join([f"- {p['name']}" for p in games[chat_id]])
    await query.edit_message_text(
        f"👥 Гравці: {len(games[chat_id])}\n\n{players_text}",
        reply_markup=query.message.reply_markup,
    )


# ================== /spin ==================
async def spin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in games or len(games[chat_id]) < 2:
        await update.message.reply_text("Недостатньо гравців для гри.")
        return

    p1, p2 = random.sample(games[chat_id], 2)
    await update.message.reply_text(f"🎲 Бутилочка вибрала: {p1['name']} ➡️ {p2['name']}")


# ================== MAIN ==================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("game", game))
    app.add_handler(CommandHandler("spin", spin))
    app.add_handler(CallbackQueryHandler(join, pattern="join"))

    print("Бот запущено...")
    app.run_polling()


if __name__ == "__main__":
    main()
