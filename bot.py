# ================================
# Telegram Mafia-like Bot (Полная версия)
# ================================

import os
import random
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

TOKEN = os.environ.get("BOT_TOKEN")

# ======= Game state =======
games = {}  # хранит игры по chat_id

# ================== Команды ==================

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! 👋 Добро пожаловать в игру 'Ночная Анонимка'!\n\n"
                                    "Чтобы начать новую игру, напиши /game в группе.")

# /game - начать новую игру
async def game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in games:
        await update.message.reply_text("Игра уже идет!")
        return

    # создаем игру
    games[chat_id] = {
        "players": [],      # список id игроков
        "alive": [],        # кто жив
        "state": "lobby",   # состояние: lobby / night / day
        "current": None     # текущая пара атакующий/цель
    }

    keyboard = [[InlineKeyboardButton("➕ Присоединиться", callback_data="join")]]
    msg = await update.message.reply_text(
        "🎮 Новая игра!\n\nИгроки: 0/20\n⏳ До старта 60 секунд",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    # Таймер на присоединение
    await asyncio.sleep(60)
    await start_game(chat_id, context)

# ================== Присоединение ==================
async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat.id
    user = query.from_user

    if chat_id not in games or games[chat_id]["state"] != "lobby":
        return

    game = games[chat_id]
    if user.id not in game["players"] and len(game["players"]) < 20:
        game["players"].append(user.id)

    players_text = "\n".join([f"- {p}" for p in game["players"]])
    await query.edit_message_text(
        f"👥 Игроки: {len(game['players'])}/20\n\n{players_text}",
        reply_markup=query.message.reply_markup
    )

# ================== Начало игры ==================
async def start_game(chat_id, context):
    game = games[chat_id]
    if len(game["players"]) < 2:
        await context.bot.send_message(chat_id, "Недостаточно игроков для старта.")
        del games[chat_id]
        return

    game["alive"] = game["players"].copy()
    game["state"] = "night"
    await context.bot.send_message(chat_id, "🌙 Ночь наступила... Игроки скрываются в темноте.")
    await asyncio.sleep(2)
    await night_round(chat_id, context)

# ================== Ночная фаза ==================
async def night_round(chat_id, context):
    game = games[chat_id]

    if len(game["alive"]) <= 1:
        await end_game(chat_id, context)
        return

    # Выбираем атакующего и цель случайно
    attacker, target = random.sample(game["alive"], 2)
    game["current"] = {"attacker": attacker, "target": target, "action": None, "defense": None}

    # Кнопки атакующего
    kb_attacker = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔪 Убить", callback_data="kill")],
        [InlineKeyboardButton("💋 Поцеловать", callback_data="kiss")],
        [InlineKeyboardButton("🤗 Обнять", callback_data="hug")],
        [InlineKeyboardButton("🥂 Напоить / Выпить", callback_data="drink")]
    ])

    # Кнопки цели
    kb_target = InlineKeyboardMarkup([
        [InlineKeyboardButton("😴 Спать", callback_data="sleep")],
        [InlineKeyboardButton("👀 Проснуться", callback_data="wake")],
        [InlineKeyboardButton("🚨 СОС", callback_data="sos")]
    ])

    try:
        await context.bot.send_message(attacker, "🌙 Твоя цель выбрана. Выбери действие:", reply_markup=kb_attacker)
        await context.bot.send_message(target, "🌙 Что ты будешь делать этой ночью?", reply_markup=kb_target)
    except:
        pass

    # Ждем действия игроков 15 сек
    await asyncio.sleep(15)
    await resolve_night(chat_id, context)

# ================== Обработка выбора ==================
async def action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user.id
    data = query.data

    for game in games.values():
        if "current" not in game or not game["current"]:
            continue

        cur = game["current"]
        if user == cur["attacker"]:
            cur["action"] = data
        elif user == cur["target"]:
            cur["defense"] = data

# ================== Разрешение ночи ==================
async def resolve_night(chat_id, context):
    game = games[chat_id]
    cur = game["current"]
    attacker = cur["attacker"]
    target = cur["target"]
    action = cur["action"]
    defense = cur["defense"]

    text = "🌅 Утро наступило...\n\n"

    # СОС всегда выигрывает
    if defense == "sos":
        if attacker in game["alive"]:
            game["alive"].remove(attacker)
        text += f"🚨 Игрок {attacker} был пойман! Цель {target} выжила.\n"

    elif action == "kill":
        if defense == "wake":
            if random.random() < 0.5:
                game["alive"].remove(target)
                text += f"💀 Игрок {target} погиб в ночи.\n"
            else:
                text += f"😮 Игрок {target} смог выжить!\n"
        else:
            game["alive"].remove(target)
            text += f"💀 Игрок {target} погиб в ночи.\n"

    elif action == "kiss":
        if defense == "wake":
            if random.random() < 0.5:
                game["alive"].remove(target)
                text += f"💀 Игрок {target} погиб от смертельного поцелуя!\n"
            else:
                text += f"💋 Игрок {target} пережил смертельный поцелуй, но зачарован на 1 день.\n"
        else:
            if random.random() < 0.7:
                game["alive"].remove(target)
                text += f"💀 Игрок {target} погиб от смертельного поцелуя!\n"
            else:
                text += f"💋 Игрок {target} пережил поцелуй, зачарован на 1 день.\n"

    elif action == "hug":
        if defense == "wake":
            if random.random() < 0.3:
                game["alive"].remove(target)
                text += f"💀 Игрок {target} погиб от объятий!\n"
            else:
                text += f"🤗 Игрок {target} пережил объятия, испуган на 1 день.\n"
        else:
            if random.random() < 0.5:
                game["alive"].remove(target)
                text += f"💀 Игрок {target} погиб от объятий!\n"
            else:
                text += f"🤗 Игрок {target} пережил объятия, испуган на 1 день.\n"

    elif action == "drink":
        text += f"🥂 Игрок {target} выпил/был напоен и не может действовать днём.\n"

    else:
        text += "🌙 Ночь прошла тихо...\n"

    await context.bot.send_message(chat_id, text)
    await asyncio.sleep(3)
    await night_round(chat_id, context)

# ================== Конец игры ==================
async def end_game(chat_id, context):
    game = games[chat_id]
    if len(game["alive"]) == 1:
        winner = game["alive"][0]
        await context.bot.send_message(chat_id, f"🏆 Победитель: {winner}")
    else:
        await context.bot.send_message(chat_id, "Все игроки погибли или никто не выжил...")
    del games[chat_id]

# ================== Main ==================
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("game", game))
    app.add_handler(CallbackQueryHandler(join, pattern="join"))
    app.add_handler(CallbackQueryHandler(action))
    app.run_polling()

if __name__ == "__main__":
    main()
