# ================================
# Telegram Mafia-like Bot с ролями, действиями и голосованием
# ================================

import os
import random
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

TOKEN = os.environ.get("BOT_TOKEN")

# ======= Game state =======
games = {}  # {chat_id: game_data}

# ================== /start ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! 👋 Добро пожаловать в игру 'Ночная Анонимка'!\n"
        "Чтобы начать новую игру, напиши /game в группе."
    )

# ================== /game ==================
async def game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in games:
        await update.message.reply_text("Игра уже идёт!")
        return

    # Создаём новую игру
    games[chat_id] = {
        "players": [],      # [{"id":..., "name":..., "role":...}]
        "alive": [],        # [id игроков]
        "state": "lobby",
        "current": None,
        "votes": {}         # для дневного голосования
    }

    keyboard = [[InlineKeyboardButton("➕ Присоединиться", callback_data="join")]]
    await update.message.reply_text(
        "🎮 Новая игра!\n⏳ 60 секунд до старта. Присоединяйтесь!",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

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
    if user.id not in [p["id"] for p in game["players"]] and len(game["players"]) < 20:
        name = user.first_name if user.first_name else f"@{user.username}"
        game["players"].append({"id": user.id, "name": name})
    players_text = "\n".join([f"- {p['name']}" for p in game["players"]])
    await query.edit_message_text(
        f"👥 Игроки: {len(game['players'])}/20\n\n{players_text}",
        reply_markup=query.message.reply_markup
    )

# ================== Назначение ролей и старт ==================
async def start_game(chat_id, context):
    game = games[chat_id]
    if len(game["players"]) < 2:
        await context.bot.send_message(chat_id, "Недостаточно игроков для старта.")
        del games[chat_id]
        return

    # Назначаем роли случайно
    roles = ["Маньяк", "Защитник", "Наблюдатель", "Везунчик"]
    for p in game["players"]:
        p["role"] = random.choice(roles)
    game["alive"] = [p["id"] for p in game["players"]]
    game["state"] = "night"

    names = ", ".join([p["name"] for p in game["players"]])
    await context.bot.send_message(chat_id, f"🌙 Ночь начинается! Игроки: {names}")
    await asyncio.sleep(2)
    await night_round(chat_id, context)

# ================== Ночная фаза ==================
async def night_round(chat_id, context):
    game = games[chat_id]
    if len(game["alive"]) <= 1:
        await end_game(chat_id, context)
        return

    # Выбираем атакующего и цель
    alive_players = [p for p in game["players"] if p["id"] in game["alive"]]
    attacker, target = random.sample(alive_players, 2)
    game["current"] = {"attacker": attacker, "target": target, "action": None, "defense": None}

    # Кнопки атакующего
    kb_attacker = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔪 Убить", callback_data="kill")],
        [InlineKeyboardButton("💋 Поцеловать", callback_data="kiss")],
        [InlineKeyboardButton("🤗 Обнять", callback_data="hug")],
        [InlineKeyboardButton("🥂 Выпить", callback_data="drink")]
    ])

    # Кнопки цели
    kb_target = InlineKeyboardMarkup([
        [InlineKeyboardButton("😴 Спать", callback_data="sleep")],
        [InlineKeyboardButton("👀 Проснуться", callback_data="wake")],
        [InlineKeyboardButton("🚨 СОС", callback_data="sos")]
    ])

    try:
        await context.bot.send_message(attacker["id"],
                                       f"🌙 Твоя цель: {target['name']}\nВыбери действие:",
                                       reply_markup=kb_attacker)
        await context.bot.send_message(target["id"],
                                       "🌙 Что будешь делать этой ночью?",
                                       reply_markup=kb_target)
    except:
        pass

    await asyncio.sleep(15)
    await resolve_night(chat_id, context)

# ================== Обработка выбора ==================
async def action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    for game in games.values():
        if not game.get("current"):
            continue
        cur = game["current"]
        if user_id == cur["attacker"]["id"]:
            cur["action"] = data
        elif user_id == cur["target"]["id"]:
            cur["defense"] = data
        # Дневное голосование
        elif game["state"] == "day" and data.startswith("vote_"):
            target_id = int(data.split("_")[1])
            game["votes"][user_id] = target_id

# ================== Разрешение ночи ==================
async def resolve_night(chat_id, context):
    game = games[chat_id]
    cur = game["current"]
    attacker = cur["attacker"]
    target = cur["target"]
    action = cur["action"]
    defense = cur["defense"]

    text = "🌅 Утро настало...\n\n"

    # СОС всегда выигрывает
    if defense == "sos":
        if attacker["id"] in game["alive"]:
            game["alive"].remove(attacker["id"])
        text += f"🚨 {attacker['name']} был пойман! {target['name']} выжила.\n"
    else:
        # Шансы действий
        if action == "kill":
            chance = 1.0 if defense == "sleep" else 0.5
            if random.random() < chance:
                game["alive"].remove(target["id"])
                text += f"💀 {target['name']} погиб в ночи.\n"
            else:
                text += f"😮 {target['name']} смог выжить!\n"
        elif action == "kiss":
            chance = 0.7 if defense == "sleep" else 0.5
            if random.random() < chance:
                game["alive"].remove(target["id"])
                text += f"💀 {target['name']} погиб от поцелуя!\n"
            else:
                text += f"💋 {target['name']} выжил, зачарован на день.\n"
        elif action == "hug":
            chance = 0.5 if defense == "sleep" else 0.3
            if random.random() < chance:
                game["alive"].remove(target["id"])
                text += f"💀 {target['name']} погиб от объятий!\n"
            else:
                text += f"🤗 {target['name']} выжил, испуган на день.\n"
        elif action == "drink":
            text += f"🥂 {target['name']} выпил/был напоен и не может действовать днём.\n"

    await context.bot.send_message(chat_id, text)
    await asyncio.sleep(2)
    await day_phase(chat_id, context)

# ================== Дневная фаза ==================
async def day_phase(chat_id, context):
    game = games[chat_id]
    game["state"] = "day"
    game["votes"] = {}

    alive_players = [p for p in game["players"] if p["id"] in game["alive"]]
    text = "☀️ День настал! Голосование: кого отправим в тюрьму?\n"
    await context.bot.send_message(chat_id, text)

    # Кнопки голосования для каждого игрока
    for p in alive_players:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"Голосовать за {t['name']}", callback_data=f"vote_{t['id']}")]
            for t in alive_players if t["id"] != p["id"]
        ])
        try:
            await context.bot.send_message(p["id"], "Выберите игрока для голосования:", reply_markup=kb)
        except:
            pass

    # Ждём 20 секунд на голосование
    await asyncio.sleep(20)

    # Подсчёт голосов
    votes_count = {}
    for vote in game["votes"].values():
        votes_count[vote] = votes_count.get(vote, 0) + 1
    if votes_count:
        max_votes = max(votes_count.values())
        eliminated = [pid for pid, count in votes_count.items() if count == max_votes]
        if eliminated:
            eliminated_id = random.choice(eliminated)
            game["alive"].remove(eliminated_id)
            name_elim = next(p["name"] for p in alive_players if p["id"] == eliminated_id)
            await context.bot.send_message(chat_id, f"⚖️ {name_elim} отправлен(а) в тюрьму!")
    else:
        await context.bot.send_message(chat_id, "Никто не был отправлен в тюрьму.")

    await asyncio.sleep(2)
    game["state"] = "night"
    await night_round(chat_id, context)

# ================== Конец игры ==================
async def end_game(chat_id, context):
    game = games[chat_id]
    if len(game["alive"]) == 1:
        winner_id = game["alive"][0]
        winner_name = next(p["name"] for p in game["players"] if p["id"] == winner_id)
        await context.bot.send_message(chat_id, f"🏆 Победитель: {winner_name}")
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
