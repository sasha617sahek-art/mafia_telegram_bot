import asyncio
import random
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

TOKEN = os.environ.get("BOT_TOKEN")

# Игровое состояние
games = {}

ROLES = ["маньяк", "защитник", "наблюдатель", "везунчик", "игрок"]

# ===== Start Game =====
async def game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    games[chat_id] = {
        "players": {},
        "alive": [],
        "roles": {},
        "state": "lobby",
        "night": 0,
        "muted": set(),
        "effects": {}
    }
    keyboard = [[InlineKeyboardButton("➕ Присоединиться", callback_data="join")]]

    await update.message.reply_text(
        "🎮 Новая игра!\n\nИгроки: 0/20\n⏳ До старта 60 сек",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    await asyncio.sleep(60)
    await start_game(chat_id, context)

# ===== Join =====
async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    chat_id = query.message.chat.id
    user = query.from_user

    if chat_id not in games:
        return

    game = games[chat_id]
    if user.id not in game["players"]:
        name = user.username if user.username else user.first_name
        game["players"][user.id] = name

    players_text = "\n".join([f"- {name}" for name in game["players"].values()])

    await query.edit_message_text(
        f"👥 Игроки: {len(game['players'])}/20\n\n{players_text}",
        reply_markup=query.message.reply_markup
    )

# ===== Start the actual game =====
async def start_game(chat_id, context):
    game = games.get(chat_id)
    if not game or len(game["players"]) < 2:
        await context.bot.send_message(chat_id, "Недостаточно игроков для начала игры.")
        return

    game["alive"] = list(game["players"].keys())
    game["night"] = 1

    # Назначаем роли
    for pid in game["players"]:
        game["roles"][pid] = random.choice(ROLES)

    roles_text = "\n".join([f"{game['players'][pid]} → {game['roles'][pid]}" for pid in game["players"]])
    await context.bot.send_message(chat_id, f"🎭 Роли назначены!\n\n{roles_text}")

    await context.bot.send_message(chat_id, f"🌙 Ночь {game['night']} наступила...")
    await asyncio.sleep(3)
    await night_round(chat_id, context)

# ===== Night round =====
async def night_round(chat_id, context):
    game = games[chat_id]
    if len(game["alive"]) <= 1:
        await end_game(chat_id, context)
        return

    p1, p2 = random.sample(game["alive"], 2)
    game["current"] = {"attacker": p1, "target": p2, "action": None, "defense": None}

    kb1 = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔪 Убить", callback_data="kill")],
        [InlineKeyboardButton("💋 Поцеловать", callback_data="kiss")],
        [InlineKeyboardButton("🤗 Обнять", callback_data="hug")],
        [InlineKeyboardButton("🍷 Напоить", callback_data="drink")]
    ])
    kb2 = InlineKeyboardMarkup([
        [InlineKeyboardButton("😴 Спать", callback_data="sleep")],
        [InlineKeyboardButton("👀 Проснуться", callback_data="wake")],
        [InlineKeyboardButton("🚨 СОС", callback_data="sos")]
    ])

    try:
        await context.bot.send_message(p1, "Ты выбрал цель. Что делать?", reply_markup=kb1)
        await context.bot.send_message(p2, "Ты слышишь шум...", reply_markup=kb2)
    except Exception as e:
        print(f"Ошибка отправки сообщений: {e}")

    await asyncio.sleep(15)
    await resolve_night(chat_id, context)

# ===== Handle actions =====
async def action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user.id

    for game in games.values():
        if "current" not in game:
            continue
        if user == game["current"]["attacker"]:
            game["current"]["action"] = query.data
        elif user == game["current"]["target"]:
            game["current"]["defense"] = query.data

# ===== Resolve night =====
async def resolve_night(chat_id, context):
    game = games[chat_id]
    cur = game["current"]

    attacker = cur["attacker"]
    target = cur["target"]
    action = cur["action"]
    defense = cur["defense"]

    attacker_name = game["players"].get(attacker, str(attacker))
    target_name = game["players"].get(target, str(target))
    attacker_role = game["roles"].get(attacker, "игрок")
    target_role = game["roles"].get(target, "игрок")

    text = f"🌅 Утро после ночи {game['night']}...\n\n"

    # Логика действий с учетом ролей
    if action == "kill":
        chance = 50
        if attacker_role == "маньяк":
            chance += 20
        if target_role == "везунчик":
            chance -= 50
        if defense == "sos":
            if attacker in game["alive"]:
                game["alive"].remove(attacker)
            text += f"🚨 {attacker_name} был пойман ночью!\n"
        else:
            if random.randint(1,100) <= chance:
                if target in game["alive"]:
                    game["alive"].remove(target)
                text += f"💀 {target_name} погиб...\n"
            else:
                text += f"🍀 {target_name} чудом выжил!\n"

    elif action == "drink":
        game["muted"].add(target)
        text += f"🍷 {target_name} был напоен и будет молчать днем...\n"

    elif action == "kiss":
        if random.randint(1,100) <= 70:
            if target in game["alive"]:
                game["alive"].remove(target)
            text += f"💋 {target_name} погиб от поцелуя...\n"
        else:
            game["muted"].add(target)
            text += f"💋 {target_name} зачарован и молчит днем...\n"

    elif action == "hug":
        if random.randint(1,100) <= 50:
            if target in game["alive"]:
                game["alive"].remove(target)
            text += f"🤗 {target_name} погиб от объятий...\n"
        else:
            game["effects"][target] = "испуган"
            text += f"🤗 {target_name} испуган и слабее защищается днем...\n"

    else:
        text += "🌙 Ночь прошла без событий...\n"

    # Наблюдатель видит атакующего
    for pid, role in game["roles"].items():
        if role == "наблюдатель" and pid in game["alive"]:
            await context.bot.send_message(pid, f"👀 Ты видел, что {attacker_name} выходил ночью...")

    # Список живых
    alive_names = []
    for pid in game["alive"]:
        name = game["players"][pid]
        if pid in game["muted"]:
            alive_names.append(f"{name} 🤐 (молчит)")
        else:
            alive_names.append(name)

    text += f"\n👥 Живые игроки ({len(alive_names)}):\n" + "\n".join([f"- {n}" for n in alive_names])

    await context.bot.send_message(chat_id, text)
    await asyncio.sleep(3)

    # День
    await day_phase(chat_id, context)

    # Следующая ночь
    game["night"] += 1
    await context.bot.send_message(chat_id, f"🌙 Ночь {game['night']} наступила...")
    await night_round(chat_id, context)

# ===== Day phase =====
async def day_phase(chat_id, context):
    game = games[chat_id]
    alive_names = []
    for pid in game["alive"]:
        name = game["players"][pid]
        if pid in game["muted"]:
            alive_names.append(f"{name} 🤐 (молчит)")
        else:
            alive_names.append(name)

    text = f"☀️ День наступил!\n\n👥 Живые игроки:\n" + "\n".join([f"- {n}" for n in alive_names])
    await context.bot.send_message(chat_id, text)

    # После дня снимаем эффект
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # Команда /game
    app.add_handler(CommandHandler("game", game))
    # Кнопка "Присоединиться"
    app.add_handler(CallbackQueryHandler(join, pattern="join"))
    # Действия ночью
    app.add_handler(CallbackQueryHandler(action))

    print("✅ Bot started and polling...")
    app.run_polling()

if __name__ == "__main__":
    main()
