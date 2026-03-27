        "oil": 0,
            "diesel": 0,
            "gas92": 0,
            "gas95": 0,
            "money": 500,
            "well_lvl": 1,
            "equipment": {"diesel": None, "gas92": None, "gas95": None}
        }

# ====== Команды ======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    nick = update.effective_user.username or update.effective_user.first_name
    init_player(user_id, nick)
    await update.message.reply_text(f"Привет, {nick}! Добро пожаловать в нефтяной магнат.\n"
                                    "Используй /status чтобы проверить свои ресурсы.")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in players:
        await start(update, context)
        return
    p = players[user_id]
    eq = p['equipment']
    await update.message.reply_text(
        f"🛢 Скважина: {p['well_lvl']} уровень\n"
        f"Нефть: {p['oil']} баррелей\n"
        f"Дизель: {p['diesel']} л\n"
        f"Бензин 92: {p['gas92']} л\n"
        f"Бензин 95: {p['gas95']} л\n"
        f"Деньги: {p['money']} 💰\n"
        f"Оборудование:\n"
        f"Дизель: {eq['diesel']}\n"
        f"Бензин 92: {eq['gas92']}\n"
        f"Бензин 95: {eq['gas95']}"
    )

# ====== Добыча нефти ======
async def mine(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in players:
        await start(update, context)
        return
    p = players[user_id]
    oil_gain = 10 + (p['well_lvl'] - 1) * 5
    p['oil'] += oil_gain
    await update.message.reply_text(f"Скважина добыла {oil_gain} баррелей нефти! Всего нефти: {p['o
