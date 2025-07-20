# =========================================================================
# ===          ФИНАЛЬНАЯ ВЕРСИЯ BOT_POLLING.PY (ПОЛНЫЙ КОД)            ===
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

import db_manager as db
import challenges_data as challenges
from apscheduler.schedulers.background import BackgroundScheduler

user_context = {}
STOP_WORDS = set(['и', 'в', 'во', 'не', 'что', 'он', 'на', 'я', 'с', 'со', 'как', 'а', 'то', 'все', 'она', 'так', 'его', 'но', 'да', 'ты', 'к', 'у', 'же', 'вы', 'за', 'бы', 'по', 'только', 'ее', 'мне', 'было', 'вот', 'от', 'меня', 'еще', 'нет', 'о', 'из', 'ему', 'теперь', 'когда', 'даже', 'ну', 'вдруг', 'ли', 'если', 'уже', 'или', 'ни', 'быть', 'был', 'него', 'до', 'вас', 'нибудь', 'опять', 'уж', 'вам', 'ведь', 'там', 'потом', 'себя', 'ничего', 'ей', 'может', 'они', 'тут', 'где', 'есть', 'надо', 'ней', 'для', 'мы', 'тебя', 'их', 'чем', 'была', 'сам', 'чтоб', 'без', 'будто', 'чего', 'раз', 'тоже', 'себе', 'под', 'будет', 'ж', 'тогда', 'кто', 'этот', 'того', 'потому', 'этого', 'какой', 'совсем', 'ним', 'здесь', 'этом', 'один', 'почти', 'мой', 'тем', 'чтобы', 'нее', 'сейчас', 'были', 'куда', 'зачем', 'всех', 'никогда', 'можно', 'при', 'наконец', 'два', 'об', 'другой', 'хоть', 'после', 'над', 'больше', 'тот', 'через', 'эти', 'нас', 'про', 'всего', 'них', 'какая', 'много', 'разве', 'три', 'эту', 'моя', 'впрочем', 'хорошо', 'свою', 'этой', 'перед', 'иногда', 'лучше', 'чуть', 'том', 'нельзя', 'такой', 'им', 'более', 'всегда', 'конечно', 'всю', 'между', 'такое', 'это'])
SEARCH_TRIGGERS = ['куда сдать', 'где принимают', 'пункты приема', 'пункты приёма', 'адреса', 'адрес', 'найди', 'найти', 'где', 'куда']
JUNK_WORDS = ['а', 'в', 'и', 'с', 'к', 'по']

try:
    from config import (TELEGRAM_TOKEN, GIGACHAT_API_KEY, KNOLEDGE_BASE_PATH, 
                        RECYCLING_POINTS_PATH, INTERESTING_FACTS_PATH, 
                        ECO_TIPS_PATH, FALLBACK_POINTS)
except ImportError:
    print("Ошибка: не удалось найти файл config.py или необходимые переменные в нем.")
    exit()

MAX_POINTS_TO_SHOW = 3

bot = telebot.TeleBot(TELEGRAM_TOKEN)
try:
    giga = GigaChatSyncClient(credentials=GIGACHAT_API_KEY, verify_ssl_certs=False)
    print("GigaChat успешно инициализирован.")
except Exception as e: print(f"Не удалось инициализировать GigaChat: {e}"); giga = None

db.init_db()
print("Бот (в режиме polling) запущен...")

def load_data() -> Tuple[pd.DataFrame, List[dict], List[str], List[str]]:
    try:
        points = pd.read_csv(RECYCLING_POINTS_PATH)
        with open(KNOLEDGE_BASE_PATH, 'r', encoding='utf-8') as f: knowledge = json.load(f)
        with open(INTERESTING_FACTS_PATH, 'r', encoding='utf-8') as f: facts = json.load(f)
        with open(ECO_TIPS_PATH, 'r', encoding='utf-8') as f: tips = json.load(f)
        print("Данные успешно загружены.")
        return points, knowledge, facts, tips
    except Exception as e: print(f"Ошибка загрузки данных: {e}"); return pd.DataFrame(), [], [], []
points_df, knowledge_base, interesting_facts, eco_tips = load_data()

def escape_markdown(text: str) -> str:
    return re.sub(f'([{re.escape(r"_*[]()~`>#+-=|{}.!")}])', r'\\\1', text)

def create_main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton('Найти пункт ♻️'), types.KeyboardButton('Задать вопрос 🧠'), types.KeyboardButton('Эко-челлендж 💪'), types.KeyboardButton('Эко-факт ✨'))
    markup.add(types.KeyboardButton('Совет дня 💡'))
    return markup

def extract_entities(text: str) -> Tuple[str | None, str | None, str | None]:
    clean_text = re.sub(r'[^\w\s]', '', text).lower()
    city, material, district = None, None, None
    cities = ['воронеж', 'екатеринбург']
    for c in cities:
        if c in clean_text: city = c; break
    if city == 'воронеж':
        districts = ['советский', 'ленинский', 'коминтерновский', 'левобережный', 'железнодорожный', 'центральный']
        for d in districts:
            if d in clean_text: district = d; clean_text = clean_text.replace(d, '').replace('район', ''); break
    temp_material = clean_text
    if city: temp_material = temp_material.replace(city, '')
    for trigger in SEARCH_TRIGGERS: temp_material = temp_material.replace(trigger, '')
    words = temp_material.strip().split()
    while words and words[0] in JUNK_WORDS: words.pop(0)
    while words and words[-1] in JUNK_WORDS: words.pop(-1)
    material = ' '.join(words)
    return material, city, district

def find_recycling_points(material: str, city: str) -> Tuple[List[dict], List[str]]:
    if points_df.empty or not material or not city: return [], []
    try:
        synonym_map = {'шины': ['шин', 'покрышк', 'колес'], 'футболк': ['футболк', 'одежд', 'вещи', 'текстиль'], 'бутылк': ['бутылк', 'пэт', 'пластик'], 'пластик': ['пластик', 'пэт', 'бутылк', 'hdpe', 'пнд'], 'батарейк': ['батарейк', 'аккумулятор'], 'бумаг': ['бумаг', 'макулатур', 'картон', 'книг'], 'картон': ['картон', 'макулатур', 'бумаг'], 'книг': ['книг', 'макулатур', 'бумаг'], 'стекл': ['стекл', 'банк'], 'одежд': ['одежд', 'вещи', 'текстиль', 'футболк'], 'металл': ['металл', 'жестян', 'алюмин'], 'крышк': ['крышк'], 'техник': ['техник', 'электроника'], 'опасные отходы': ['опасные отходы', 'ртуть', 'градусник', 'лампочк', 'лампа'], 'зубные щетки': ['зубная щетка', 'зубные щетки']}
        search_terms = []
        for key in synonym_map.keys():
            if key in material: search_terms = synonym_map[key]; break
        if not search_terms: search_terms = [material]
        city_points = points_df[points_df['city'].str.lower() == city.lower()]
        valid_points = city_points.dropna(subset=['accepts'])
        pattern = '|'.join(search_terms)
        found_points = valid_points[valid_points['accepts'].str.lower().str.contains(pattern)]
        return found_points.to_dict('records'), search_terms
    except Exception as e: print(f"Ошибка поиска: {e}"); return [], []

def format_points_response(points: List[dict], header: str, search_terms: List[str], original_material: str) -> str:
    response_parts = [header]
    for idx, point in enumerate(points, 1):
        name, address, work_hours = escape_markdown(point.get('name', '')), escape_markdown(point.get('address', '')), escape_markdown(point.get('work_hours', ''))
        accepts_raw = str(point.get('accepts', ''))
        accepts_display = f"Да, включая '{escape_markdown(original_material.capitalize())}' и другое\\." if any(term in accepts_raw.lower() for term in search_terms) else escape_markdown(accepts_raw[:100] + '...' if len(accepts_raw) > 100 else accepts_raw)
        response_parts.append(f"📍 *{idx}\\. {name}*\n   *Адрес:* {address}\n   *Время работы:* {work_hours}\n   *Что принимает:* {accepts_display}")
    return "\n\n".join(response_parts)

def get_knowledge_answer(question: str) -> Tuple[str, str | None]:
    clean_question = re.sub(r'[^\w\s]', '', question.lower())
    user_words = set(clean_question.split()) - STOP_WORDS
    if not user_words: return "", None
    best_match_score = 0
    best_answer, best_context = "", None
    for item in knowledge_base:
        kb_clean_question = re.sub(r'[^\w\s]', '', item['question'].lower())
        kb_words = set(kb_clean_question.split()) - STOP_WORDS
        if not kb_words: continue
        score = len(user_words.intersection(kb_words))
        ratio = score / len(kb_words) if len(kb_words) > 0 else 0
        if score >= 2 and ratio > 0.6 and score > best_match_score:
            best_match_score, best_answer = score, item['answer']
            best_context = item.get('context_keyword')
    return (best_answer, best_context) if best_match_score >= 2 else ("", None)

def get_gigachat_answer(question: str) -> str:
    if not giga: return "Извините, модуль GigaChat не был загружен."
    system_prompt = "Твоя роль - эксперт по экологии. Отвечай на вопросы, связанные с экологией и переработкой. Твой ответ должен быть ОДНИМ, максимум двумя предложениями. Ни при каких условиях не превышай лимит в 15 слов. Категорически запрещено отвечать списками, перечислениями или поэтапными инструкциями. Если вопрос не по теме, твой стандартный отказ: 'К сожалению, я могу обсуждать только вопросы, связанные с экологией.'"
    payload = Chat(messages=[Messages(role=MessagesRole.SYSTEM, content=system_prompt), Messages(role=MessagesRole.USER, content=question)], temperature=0.6)
    try: response = giga.chat(payload); return response.choices[0].message.content
    except Exception as e: print(f"Ошибка при обращении к GigaChat: {e}"); return "Извините, произошла ошибка."

def handle_info_request(text: str) -> str | None:
    text_lower = text.lower()
    for city, point_info in FALLBACK_POINTS.items():
        if point_info['name'].lower() in text_lower:
            if 'телефон' in text_lower or 'номер' in text_lower: return f"📞 Телефон пункта '{point_info['name']}': `{escape_markdown(point_info.get('phone', 'не указан'))}`"
            if 'сайт' in text_lower: return f"🌐 Сайт пункта '{point_info['name']}': {escape_markdown(point_info.get('website', 'не указан'))}"
            if 'адрес' in text_lower: return f"📍 Адрес пункта '{point_info['name']}': {escape_markdown(point_info.get('address', 'не указан'))}"
    return None

def check_challenges():
    print(f"[{datetime.now()}] Запущена проверка челленджей...")
    active_challenges = db.get_all_active_challenges()
    for challenge in active_challenges:
        user_id, challenge_id = challenge['user_id'], challenge['challenge_id']
        start_date = date.fromisoformat(challenge['start_date'])
        challenge_info = challenges.CHALLENGES[challenge_id]
        days_passed = (date.today() - start_date).days
        if days_passed >= challenge_info['duration_days']: bot.send_message(user_id, challenge_info['end_message']); db.end_challenge(user_id); print(f"Челлендж {challenge_id} завершен для {user_id}")
        elif days_passed > 0: bot.send_message(user_id, f"День {days_passed + 1}: {challenge_info['daily_message']}"); print(f"Отправлено напоминание для {user_id}")

def send_daily_tip():
    print(f"[{datetime.now()}] Запущена рассылка эко-советов...")
    subscribers = db.get_all_subscribers()
    if not subscribers or not eco_tips: print("Нет подписчиков или советов."); return
    tip_of_the_day = random.choice(eco_tips)
    message = f"💡 *Эко-совет дня:*\n\n{escape_markdown(tip_of_the_day)}"
    for user_id in subscribers:
        try: bot.send_message(user_id, message, parse_mode='MarkdownV2')
        except Exception as e:
            if 'bot was blocked' in str(e): print(f"{user_id} заблокировал бота."); db.remove_subscriber(user_id)
            else: print(f"Ошибка отправки {user_id}: {e}")
    print(f"Рассылка завершена для {len(subscribers)} пользователей.")

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "♻️ *Привет\\! Я ваш эко\\-помощник\\.*\n\nИспользуйте кнопки ниже, чтобы начать\\!", parse_mode='MarkdownV2', reply_markup=create_main_keyboard())

@bot.message_handler(func=lambda message: message.text.startswith('эко-челлендж'))
def handle_challenges_button(message):
    current_challenge = db.get_user_challenge(message.from_user.id)
    if current_challenge:
        challenge_info = challenges.CHALLENGES[current_challenge['challenge_id']]
        start_date = date.fromisoformat(current_challenge['start_date'])
        days_passed = (date.today() - start_date).days
        response = (f"Вы уже участвуете в челлендже:\n\n*{challenge_info['title']}*\nДень {days_passed + 1} из {challenge_info['duration_days']}.\n\nХотите отказаться и выбрать новый?")
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Отказаться и выбрать новый", callback_data="show_all_challenges"), types.InlineKeyboardButton("Нет, я продолжаю!", callback_data="cancel_action"))
        bot.send_message(message.chat.id, response, parse_mode='Markdown', reply_markup=markup)
    else: show_all_challenges(message.chat.id)

def show_all_challenges(chat_id):
    markup = types.InlineKeyboardMarkup()
    for c_id, c_info in challenges.CHALLENGES.items():
        markup.add(types.InlineKeyboardButton(c_info['title'], callback_data=f"show_challenge_{c_id}"))
    bot.send_message(chat_id, "Выберите челлендж:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text.startswith('совет дня'))
def handle_tip_button(message):
    user_id = message.from_user.id
    tip_of_the_day = random.choice(eco_tips) if eco_tips else "У меня закончились советы."
    response = f"💡 *Случайный совет:*\n\n{escape_markdown(tip_of_the_day)}\n\n"
    markup = types.InlineKeyboardMarkup()
    if db.is_subscribed(user_id):
        response += "Вы подписаны на ежедневную рассылку. Хотите отписаться?"
        markup.add(types.InlineKeyboardButton("Отписаться 🔕", callback_data="unsubscribe_tip"))
    else:
        response += "Хотите получать такие советы каждый день?"
        markup.add(types.InlineKeyboardButton("Подписаться 🔔", callback_data="subscribe_tip"))
    bot.send_message(user_id, response, parse_mode='MarkdownV2', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True) # Универсальный обработчик
def handle_callbacks(call):
    user_id = call.from_user.id
    if call.data in ['subscribe_tip', 'unsubscribe_tip']:
        if call.data == 'subscribe_tip': db.add_subscriber(user_id); bot.edit_message_text("Отлично! Вы подписались.", call.message.chat.id, call.message.message_id)
        else: db.remove_subscriber(user_id); bot.edit_message_text("Вы отписались от рассылки.", call.message.chat.id, call.message.message_id)
    elif call.data.startswith('show_challenge_'):
        challenge_id = call.data.replace('show_challenge_', '')
        info = challenges.CHALLENGES[challenge_id]
        response = f"*{info['title']}*\n\n{info['description']}\n\nДлительность: {info['duration_days']} дней. Принять вызов?"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✅ Принять!", callback_data=f"accept_{challenge_id}"), types.InlineKeyboardButton("⬅️ Назад", callback_data="show_all"))
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=response, parse_mode='Markdown', reply_markup=markup)
    elif call.data.startswith('accept_challenge_'):
        challenge_id = call.data.replace('accept_challenge_', '')
        db.start_challenge(user_id, challenge_id)
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=challenges.CHALLENGES[challenge_id]['start_message'])
    elif call.data == 'show_all_challenges':
        bot.delete_message(call.message.chat.id, call.message.message_id); show_all_challenges(call.message.chat.id)
    elif call.data == 'cancel_action':
        bot.delete_message(call.message.chat.id, call.message.message_id); bot.send_message(call.message.chat.id, "Отлично! Продолжаем! 💪")
    elif call.data.startswith('search_context_'):
        material = call.data.replace('search_context_', '')
        bot.answer_callback_query(call.id, f"Ищу пункты для '{material}'...")
        bot.send_message(call.message.chat.id, f"В каком городе найти пункты для *{escape_markdown(material)}*?", parse_mode='MarkdownV2')

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    try:
        user_id = message.from_user.id
        text = message.text.strip().lower()
        response = ""
        if text.startswith('найти пункт'): bot.reply_to(message, "Какой вид вторсырья и в каком городе сдать?\n\nНапример: *Батарейки в Воронеже*", parse_mode='Markdown'); return
        if text.startswith('задать вопрос'): bot.reply_to(message, "Слушаю ваш вопрос о переработке отходов!"); return
        if text.startswith('эко-факт'): bot.reply_to(message, escape_markdown(random.choice(interesting_facts)), parse_mode='MarkdownV2'); return
        info_response = handle_info_request(text)
        if info_response: bot.reply_to(message, info_response, parse_mode='MarkdownV2'); return
        
        is_search_query = any(trigger in text for trigger in SEARCH_TRIGGERS)
        material, city, district = extract_entities(text)
        is_point_search = material and (city or is_search_query)

        if is_point_search:
            if not city:
                user_context[user_id] = {'last_material': material}
                bot.reply_to(message, f"Отлично, ищем '{escape_markdown(material)}'. В каком городе?"); return
            if not material and city:
                material = user_context.get(user_id, {}).pop('last_material', None)
            if city and material:
                all_city_points, search_terms = find_recycling_points(material, city)
                safe_material = escape_markdown(material)
                if not all_city_points:
                    if city.lower() in FALLBACK_POINTS:
                        fallback = FALLBACK_POINTS[city.lower()]
                        response = (f"😔 К сожалению, я не нашел специализированных пунктов для '{safe_material}'\\.\n\n"
                                    f"Но в городе *{escape_markdown(city.capitalize())}* есть универсальный вариант:\n\n"
                                    f"📍 *{escape_markdown(fallback['name'])}*\n"
                                    f"   *Адрес:* {escape_markdown(fallback['address'])}\n"
                                    f"   *Телефон:* `{escape_markdown(fallback.get('phone', 'не указан'))}`\n\n"
                                    f"⚠️ *Важно:* {escape_markdown(fallback['note'])}")
                    else: response = f"К сожалению, я не нашел пунктов для '{safe_material}' в городе *{escape_markdown(city.capitalize())}*\\."
                else:
                    points_to_show = []
                    if district:
                        points_in_district = [p for p in all_city_points if district in p.get('address', '').lower()]
                        if points_in_district: all_city_points = points_in_district
                    lebestok_points = [p for p in all_city_points if "седьмой лепесток" in p.get('name', '').lower()]
                    other_points = [p for p in all_city_points if "седьмой лепесток" not in p.get('name', '').lower()]
                    if lebestok_points: points_to_show.append(lebestok_points[0])
                    remaining_slots = MAX_POINTS_TO_SHOW - len(points_to_show)
                    if other_points and remaining_slots > 0: points_to_show.extend(other_points[:remaining_slots])
                    if not points_to_show: response = f"К сожалению, подходящих пунктов для '{safe_material}' не нашлось\\."
                    else:
                        header = f"✅ Нашел пункты для '{safe_material}' в городе *{escape_markdown(city.capitalize())}*:"
                        if district and any(district in p.get('address', '').lower() for p in points_to_show):
                            header = f"✅ Нашел пункты для '{safe_material}' в районе *{escape_markdown(district.capitalize())}*:"
                        response = format_points_response(points_to_show, header, search_terms, material)
        else:
            answer, context_to_save = get_knowledge_answer(text)
            if answer:
                response, markup = escape_markdown(answer), None
                if context_to_save:
                    user_context[user_id] = {'last_material': context_to_save}
                    markup = types.InlineKeyboardMarkup()
                    markup.add(types.InlineKeyboardButton(f"Найти пункты для '{context_to_save}'", callback_data=f"search_context_{context_to_save}"))
                bot.reply_to(message, response, parse_mode='MarkdownV2', reply_markup=markup); return
            else:
                bot.send_chat_action(message.chat.id, 'typing')
                response_giga = get_gigachat_answer(text)
                response = escape_markdown(response_giga).replace(r'\*', '*')
        bot.reply_to(message, response, parse_mode='MarkdownV2')
    except Exception as e:
        print(f"Произошла критическая ошибка: {e}")
        bot.reply_to(message, "Ой, что\\-то пошло не так\\.\\.\\.", parse_mode='MarkdownV2')

if __name__ == "__main__":
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_challenges, 'cron', hour=10)
    scheduler.add_job(send_daily_tip, 'cron', hour=11)
    scheduler.start()
    print("Планировщик запущен.")
    try:
        bot.polling(none_stop=True)
    except Exception as e:
        print(f"Бот остановился: {e}")
        scheduler.shutdown()