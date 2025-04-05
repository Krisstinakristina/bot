# -*- coding: utf-8 -*-
import telebot
import os
from dotenv import load_dotenv
from telebot import types
from openai import OpenAI
import json
import yookassa
from datetime import datetime
import pytesseract
from PIL import Image
import io
import re

load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
YOOKASSA_SHOP_ID = os.getenv('YOOKASSA_SHOP_ID')
YOOKASSA_SECRET_KEY = os.getenv('YOOKASSA_SECRET_KEY')
ADMIN_ID = os.getenv('ADMIN_ID', '')

bot = telebot.TeleBot(BOT_TOKEN)

# Константы
SUBSCRIPTION_PRICE = 200
TOKENS_PER_PAYMENT = 25000

# Данные пользователей
user_data_storage = {}

genres = {
    'A': 'Мифология',
    'B': 'Приключение',
    'C': 'Фантастика',
    'D': 'Детектив',
    'E': 'Сказка'
}

morals = {
    '1': 'Доброта',
    '2': 'Честность',
    '3': 'Терпеливость',
    '4': 'Семья важна',
    '5': 'Благодарность'
}

def get_user_data(user_id):
    if user_id not in user_data_storage:
        user_data_storage[user_id] = {
            'user_id': user_id,
            'subscription_type': 'none',
            'available_tokens': 0,
            'subscription_expiry_date': None,
            'pending_payment_code': None
        }
    return user_data_storage[user_id]

def update_user_data(user_id, data):
    user_data_storage[user_id] = data

client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

def generate_payment_code(user_id):
    return f"SKZ-{user_id}-{datetime.now().strftime('%d%H')}"

# Улучшенная функция нормализации текста
def normalize_text(text):
    text = text.lower()
    text = re.sub(r'[^а-яa-z0-9\s]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

# Улучшенная функция проверки платежа
def validate_payment(text, payment_code, amount):
    normalized_text = normalize_text(text)
    code_pattern = re.escape(payment_code.lower())
    amount_pattern = r'200(\s|р|руб|рублей)'
    date_pattern = r'\d{1,2}\s?[\.\/]\s?\d{1,2}\s?[\.\/]\s?\d{2,4}'
    
    code_found = re.search(code_pattern, normalized_text) is not None
    amount_found = re.search(amount_pattern, normalized_text) is not None
    date_found = re.search(date_pattern, text) is not None  # Ищем в оригинальном тексте
    
    return code_found and amount_found and date_found

@bot.message_handler(commands=['start'])
def start(message):
    user = get_user_data(message.from_user.id)
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    if user['available_tokens'] <= 0:
        markup.add(types.KeyboardButton("💰 Купить подписку"))
    else:
        markup.add(types.KeyboardButton("📖 Создать сказку"))
    
    bot.send_message(
        message.chat.id,
        f"👋 Привет! Я бот-сказочник. За {SUBSCRIPTION_PRICE}₽ ты получишь {TOKENS_PER_PAYMENT} токенов (~20-25 сказок).\n\nВыбери действие:",
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: message.text == "📖 Создать сказку")
def create_story(message):
    user = get_user_data(message.from_user.id)
    if user['available_tokens'] <= 0:
        bot.send_message(message.chat.id, "❌ У вас закончились токены. Купите подписку.")
        return
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = [types.KeyboardButton(name) for name in genres.values()]
    markup.add(*buttons)
    
    bot.send_message(message.chat.id, "Выберите жанр сказки:", reply_markup=markup)
    bot.register_next_step_handler(message, process_genre_selection)

def process_genre_selection(message):
    if message.text not in genres.values():
        bot.send_message(message.chat.id, "❌ Пожалуйста, выберите жанр из списка.")
        return create_story(message)
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = [types.KeyboardButton(name) for name in morals.values()]
    markup.add(*buttons)
    
    bot.send_message(message.chat.id, "Теперь выберите мораль:", reply_markup=markup)
    bot.register_next_step_handler(message, process_moral_selection, selected_genre=message.text)

def process_moral_selection(message, selected_genre):
    if message.text not in morals.values():
        bot.send_message(message.chat.id, "❌ Пожалуйста, выберите мораль из списка.")
        return create_story(message)
    
    msg = bot.send_message(message.chat.id, "🧙 Введите имена героев через запятую и желаемое действие (например: 'Иван, Марья, найти волшебный цветок'):")
    bot.register_next_step_handler(msg, generate_fairy_tale, genre=selected_genre, moral=message.text)

def generate_fairy_tale(message, genre, moral):
    characters_and_action = message.text
    
    try:
        prompt = f"Напиши {genre.lower()} сказку с героями: {characters_and_action}. "
        prompt += f"Мораль сказки: '{moral}'. "
        prompt += "Используй простой язык, 3-5 абзацев."
        
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}]
        )
        
        user = get_user_data(message.from_user.id)
        user['available_tokens'] -= 1000
        update_user_data(message.from_user.id, user)
        
        bot.send_message(message.chat.id, response.choices[0].message.content)
        
    except Exception as e:
        bot.send_message(message.chat.id, f"⚠️ Ошибка при генерации: {str(e)}")
        print(f"Generation error: {e}")

@bot.message_handler(func=lambda message: message.text == "💰 Купить подписку")
def buy_subscription(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    
    payment_code = generate_payment_code(user_id)
    user['pending_payment_code'] = payment_code
    update_user_data(user_id, user)
    
    instructions = (
        f"📌 Для оплаты подписки:\n"
        f"1. Переведите {SUBSCRIPTION_PRICE}₽ на ЮMoney\n"
        f"2. В комментарии укажите: {payment_code}\n"
        f"3. Пришлите скриншот чека\n\n"
        f"❗ Важно: код {payment_code} должен быть в комментарии\n"
        f"❗ Дата должна быть сегодняшней ({datetime.now().strftime('%d.%m.%Y')})"
    )
    
    bot.send_message(
        message.chat.id,
        instructions,
        reply_markup=types.ForceReply(selective=False)
    )

@bot.message_handler(content_types=['photo'])
def handle_payment_screenshot(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    
    if not user.get('pending_payment_code'):
        bot.reply_to(message, "❌ Сначала запросите подписку через команду /start")
        return
    
    try:
        # Получаем и обрабатываем изображение
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        img = Image.open(io.BytesIO(downloaded_file))
        
        # Улучшенное распознавание текста
        custom_config = r'--oem 3 --psm 6 -l rus+eng'
        try:
            text = pytesseract.image_to_string(img, config=custom_config)
            print(f"Распознанный текст: {text}")  # Для отладки
        except Exception as e:
            bot.reply_to(message, "❌ Ошибка распознавания текста. Попробуйте более четкий скриншот.")
            print(f"OCR Error: {e}")
            return
        
        # Проверка платежа с улучшенной валидацией
        if validate_payment(text, user['pending_payment_code'], SUBSCRIPTION_PRICE):
            user['available_tokens'] += TOKENS_PER_PAYMENT
            user['pending_payment_code'] = None
            update_user_data(user_id, user)
            
            bot.reply_to(
                message,
                f"✅ Оплата подтверждена! Ваш баланс: {user['available_tokens']} токенов."
            )
            
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.add(types.KeyboardButton("📖 Создать сказку"))
            bot.send_message(
                message.chat.id,
                "Выберите действие:",
                reply_markup=markup
            )
            
            if ADMIN_ID:
                bot.send_message(
                    ADMIN_ID,
                    f"Новая подписка от @{message.from_user.username}\n"
                    f"ID: {user_id}\n"
                    f"Токенов: {user['available_tokens']}"
                )
        else:
            bot.reply_to(
                message,
                f"❌ Не удалось подтвердить платеж. Проверьте:\n"
                f"- Код {user['pending_payment_code']}\n"
                f"- Сумма {SUBSCRIPTION_PRICE}₽\n"
                f"- Дата {datetime.now().strftime('%d.%m.%Y')}\n"
                f"- Скриншот должен содержать все эти данные"
            )
            
    except Exception as e:
        bot.reply_to(message, "⚠️ Ошибка обработки скриншота. Попробуйте еще раз.")
        print(f"Screenshot Error: {e}")

@bot.message_handler(commands=['tesseract_test'])
def test_tesseract(message):
    try:
        version = pytesseract.get_tesseract_version()
        bot.reply_to(message, f"✅ Tesseract работает! Версия: {version}")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {str(e)}\nTesseract не установлен!")

if __name__ == '__main__':
    print("Бот запущен в режиме long-polling...")
    bot.infinity_polling()