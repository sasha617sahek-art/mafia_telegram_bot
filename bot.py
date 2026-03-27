import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

players = {}

def init_player(user_id, nick):
    if user_id not in players:
        players[user_id] = {
            "nick": nick,
            "oil": 0,
            "diesel": 0,
            "gas92": 0,
            "gas95": 0,
            "money": 500,
            "well_lvl": 1,
            "equipment": {"diesel": None, "gas92": None, "gas95": None}
        }

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    nick = update.effective_user.username or update.effective_user.first_name
    init_player(user_id, nick)
    await update.message.reply_text(
        f"Привет, {nick}! Добро пожаловать в нефтяной магнат.\n"
        "Используй /status чтобы проверить свои ресурсы."
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in players:
        await update.message.reply_text("Сначала напиши /start чтобы начать игру!")
        return
    p = players[user_id]
    await update.message.reply_text(
        f"🛢 Скважина: {p['well_lvl']} уровень\n"
        f"Нефть: {p['oil']}\n"
        f"Дизель: {p['diesel']}\n"
        f"Бензин 92: {p['gas92']}\n"
        f"Бензин 95: {p['gas95']}\n"
        f"Деньги: {p['money']}"
    )

if __name__ == "__main__":
    TOKEN = os.environ.get("BOT_TOKEN")
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.run_polling()import random
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler

# ====== Настройки оборудования ======
equipment_stats = {
    "diesel": {"мини": 8, "среднее": 15, "большое": 25},
    "gas92": {"мини": 8, "среднее": 15, "большое": 25},
    "gas95": {"мини": 8, "среднее": 15, "большое": 25},
}

# ====== Добыча нефти ======
async def mine(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in players:
        await update.message.reply_text("Сначала напиши /start чтобы начать игру!")
        return
    p = players[user_id]
    oil_gain = 10 + (p['well_lvl'] - 1) * 5
    p['oil'] += oil_gain
    await update.message.reply_text(f"Скважина добыла {oil_gain} баррелей нефти! Всего нефти: {p['oil']}")

# ====== Переработка нефти ======
async def process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in players:
        await update.message.reply_text("Сначала напиши /start чтобы начать игру!")
        return
    p = players[user_id]
    msg = ""
    for fuel, eq in p['equipment'].items():
        if eq and p['oil'] > 0:
            rate = equipment_stats[fuel][eq]
            used_oil = min(p['oil'], 10)
            produced = int(rate * used_oil / 10)  # пропорционально использованной нефти
            p['oil'] -= used_oil
            p[fuel] += produced
            msg += f"{fuel.capitalize()}: переработано {produced} л (использовано {used_oil} баррелей нефти)\n"
    if msg == "":
        msg = "У тебя нет оборудования или нефти для переработки."
    await update.message.reply_text(msg)# ====== Магазин оборудования ======
equipment_cost = {
    "мини": 100,
    "среднее": 200,
    "большое": 400
}

async def shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in players:
        await update.message.reply_text("Сначала напиши /start чтобы начать игру!")
        return
    p = players[user_id]
    buttons = []
    for fuel in ["diesel", "gas92", "gas95"]:
        for level in ["мини", "среднее", "большое"]:
            buttons.append([InlineKeyboardButton(f"{fuel.capitalize()} {level} ({equipment_cost[level]}💰)", callback_data=f"buy_{fuel}_{level}")])
    markup = InlineKeyboardMarkup(buttons)
    await update.message.reply_text("Магазин оборудования:", reply_markup=markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if user_id not in players:
        await query.edit_message_text("Сначала напиши /start чтобы начать игру!")
        return
    p = players[user_id]
    data = query.data

    if data.startswith("buy_"):
        _, fuel, level = data.split("_")
        if p['equipment'][fuel]:
            await query.edit_message_text(f"У тебя уже есть оборудование для {fuel} ({p['equipment'][fuel]}). Продай его, чтобы купить новое.")
            return
        cost = equipment_cost[level]
        if p['money'] < cost:
            await query.edit_message_text("Недостаточно денег!")
            return
        p['money'] -= cost
        p['equipment'][fuel] = level
        await query.edit_message_text(f"Ты купил {fuel} оборудование {level}!")# ====== Продажа топлива NPC ======
fuel_prices = {"diesel": 5, "gas92": 4, "gas95": 6}  # 💰 за литр

async def sell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in players:
        await update.message.reply_text("Сначала напиши /start чтобы начать игру!")
        return
    p = players[user_id]
    args = context.args
    if len(args) != 2:
        await update.message.reply_text("Используй: /sell <тип топлива> <кол-во>")
        return
    fuel, amount_str = args
    if not amount_str.isdigit() or int(amount_str) <= 0:
        await update.message.reply_text("Количество должно быть положительным числом!")
        return
    amount = int(amount_str)
    if fuel not in ["diesel", "gas92", "gas95"]:
        await update.message.reply_text("Неверный тип топлива!")
        return
    if p[fuel] < amount:
        await update.message.reply_text(f"У тебя нет столько {fuel}.")
        return
    p[fuel] -= amount
    earned = amount * fuel_prices[fuel]
    p['money'] += earned
    await update.message.reply_text(f"Продано {amount} л {fuel} за {earned}💰")

# ====== Передача денег другому игроку ======
async def pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in players:
        await update.message.reply_text("Сначала напиши /start чтобы начать игру!")
        return
    p = players[user_id]
    args = context.args
    if len(args) != 2:
        await update.message.reply_text("Используй: /pay <ник игрока> <сумма>")
        return
    target_nick, amount_str = args
    if not amount_str.isdigit() or int(amount_str) <= 0:
        await update.message.reply_text("Сумма должна быть положительным числом!")
        return
    amount = int(amount_str)
    if p['money'] < amount:
        await update.message.reply_text("Недостаточно денег!")
        return
    target = None
    for uid, pl in players.items():
        if pl['nick'] == target_nick:
            target = pl
            break
    if not target:
        await update.message.reply_text("Игрок не найден!")
        return
    p['money'] -= amount
    target['money'] += amount
    await update.message.reply_text(f"Ты перевёл {amount}💰 игроку {target_nick}!")# ====== Прокачка скважины ======
upgrade_costs = {1: {"oil": 50, "money": 100}, 2: {"oil": 100, "money": 200}}

async def upgrade_well(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in players:
        await update.message.reply_text("Сначала напиши /start чтобы начать игру!")
        return
    p = players[user_id]
    current_lvl = p['well_lvl']
    if current_lvl >= 3:
        await update.message.reply_text("Скважина уже максимального уровня!")
        return
    cost = upgrade_costs[current_lvl]
    if p['oil'] < cost['oil'] or p['money'] < cost['money']:
        await update.message.reply_text(f"Для прокачки нужно {cost['oil']} нефти и {cost['money']}💰")
        return
    p['oil'] -= cost['oil']
    p['money'] -= cost['money']
    p['well_lvl'] += 1
    await update.message.reply_text(f"Скважина прокачана до уровня {p['well_lvl']}!\nТеперь добыча нефти выше.")# ====== Команда помощи ======
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🛢 *Нефтяной Магнат — Команды*\n\n"
        "/start — регистрация и приветствие\n"
        "/status — показать ресурсы и деньги\n"
        "/mine — добыть нефть\n"
        "/process — переработать нефть в дизель или бензин\n"
        "/shop — открыть магазин оборудования\n"
        "/sell <топливо> <кол-во> — продать топливо NPC\n"
        "/pay <ник> <сумма> — передать деньги другому игроку\n"
        "/upgrade_well — прокачать скважину (увеличивает добычу нефти)\n"
        "/help — показать это сообщение"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")# ====== Продажа и замена оборудования ======
async def sell_equipment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in players:
        await update.message.reply_text("Сначала напиши /start чтобы начать игру!")
        return
    p = players[user_id]
    args = context.args
    if len(args) != 1:
        await update.message.reply_text("Используй: /sell_eq <тип топлива>")
        return
    fuel = args[0].lower()
    if fuel not in ["diesel", "gas92", "gas95"]:
        await update.message.reply_text("Неверный тип топлива!")
        return
    if not p['equipment'][fuel]:
        await update.message.reply_text(f"У тебя нет оборудования для {fuel}")
        return
    level = p['equipment'][fuel]
    sell_price = equipment_cost[level] // 2
    p['money'] += sell_price
    p['equipment'][fuel] = None
    await update.message.reply_text(f"Ты продал оборудование {fuel} {level} за {sell_price}💰")# ====== Подключение команд ======
app.add_handler(CommandHandler("start", start))           # ← не забудь
app.add_handler(CommandHandler("status", status))         # ← не забудь
app.add_handler(CommandHandler("mine", mine))
app.add_handler(CommandHandler("process", process))
app.add_handler(CommandHandler("shop", shop))
app.add_handler(CommandHandler("sell", sell))
app.add_handler(CommandHandler("pay", pay))
app.add_handler(CommandHandler("upgrade_well", upgrade_well))
app.add_handler(CommandHandler("help", help_command))
app.add_handler(CommandHandler("sell_eq", sell_equipment))
app.add_handler(CallbackQueryHandler(button_handler))
