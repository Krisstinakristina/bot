# -*- coding: utf-8 -*-
import telebot
import os
from dotenv import load_dotenv
from telebot import types
from openai import OpenAI  # Import OpenAI library
import json

load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')  # Get DeepSeek API key from .env

bot = telebot.TeleBot(BOT_TOKEN)

genres = {
    'A': 'Мифология',
    'B': 'Приключение',
    'C': 'Фантастика',
    'D': 'Приключение',
    'E': 'Сказка'
}

morals = {
    '1': 'Будь добрым',
    '2': 'Будь храбрым',
    '3': 'Будь честным',
    '4': 'Будь терпеливым',
    '5': 'Будь благодарным'
}

user_data = {}

# Initialize OpenAI client
client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

def generate_deepseek_response(prompt, genre, moral):
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "Ты - добрый помощник, который пишет сказки."},
                {"role": "user", "content": f"Напиши сказку в жанре {genre} с моралью {moral} про: {prompt}"},
            ],
            stream=False
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Ошибка при запросе к DeepSeek API: {e}"


@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    button = types.KeyboardButton("Начать создание истории!")
    markup.add(button)
    bot.reply_to(message, "Привет, мир!", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "Начать создание истории!")
def start_story(message):
    genre_selection(message)

@bot.message_handler(commands=['genres'])
def genre_selection(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    for key, value in genres.items():
        markup.add(types.InlineKeyboardButton(text=f"{value}", callback_data=f"genre_{key}"))
    bot.send_message(message.chat.id, "Выберите жанр:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("genre_"))
def moral_selection(call):
    genre_key = call.data.split("_")[1]
    user_data[call.message.chat.id] = {'genre': genres[genre_key]}
    markup = types.InlineKeyboardMarkup(row_width=2)
    for key, value in morals.items():
        markup.add(types.InlineKeyboardButton(text=f"{value}", callback_data=f"moral_{key}"))
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=f"Вы выбрали жанр: {genres[genre_key]}. Выберите мораль:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("moral_"))
def process_moral(call):
    moral_key = call.data.split("_")[1]
    user_data[call.message.chat.id]['moral'] = morals[moral_key]
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=f"Вы выбрали жанр: {user_data[call.message.chat.id]['genre']} и мораль: {user_data[call.message.chat.id]['moral']}. Теперь отправьте мне персонажей через запятую и опишите действие!", reply_markup=None)

@bot.message_handler(func=lambda message: True)
def story_generation(message):
    if message.chat.id in user_data and 'genre' in user_data[message.chat.id] and 'moral' in user_data[message.chat.id]:
        genre = user_data[message.chat.id]['genre']
        moral = user_data[message.chat.id]['moral']
        prompt = message.text
        response = generate_deepseek_response(prompt, genre=genre, moral=moral)
        bot.reply_to(message, response)
    else:
        bot.reply_to(message, "Пожалуйста, начните с выбора жанра и морали, используя команду /start.")

bot.infinity_polling()