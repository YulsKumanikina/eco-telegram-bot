# =========================================================================
# ===           ФИНАЛЬНАЯ ВЕРСИЯ С ПОДПИСКОЙ НА СОВЕТЫ                ===
# =========================================================================

import telebot
from telebot import types 
import pandas as pd
import json
import re
from typing import List, Tuple
from gigachat.client import GigaChatSyncClient
from gigachat.models import Chat, Messages, MessagesRole
import random
from datetime import datetime, date

# --- НОВЫЕ ИМПОРТЫ ДЛЯ ЧЕЛЛЕНДЖЕЙ ---
import db_manager as db
import challenges_data as challenges
from apscheduler.schedulers.background import BackgroundScheduler

# ... (все ваши глобальные настройки и словари остаются без изменений) ...
user_context = {}
STOP_WORDS = set(['и', 'в', 'во', 'не', 'что', 'он', 'на', 'я', 'с', 'со', 'как', 'а', 'то', 'все', 'она', 'так', 'его', 'но', 'да', 'ты', 'к', 'у', 'же', 'вы', 'за', 'бы', 'по', 'только', 'ее', 'мне', 'было', 'вот', 'от', 'меня', 'еще', 'нет', 'о', 'из', 'ему', 'теперь', 'когда', 'даже', 'ну', 'вдруг', 'ли', 'если', 'уже', 'или', 'ни', 'быть', 'был', 'него', 'до', 'вас', 'нибудь', 'опять', 'уж', 'вам', 'ведь', 'там', 'потом', 'себя', 'ничего', 'ей', 'может', 'они', 'тут', 'где', 'есть', 'надо', 'ней', 'для', 'мы', 'тебя', 'их', 'чем', 'была', 'сам', 'чтоб', 'без', 'будто', 'чего', 'раз', 'тоже', 'себе', 'под', 'будет', 'ж', 'тогда', 'кто', 'этот', 'того', 'потому', 'этого', 'какой', 'совсем', 'ним', 'здесь', 'этом', 'один', 'почти', 'мой', 'тем', 'чтобы', 'нее', 'сейчас', 'были', 'куда', 'зачем', 'всех', 'никогда', 'можно', 'при', 'наконец', 'два', 'об', 'другой', 'хоть', 'после', 'над', 'больше', 'тот', 'через', 'эти', 'нас', 'про', 'всего', 'них', 'какая', 'много', 'разве', 'три', 'эту', 'моя', 'впрочем', 'хорошо', 'свою', 'этой', 'перед', 'иногда', 'лучше', 'чуть', 'том', 'нельзя', 'такой', 'им', 'более', 'всегда', 'конечно', 'всю', 'между', 'такое', 'это'])
SEARCH_TRIGGERS = ['куда сдать', 'где принимают', 'пункты приема', 'пункты приёма', 'адреса', 'адрес', 'найди', 'найти', 'где', 'куда']
JUNK_PREFIXES = ['а', 'в', 'и', 'с', 'к', 'по']

# --- КОНФИГУРАЦИЯ ---
try:
    from config import (TELEGRAM_TOKEN, GIGACHAT_API_KEY, KNOLEDGE_BASE_PATH, RECYCLING_POINTS_PATH, INTERESTING_FACTS_PATH, FALLBACK_POINTS)
except ImportError:
    print("Ошибка: не удалось найти файл config.py или необходимые переменные в нем.")
    exit()

ECO_TIPS_PATH = 'data/eco_tips.json' # Путь к новому файлу с советами
MAX_POINTS_TO_SHOW = 3

# --- ИНИЦИАЛИЗАЦИЯ ---
bot = telebot.TeleBot(TELEGRAM_TOKEN)
try:
    giga = GigaChatSyncClient(credentials=GIGACHAT_API_KEY, verify_ssl_certs=False)
    print("GigaChat успешно инициализирован.")
except Exception as e: print(f"Не удалось инициализировать GigaChat: {e}"); giga = None

db.init_db()
print("Бот (в режиме polling) запущен...")

# --- ЗАГРУЗКА ДАННЫХ ---
def load_data() -> Tuple[pd.DataFrame, List[dict], List[str], List[str]]:
    try:
        points = pd.read_csv(RECYCLING_POINTS_PATH)
        with open(KNOLEDGE_BASE_PATH, 'r', encoding='utf-8') as f: knowledge = json.load(f)
        with open(INTERESTING_FACTS_PATH, 'r', encoding='utf-8') as f: facts = json.load(f)
        with open(ECO_TIPS_PATH, 'r', encoding='utf-8') as f: tips = json.load(f) # Загружаем советы
        print("Данные успешно загружены.")
        return points, knowledge, facts, tips
    except Exception as e: print(f"Ошибка загрузки данных: {e}"); return pd.DataFrame(), [], [], []
points_df, knowledge_base, interesting_facts, eco_tips = load_data()

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
# ... (все ваши вспомогательные функции, кроме create_main_keyboard, остаются без изменений) ...
def escape_markdown(text: str) -> str:
    return re.sub(f'([{re.escape(r"_*[]()~`>#+-=|{}.!")}])', r'\\\1', text)

def create_main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    # Добавляем 5 кнопок. 5-я будет в отдельном ряду.
    markup.add(
        types.KeyboardButton('Найти пункт ♻️'), 
        types.KeyboardButton('Задать вопрос 🧠'),
        types.KeyboardButton('Эко-челлендж 💪'), 
        types.KeyboardButton('Эко-факт ✨')
    )
    markup.add(types.KeyboardButton('Совет дня 💡')) # Новая кнопка
    return markup
#... (остальные функции extract_entities, find_recycling_points и т.д. без изменений)

# --- ФУНКЦИИ ДЛЯ ПЛАНИРОВЩИКА ---
def check_challenges():
    # ... (эта функция без изменений) ...
    pass

# НОВАЯ ФУНКЦИЯ ДЛЯ РАССЫЛКИ СОВЕТОВ
def send_daily_tip():
    print(f"[{datetime.now()}] Запущена рассылка эко-советов...")
    subscribers = db.get_all_subscribers()
    if not subscribers or not eco_tips:
        print("Нет подписчиков или советов для рассылки.")
        return
        
    tip_of_the_day = random.choice(eco_tips)
    message = f"💡 *Эко-совет дня:*\n\n{escape_markdown(tip_of_the_day)}"
    
    for user_id in subscribers:
        try:
            bot.send_message(user_id, message, parse_mode='MarkdownV2')
        except Exception as e:
            # Если пользователь заблокировал бота, просто удаляем его из подписки
            if 'bot was blocked by the user' in str(e):
                print(f"Пользователь {user_id} заблокировал бота. Удаляем из подписки.")
                db.remove_subscriber(user_id)
            else:
                print(f"Не удалось отправить совет пользователю {user_id}: {e}")
    print(f"Рассылка завершена. Отправлено {len(subscribers)} пользователям.")

# --- ОБРАБОТЧИКИ TELEGRAM ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "♻️ *Привет\\! Я ваш эко\\-помощник\\.*\n\nИспользуйте кнопки ниже, чтобы начать\\!", parse_mode='MarkdownV2', reply_markup=create_main_keyboard())

# --- ОБРАБОТЧИКИ ДЛЯ ЧЕЛЛЕНДЖЕЙ И СОВЕТОВ ---
@bot.message_handler(func=lambda message: message.text == 'Эко-челлендж 💪')
def handle_challenges_button(message):
    # ... (этот обработчик без изменений) ...
    pass

# НОВЫЙ ОБРАБОТЧИК КНОПКИ "Совет дня"
@bot.message_handler(func=lambda message: message.text == 'Совет дня 💡')
def handle_tip_button(message):
    user_id = message.from_user.id
    markup = types.InlineKeyboardMarkup()
    if db.is_subscribed(user_id):
        text = "Вы уже подписаны на ежедневную рассылку эко-советов. Хотите отписаться?"
        markup.add(types.InlineKeyboardButton("Отписаться 🔕", callback_data="unsubscribe_tip"))
    else:
        text = "Хотите ежедневно получать один полезный совет об экологии и осознанном потреблении?"
        markup.add(types.InlineKeyboardButton("Подписаться 🔔", callback_data="subscribe_tip"))
    bot.send_message(user_id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in ['subscribe_tip', 'unsubscribe_tip'])
def callback_subscription(call):
    user_id = call.from_user.id
    if call.data == 'subscribe_tip':
        db.add_subscriber(user_id)
        bot.edit_message_text("Отлично! Вы подписались на 'Эко-совет дня'. Ждите первое сообщение завтра утром.", call.message.chat.id, call.message.message_id)
    elif call.data == 'unsubscribe_tip':
        db.remove_subscriber(user_id)
        bot.edit_message_text("Вы отписались от рассылки. Если захотите вернуться, просто нажмите кнопку в меню снова.", call.message.chat.id, call.message.message_id)

# ... (все остальные обработчики callback_query_handler и handle_text остаются без изменений) ...
# ...

# --- ЗАПУСК БОТА И ПЛАНИРОВЩИКА ---
if __name__ == "__main__":
    scheduler = BackgroundScheduler()
    # Задача 1: Проверка челленджей в 10:00
    scheduler.add_job(check_challenges, 'cron', hour=10)
    # ЗАДАЧА 2: Рассылка советов в 11:00
    scheduler.add_job(send_daily_tip, 'cron', hour=11)
    scheduler.start()
    print("Планировщик для проверки челленджей и рассылки советов запущен.")
    
    try:
        bot.polling(none_stop=True)
    except Exception as e:
        print(f"Бот остановился из-за ошибки: {e}")
        scheduler.shutdown()