# =========================================================================
# ===                  ФИНАЛЬНАЯ ВЕРСИЯ BOT_POLLING.PY                  ===
# ===             (С постоянными и контекстными кнопками)             ===
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

# --- ГЛОБАЛЬНЫЕ НАСТРОЙКИ И СЛОВАРИ ---

user_context = {}
STOP_WORDS = set(['и', 'в', 'во', 'не', 'что', 'он', 'на', 'я', 'с', 'со', 'как', 'а', 'то', 'все', 'она', 'так', 'его', 'но', 'да', 'ты', 'к', 'у', 'же', 'вы', 'за', 'бы', 'по', 'только', 'ее', 'мне', 'было', 'вот', 'от', 'меня', 'еще', 'нет', 'о', 'из', 'ему', 'теперь', 'когда', 'даже', 'ну', 'вдруг', 'ли', 'если', 'уже', 'или', 'ни', 'быть', 'был', 'него', 'до', 'вас', 'нибудь', 'опять', 'уж', 'вам', 'ведь', 'там', 'потом', 'себя', 'ничего', 'ей', 'может', 'они', 'тут', 'где', 'есть', 'надо', 'ней', 'для', 'мы', 'тебя', 'их', 'чем', 'была', 'сам', 'чтоб', 'без', 'будто', 'чего', 'раз', 'тоже', 'себе', 'под', 'будет', 'ж', 'тогда', 'кто', 'этот', 'того', 'потому', 'этого', 'какой', 'совсем', 'ним', 'здесь', 'этом', 'один', 'почти', 'мой', 'тем', 'чтобы', 'нее', 'сейчас', 'были', 'куда', 'зачем', 'всех', 'никогда', 'можно', 'при', 'наконец', 'два', 'об', 'другой', 'хоть', 'после', 'над', 'больше', 'тот', 'через', 'эти', 'нас', 'про', 'всего', 'них', 'какая', 'много', 'разве', 'три', 'эту', 'моя', 'впрочем', 'хорошо', 'свою', 'этой', 'перед', 'иногда', 'лучше', 'чуть', 'том', 'нельзя', 'такой', 'им', 'более', 'всегда', 'конечно', 'всю', 'между', 'такое', 'это'])
SEARCH_TRIGGERS = ['куда сдать', 'где принимают', 'пункты приема', 'пункты приёма', 'адреса', 'адрес', 'найди', 'найти', 'где', 'куда']

# --- КОНФИГУРАЦИЯ ---
try:
    from config import (TELEGRAM_TOKEN, GIGACHAT_API_KEY, KNOLEDGE_BASE_PATH, RECYCLING_POINTS_PATH, INTERESTING_FACTS_PATH, FALLBACK_POINTS)
except ImportError:
    print("Ошибка: не удалось найти файл config.py или необходимые переменные в нем.")
    exit()

MAX_POINTS_TO_SHOW = 3

# --- ИНИЦИАЛИЗАЦИЯ ---
bot = telebot.TeleBot(TELEGRAM_TOKEN)
try:
    giga = GigaChatSyncClient(credentials=GIGACHAT_API_KEY, verify_ssl_certs=False)
    print("GigaChat успешно инициализирован.")
except Exception as e:
    print(f"Не удалось инициализировать GigaChat: {e}")
    giga = None

print("Бот (в режиме polling) запущен...")

# --- ЗАГРУЗКА ДАННЫХ ---
def load_data() -> Tuple[pd.DataFrame, List[dict], List[str]]:
    try:
        points = pd.read_csv(RECYCLING_POINTS_PATH)
        with open(KNOLEDGE_BASE_PATH, 'r', encoding='utf-8') as f: knowledge = json.load(f)
        with open(INTERESTING_FACTS_PATH, 'r', encoding='utf-8') as f: facts = json.load(f)
        print("Данные успешно загружены.")
        return points, knowledge, facts
    except Exception as e:
        print(f"Ошибка загрузки данных: {e}")
        return pd.DataFrame(), [], []

points_df, knowledge_base, interesting_facts = load_data()

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def escape_markdown(text: str) -> str:
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

def create_main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton('Найти пункт ♻️'), types.KeyboardButton('Задать вопрос 🧠'), types.KeyboardButton('Эко-факт ✨'))
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
    if city:
        temp_material = clean_text.replace(city, '')
        for trigger in SEARCH_TRIGGERS: temp_material = temp_material.replace(trigger, '')
        material = temp_material.replace(' в ', ' ').strip()
    return material, city, district

def find_recycling_points(material: str, city: str) -> Tuple[List[dict], List[str]]:
    if points_df.empty or not material or not city: return [], []
    try:
        synonym_map = {'бутылк': ['бутылк', 'пэт', 'пластик'], 'пластик': ['пластик', 'пэт', 'бутылк', 'hdpe', 'пнд'], 'батарейк': ['батарейк', 'аккумулятор'], 'бумаг': ['бумаг', 'макулатур', 'картон', 'книг'], 'картон': ['картон', 'макулатур', 'бумаг'], 'книг': ['книг', 'макулатур', 'бумаг'], 'стекл': ['стекл', 'банк'], 'одежд': ['одежд', 'вещи', 'текстиль'], 'металл': ['металл', 'жестян', 'алюмин'], 'крышк': ['крышк'], 'техник': ['техник', 'электроника'], 'опасные отходы': ['опасные отходы', 'ртуть', 'градусник', 'лампочк', 'лампа']}
        search_terms = []
        for key, values in synonym_map.items():
            if key in material: search_terms = values; break
        if not search_terms: search_terms = [material[:-1] if len(material) > 3 else material]
        city_points = points_df[points_df['city'].str.lower() == city.lower()]
        valid_points = city_points.dropna(subset=['accepts'])
        pattern = '|'.join(search_terms)
        found_points = valid_points[valid_points['accepts'].str.lower().str.contains(pattern)]
        return found_points.to_dict('records'), search_terms
    except Exception as e:
        print(f"Ошибка поиска: {e}")
        return [], []

def format_points_response(points: List[dict], header: str, search_terms: List[str], original_material: str) -> str:
    response_parts = [header]
    for idx, point in enumerate(points, 1):
        name = escape_markdown(point.get('name', 'Без названия'))
        address = escape_markdown(point.get('address', 'не указан'))
        work_hours = escape_markdown(point.get('work_hours', 'не указаны'))
        accepts_raw = str(point.get('accepts', 'не указано'))
        accepts_display = ""
        if any(term in accepts_raw.lower() for term in search_terms):
            accepts_display = f"Да, включая '{escape_markdown(original_material.capitalize())}' и другое\\."
        else:
            accepts_display = escape_markdown((accepts_raw[:100] + '...') if len(accepts_raw) > 100 else accepts_raw)
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
        score = len(user_words.intersection(kb_words))
        if score > best_match_score:
            best_match_score, best_answer = score, item['answer']
            best_context = item.get('context_keyword')
    return (best_answer, best_context) if best_match_score >= 1 else ("", None)

def get_gigachat_answer(question: str) -> str:
    if not giga: return "Извините, модуль GigaChat не был загружен."
    system_prompt = "Твоя роль - эксперт по экологии. Отвечай на вопросы, связанные с экологией, переработкой отходов, защитой природы. Категорически запрещено отвечать на любые другие темы. Если вопрос не по теме, твой стандартный отказ: 'К сожалению, я могу обсуждать только вопросы, связанные с экологией.' Ответ на правильный вопрос должен быть кратким (не более 25 слов)."
    payload = Chat(messages=[Messages(role=MessagesRole.SYSTEM, content=system_prompt), Messages(role=MessagesRole.USER, content=question)], temperature=0.7)
    try:
        response = giga.chat(payload)
        return response.choices[0].message.content if response.choices else "GigaChat не смог дать ответ."
    except Exception as e:
        print(f"Ошибка при обращении к GigaChat: {e}")
        return "Извините, произошла ошибка при подключении к нейросети."

# --- ОБРАБОТЧИКИ TELEGRAM ---

@bot.message_handler(commands=['start'])
def send_welcome(message):
    response = ("♻️ *Привет\\! Я ваш эко\\-помощник\\.*\n\n"
                "Я здесь, чтобы помочь вам сделать мир чище\\.\n\n"
                "Используйте кнопки ниже, чтобы начать\\!")
    bot.reply_to(message, response, parse_mode='MarkdownV2', reply_markup=create_main_keyboard())

# --- ЭТОТ ОБРАБОТЧИК НУЖНО ДОБАВИТЬ ---
@bot.callback_query_handler(func=lambda call: call.data.startswith('search_context_'))
def handle_context_search(call):
    material = call.data.replace('search_context_', '')
    bot.answer_callback_query(call.id, f"Ищу пункты для '{material}'...")
    response = f"В каком городе вы хотите найти пункты для *{escape_markdown(material)}*?"
    bot.send_message(call.message.chat.id, response, parse_mode='MarkdownV2')
# ----------------------------------------

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    try:
        user_id = message.from_user.id
        text = message.text.strip().lower()

        if text == 'найти пункт ♻️':
            response = "Какой вид вторсырья и в каком городе вы хотите сдать?\n\nНапример: *Батарейки в Воронеже*"
            bot.reply_to(message, response, parse_mode='Markdown')
            return
        if text == 'задать вопрос 🧠':
            response = "Слушаю ваш вопрос об экологии!"
            bot.reply_to(message, response)
            return
        if text == 'эко-факт ✨':
             response = escape_markdown(random.choice(interesting_facts)) if interesting_facts else "Факты закончились!"
             bot.reply_to(message, response, parse_mode='MarkdownV2')
             return

        material, city, district = extract_entities(text)

        if city and not material:
            if user_id in user_context and 'last_material' in user_context[user_id]:
                material = user_context[user_id]['last_material']
                print(f"Взят материал '{material}' из контекста для пользователя {user_id}")

        if city:
            if not material:
                response = "Пожалуйста, уточните, что именно вы хотите сдать? Например: 'куда сдать батарейки'."
            else:
                all_city_points, search_terms = find_recycling_points(material, city)
                safe_material = escape_markdown(material)
                if not all_city_points:
                    if city.lower() in FALLBACK_POINTS:
                        fallback = FALLBACK_POINTS[city.lower()]
                        response = (f"😔 К сожалению, я не нашел специализированных пунктов для '{safe_material}'\\.\n\n"
                                    f"Но в городе *{escape_markdown(city.capitalize())}* есть универсальный вариант:\n\n"
                                    f"📍 *{escape_markdown(fallback['name'])}*\n"
                                    f"   *Адрес:* {escape_markdown(fallback['address'])}\n\n"
                                    f"⚠️ *Важно:* {escape_markdown(fallback['note'])}")
                    else:
                        response = f"К сожалению, в городе {escape_markdown(city.capitalize())} я не нашел пунктов приема для '{safe_material}'\\."
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
                    if not points_to_show:
                        response = f"К сожалению, в районе *{escape_markdown(district.capitalize())}* я не нашел подходящих пунктов\\." if district else f"К сожалению, я не нашел подходящих пунктов для '{safe_material}'\\."
                    else:
                        header = f"✅ Нашел пункты для '{safe_material}' в городе {escape_markdown(city.capitalize())}:"
                        if district and any(district in p.get('address', '').lower() for p in points_to_show):
                            header = f"✅ Нашел пункты для '{safe_material}' в районе *{escape_markdown(district.capitalize())}*:"
                        response = format_points_response(points_to_show, header, search_terms, material)
        else:
            answer, context_to_save = get_knowledge_answer(text)
            if answer:
                response = escape_markdown(answer)
                markup = None
                if context_to_save:
                    user_context[user_id] = {'last_material': context_to_save}
                    print(f"Сохранен контекст '{context_to_save}' для пользователя {user_id}")
                    markup = types.InlineKeyboardMarkup()
                    button_text = f"Найти пункты для '{context_to_save}'"
                    callback_data = f"search_context_{context_to_save}"
                    markup.add(types.InlineKeyboardButton(text=button_text, callback_data=callback_data))
                # Отправляем сообщение здесь, а не выходим из функции
                bot.reply_to(message, response, parse_mode='MarkdownV2', reply_markup=markup)
                return # <-- ВАЖНО: выход здесь
            else:
                bot.send_chat_action(message.chat.id, 'typing')
                response_giga = get_gigachat_answer(text)
                response = escape_markdown(response_giga).replace(r'\*', '*')
        
        # Этот блок теперь будет выполняться только для некоторых сценариев
        bot.reply_to(message, response, parse_mode='MarkdownV2')

    except Exception as e:
        print(f"Произошла критическая ошибка: {e}")
        bot.reply_to(message, "Ой, что\\-то пошло не так\\.\\.\\.", parse_mode='MarkdownV2')

# --- ЗАПУСК БОТА ---
if __name__ == "__main__":
    try:
        bot.polling(none_stop=True)
    except Exception as e:
        print(f"Бот остановился из-за ошибки: {e}")