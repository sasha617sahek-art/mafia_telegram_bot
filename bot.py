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
        "Привіт 👋 Це гра 'Бутилочка'. Напиши /game у групі щоб почати!"
    )


# ================== /game ==================
async def game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in games:
        await update.message.reply_text("Ігра вже йде!")
        return

    games[chat_id] = {
        "players": [],
        "alive": [],
        "state": "lobby",
        "current": None,
        "round": 0,
    }

    keyboard = [[InlineKeyboardButton("➕ Приєднатися", callback_data="join")]]
    await update.message.reply_text(
        "🎮 Нова гра! ⏳ 60 секунд на приєднання.",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

    await asyncio.sleep(60)

    game_data = games.get(chat_id)
    if not game_data or game_data["state"] != "lobby":
        return

    if not game_data["players"]:
        await context.bot.send_message(chat_id, "⏳ Ніхто не приєднався. Ігра скасована.")
        del games[chat_id]
        return

    players_text = "\n".join([f"- {p['name']}" for p in game_data["players"]])
    await context.bot.send_message(
        chat_id,
        f"⏳ Час вийшов!\n👥 Гравці: {len(game_data['players'])}\n\n{players_text}",
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

        # повідомлення у приватному чаті
        try:
            await context.bot.send_message(
                user.id,
                f"✅ Ти приєднався до гри в групі {query.message.chat.title}!"
            )
        except Exception:
            await query.message.reply_text(
                f"{name}, спочатку відкрий бота приватно і натисни Start!"
            )

    # оновлення повідомлення у групі
    players_text = "\n".join([f"- {p['name']}" for p in game["players"]])
    await query.edit_message_text(
        f"👥 Гравці: {len(game['players'])}\n\n{players_text}",
        reply_markup=query.message.reply_markup,
    )


# ================== Початок раунда ==================
async def start_round(chat_id, context):
    game = games[chat_id]
    if len(game["players"]) < 2:
        await context.bot.send_message(chat_id, "Недостатньо гравців для старту.")
        del games[chat_id]
        return

    game["alive"] = [p["id"] for p in game["players"]]
    game["state"] = "round"
    await next_turn(chat_id, context)


# ================== Наступний хід ==================
async def next_turn(chat_id, context):
    game = games.get(chat_id)
    if not game:
        return

    alive_players = [p for p in game["players"] if p["id"] in game["alive"]]

    if len(alive_players) == 1:
        await context.bot.send_message(chat_id, f"🏆 Переможець: {alive_players[0]['name']}")
        del games[chat_id]
        return

    if len(alive_players) <= 0:
        await end_game(chat_id, context)
        return

    game["round"] += 1
    p1, p2 = random.sample(alive_players, 2)
    game["current"] = {"p1": p1, "p2": p2, "action": None, "response": None}

    kb_p1 = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔪 Вбити", callback_data="kill")],
        [InlineKeyboardButton("💋 Поцілувати", callback_data="kiss")],
        [InlineKeyboardButton("🤗 Обняти", callback_data="hug")],
        [InlineKeyboardButton("🥂 Напоїти", callback_data="drink")],
    ])

    try:
        await context.bot.send_message(
            p1["id"],
            f"🎲 Раунд {game['round']}!\nТи вибраний з {p2['name']}!\nВибери дію:",
            reply_markup=kb_p1,
        )
    except Exception:
        pass

    await asyncio.sleep(15)
    await check_turn(chat_id, context)


# ================== Обробка кнопок ==================
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
                    [InlineKeyboardButton("✅ Прийняти", callback_data="accept")],
                    [InlineKeyboardButton("❌ Відмовитись", callback_data="decline")],
                ])
                try:
                    await context.bot.send_message(
                        cur["p2"]["id"],
                        f"{cur['p1']['name']} вибрав дію: {data}\nПрийми чи відмовся?",
                        reply_markup=kb_p2,
                    )
                except Exception:
                    pass
            elif user_id == cur["p2"]["id"]:
                cur["response"] = data


# ================== Перевірка ходу ==================
async def check_turn(chat_id, context):
    game = games.get(chat_id)
    if not game or not game.get("current"):
        return

    cur = game["current"]
    p1, p2 = cur["p1"], cur["p2"]
    action, response = cur["action"], cur["response"]

    text = f"🎲 Раунд {game['round']}: {p1['name']} і {p2['name']}\n"

    if response == "accept":
        if action == "kill":
            if p2["id"] in game["alive"]:
                game["alive"].remove(p2["id"])
            text += f"💀 {p1['name']} вбив {p2['name']}!\n"
        elif action == "kiss":
            text += f"💋 {p1['name']} поцілував {p2['name']}!\n"
        elif action == "hug":
            text += f"🤗 {p1['name']} обняв {p2['name']}!\n"
        elif action == "drink":
            text += f"🥂 {p1['name']} напоїв {p2['name']}!\n"
    elif response == "decline":
        text += f"❌ {p2['name']} відмовився від дії.\n"
    else:
        text += "⏱ Час вийшов, дія не виконана.\n"

    alive_players = [p for p in game["players"] if p["id"] in game["alive"]]
    players_text = "\n".join([f"- {p['name']}" for p in alive_players])
    text += f"\n👥 Залишилось гравців: {len(alive_players)}\n{players_text}"

    await context.bot.send_message(chat_id, text)
    await asyncio.sleep(2)
    await next_turn(chat_id, context)


# ================== Кінець гри ==================
async def end_game(chat_id, context):
    game = games.get(chat_id)
    if not game:
        return

    alive_players = [p for p in game["players"] if p["id"] in game["alive"]]
    if alive_players:
        winner_names = ", ".join([p["name"] for p in alive_players])
        await context.bot.send_message(chat_id, f"🏆 Переможці: {winner_names}")
    else:
        await context.bot.send_message(chat_id, "Всі гравці вибиті, переможців нем
