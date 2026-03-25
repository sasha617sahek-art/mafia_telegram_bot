import os
import random
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

TOKEN = os.environ.get("BOT_TOKEN")
games = {}  # chat_id : game_data


# ================== /start ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! 👋 Добро пожаловать в игру 'Бутылочка'!\n"
        "Чтобы начать игру в группе, напиши /game"
    )


# ================== /game ==================
async def game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in games:
        await update.message.reply_text("Игра уже идёт!")
        return

    games[chat_id] = {
        "players": [],
        "alive": [],
        "state": "lobby",
        "current": None,
        "round": 0,
    }

    keyboard = [[InlineKeyboardButton("➕ Присоединиться", callback_data="join")]]
    await update.message.reply_text(
        "🎮 Новая игра! ⏳ 60 секунд на присоединение.",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

    await asyncio.sleep(60)

    game_data = games.get(chat_id)
    if not game_data or game_data["state"] != "lobby":
        return

    if not game_data["players"]:
        await context.bot.send_message(chat_id, "⏳ Никто не присоединился. Игра отменена.")
        del games[chat_id]
        return

    players_text = "\n".join([f"- {p['name']}" for p in game_data["players"]])
    await context.bot.send_message(
        chat_id,
        f"⏳ Время вышло!\n👥 Игроки: {len(game_data['players'])}\n\n{players_text}",
    )

    await start_round(chat_id, context)


# ================== Присоединение ==================
async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat.id
    user = query.from_user

    if chat_id not in games or games[chat_id]["state"] != "lobby":
        return

    game = games[chat_id]
    if user.id not in [p["id"] for p in game["players"]]:
        name = user.first_name or f"@{user.username}"
        game["players"].append({"id": user.id, "name": name})

    players_text = "\n".join([f"- {p['name']}" for p in game["players"]])
    await query.edit_message_text(
        f"👥 Игроки: {len(game['players'])}\n\n{players_text}",
        reply_markup=query.message.reply_markup,
    )


# ================== Начало раунда ==================
async def start_round(chat_id, context):
    game = games[chat_id]
    if len(game["players"]) < 2:
        await context.bot.send_message(chat_id, "Недостаточно игроков для старта.")
        del games[chat_id]
        return

    game["alive"] = [p["id"] for p in game["players"]]
    game["state"] = "round"
    await next_turn(chat_id, context)


# ================== Следующий ход ==================
async def next_turn(chat_id, context):
    game = games.get(chat_id)
    if not game:
        return

    alive_players = [p for p in game["players"] if p["id"] in game["alive"]]

    if len(alive_players) == 1:
        await context.bot.send_message(chat_id, f"🏆 Победитель: {alive_players[0]['name']}")
        del games[chat_id]
        return

    if len(alive_players) <= 0:
        await end_game(chat_id, context)
        return

    game["round"] += 1
    p1, p2 = random.sample(alive_players, 2)
    game["current"] = {"p1": p1, "p2": p2, "action": None, "response": None}

    kb_p1 = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔪 Убить", callback_data="kill")],
        [InlineKeyboardButton("💋 Поцеловать", callback_data="kiss")],
        [InlineKeyboardButton("🤗 Обнять", callback_data="hug")],
        [InlineKeyboardButton("🥂 Выпить", callback_data="drink")],
    ])

    try:
        await context.bot.send_message(
            p1["id"],
            f"🎲 Раунд {game['round']}!\nТы выбран с {p2['name']}!\nВыбери действие:",
            reply_markup=kb_p1,
        )
    except Exception:
        pass

    await asyncio.sleep(15)
    await check_turn(chat_id, context)


# ================== Обработка кнопок ==================
async def action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    for game in games.values():
        if game.get("current"):
            cur = game["current"]
            if user_id == cur["p1"]["id"]:
                cur["action"] = data
                kb_p2 = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Принять", callback_data="accept")],
                    [InlineKeyboardButton("❌ Отказаться", callback_data="decline")],
                ])
                try:
                    await context.bot.send_message(
                        cur["p2"]["id"],
                        f"{cur['p1']['name']} выбрал действие: {data}\nПрими или откажись?",
                        reply_markup=kb_p2,
                    )
                except Exception:
                    pass
            elif user_id == cur["p2"]["id"]:
                cur["response"] = data


# ================== Проверка хода ==================
async def check_turn(chat_id, context):
    game = games.get(chat_id)
    if not game or not game.get("current"):
        return

    cur = game["current"]
    p1, p2 = cur["p1"], cur["p2"]
    action, response = cur["action"], cur["response"]

    text = f"🎲 Раунд {game['round']}: {p1['name']} и {p2['name']}\n"

    if response == "accept":
        if action == "kill":
            if p2["id"] in game["alive"]:
                game["alive"].remove(p2["id"])
            text += f"💀 {p1['name']} убил {p2['name']}!\n"
        elif action == "kiss":
            text += f"💋 {p1['name']} поцеловал {p2['name']}!\n"
        elif action == "hug":
            text += f"🤗 {p1['name']} обнял {p2['name']}!\n"
        elif action == "drink":
            text += f"🥂 {p1['name']} дал выпить {p2['name']}!\n"
    elif response == "decline":
        text += f"❌ {p2['name']} отказался от действия.\n"
    else:
        text += "⏱ Время истекло, действие не выполнено.\n"

    alive_players = [p for p in game["players"] if p["id"] in game["alive"]]
    players_text = "\n".join([f"- {p['name']}" for p in alive_players])
    text += f"\n👥 Осталось игроков: {len(alive_players)}\n{players_text}"

    await context.bot.send_message(chat_id, text)
    await asyncio.sleep(2)
    await next_turn(chat_id, context)


# ================== Конец игры ==================
async def end_game(chat_id, context):
    game = games.get(chat_id)
    if not game:
        return

    alive_players = [p for p in game["players"] if p["id"] in game["alive"]]
    if alive_players:
        winner_names = ", ".join([p["name"] for p in alive_players])
        await context.bot.send_message(chat_id, f"🏆 Победители: {winner_names}")
    else:
        await context.bot.send_message(chat_id, "Все игроки выбиты, нет победителей.")

    del games[chat_id]
