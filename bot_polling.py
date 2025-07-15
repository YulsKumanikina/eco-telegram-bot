# bot_polling.py (ФИНАЛЬНАЯ ВЕРСИЯ - СЛУЧАЙНЫЕ ФАКТЫ)
import telebot
import pandas as pd
import json
import re
from typing import List, Tuple
from gigachat.client import GigaChatSyncClient
from gigachat.models import Chat, Messages, MessagesRole
import random # <-- ИМПОРТИРУЕМ МОДУЛЬ ДЛЯ СЛУЧАЙНОГО ВЫБОРА

# --- КОНФИГУРАЦИЯ ---
try:
    from config import TELEGRAM_TOKEN, GIGACHAT_API_KEY, KNOLEDGE_BASE_PATH, RECYCLING_POINTS_PATH
except ImportError:
    print("Ошибка: не удалось найти файл config.py или переменные в нем.")
    exit()

INTERESTING_FACTS_PATH = './data/interesting_facts.json' # <-- НОВЫЙ ПУТЬ
MAX_POINTS_TO_SHOW = 3

# --- Инициализация ботов ---
bot = telebot.TeleBot(TELEGRAM_TOKEN)
try:
    giga = GigaChatSyncClient(credentials=GIGACHAT_API_KEY, verify_ssl_certs=False)
    print("GigaChat успешно инициализирован.")
except Exception as e:
    print(f"Не удалось инициализировать GigaChat: {e}")
    giga = None

print("Бот (в режиме polling) запущен...")

# --- Загрузка данных ---
def load_data() -> Tuple[pd.DataFrame, List[dict], List[str]]: # <-- ИЗМЕНЕНИЕ
    try:
        points = pd.read_csv(RECYCLING_POINTS_PATH)
        with open(KNOLEDGE_BASE_PATH, 'r', encoding='utf-8') as f:
            knowledge = json.load(f)
        with open(INTERESTING_FACTS_PATH, 'r', encoding='utf-8') as f: # <-- ЗАГРУЖАЕМ ФАКТЫ
            facts = json.load(f)
        print("Данные успешно загружены.")
        return points, knowledge, facts
    except Exception as e:
        print(f"Ошибка загрузки данных: {e}"); return pd.DataFrame(), [], []

points_df, knowledge_base, interesting_facts = load_data() # <-- ИЗМЕНЕНИЕ

# --- Вспомогательная функция и остальные (без изменений) ---
# ... (код до handle_text опущен для краткости) ...
def escape_markdown(text: str) -> str:
    escape_chars = r'_*[]()~`>#+-=|{}.!'; return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)
def extract_entities(text: str) -> Tuple[str | None, str | None, str | None]:
    clean_text = re.sub(r'[^\w\s]', '', text).lower(); city, material, district = None, None, None; cities = ['воронеж', 'екатеринбург'];
    for c in cities:
        if c in clean_text: city = c; break
    if city == 'воронеж':
        districts = ['советский', 'ленинский', 'коминтерновский', 'левобережный', 'железнодорожный', 'центральный']
        for d in districts:
            if d in clean_text: district = d; clean_text = clean_text.replace(d, '').replace('район', ''); break
    if city: material = clean_text.replace(city, '').replace('куда сдать', '').replace('где принимают', '').replace('в', '').strip()
    return material, city, district
def find_recycling_points(material: str, city: str) -> Tuple[List[dict], List[str]]:
    if points_df.empty or not material or not city: return [], [];
    try:
        synonym_map = {'бутылк': ['бутылк', 'пэт', 'пластик'], 'пластик': ['пластик', 'пэт', 'бутылк', 'hdpe', 'пнд'], 'батарейк': ['батарейк', 'аккумулятор'], 'бумаг': ['бумаг', 'макулатур', 'картон', 'книг'], 'картон': ['картон', 'макулатур', 'бумаг'], 'книг': ['книг', 'макулатур', 'бумаг'], 'стекл': ['стекл', 'банк'], 'одежд': ['одежд', 'вещи', 'текстиль'], 'металл': ['металл', 'жестян', 'алюмин'], 'крышк': ['крышк'], 'техник': ['техник', 'электроника'],}
        search_terms = [];
        for key, values in synonym_map.items():
            if key in material: search_terms = values; break
        if not search_terms: search_terms = [material[:-1] if len(material) > 3 else material]
        city_points = points_df[points_df['city'].str.lower() == city.lower()]; valid_points = city_points.dropna(subset=['accepts']); pattern = '|'.join(search_terms)
        found_points = valid_points[valid_points['accepts'].str.lower().str.contains(pattern)]; return found_points.to_dict('records'), search_terms
    except Exception as e: print(f"Ошибка поиска: {e}"); return [], []
def format_points_response(points: List[dict], header: str, search_terms: List[str]) -> str:
    response_parts = [header]
    for idx, point in enumerate(points, 1):
        name = escape_markdown(point.get('name', 'Без названия')); address = escape_markdown(point.get('address', 'не указан'))
        work_hours = escape_markdown(point.get('work_hours', 'не указаны')); accepts_raw = str(point.get('accepts', 'не указано'))
        accepts_display = ""; found_keyword = False
        for term in search_terms:
            if term in accepts_raw.lower(): accepts_display = f"Да, включая '{escape_markdown(term.capitalize())}' и другое\\."; found_keyword = True; break
        if not found_keyword: accepts_display = escape_markdown((accepts_raw[:100] + '...') if len(accepts_raw) > 100 else accepts_raw)
        response_parts.append(
            f"📍 *{idx}\\. {name}*\n"
            f"   *Адрес:* {address}\n"
            f"   *Время работы:* {work_hours}\n"
            f"   *Что принимает:* {accepts_display}")
    return "\n\n".join(response_parts)
def get_knowledge_answer(question: str) -> str:
    user_words = set(re.sub(r'[^\w\s]', '', question.lower()).split()); best_match_score = 0; best_answer = ""
    for item in knowledge_base:
        kb_words = set(re.sub(r'[^\w\s]', '', item['question'].lower()).split())
        score = len(user_words.intersection(kb_words))
        if score > best_match_score: best_match_score = score; best_answer = item['answer']
    return best_answer if best_match_score >= 2 else ""
def get_gigachat_answer(question: str) -> str:
    if not giga: return "Извините, модуль GigaChat не был загружен."
    system_prompt = (
        "Твоя роль - эксперт по экологии. Твоя единственная задача - отвечать на вопросы, связанные с экологией, переработкой отходов, защитой природы и устойчивым развитием. "
        "Категорически запрещено отвечать на любые другие темы (политика, история, рецепты, математика и т.д.). "
        "Если вопрос не по теме, твой стандартный отказ: 'К сожалению, я могу обсуждать только вопросы, связанные с экологией. Давайте вернемся к этой теме.'"
        "Твой ответ на правильный вопрос должен быть кратким (не более 25 слов). Важные слова выделяй тегами <b_> и </b_>."
    )
    payload = Chat(messages=[Messages(role=MessagesRole.SYSTEM, content=system_prompt), Messages(role=MessagesRole.USER, content=question)], temperature=0.7)
    try:
        response = giga.chat(payload)
        if response.choices:
            raw_answer = response.choices[0].message.content
            return raw_answer.replace("<b_>", "*").replace("</b_>", "*")
        return "GigaChat не смог дать ответ."
    except Exception as e: print(f"Ошибка при обращении к GigaChat: {e}"); return "Извините, произошла ошибка при подключении к нейросети."

@bot.message_handler(commands=['start'])
def send_welcome(message):
    response = (
        "♻️ *Привет\\! Я ваш эко\\-помощник\\.*\n\n"
        "Я здесь, чтобы помочь вам сделать мир чище\\.\n\n"
        "📍 *Ищу пункты приема вторсырья*\n"
        "→ _Куда сдать батарейки?_\n\n"
        "🧠 *Отвечаю на вопросы об экологии*\n"
        "→ _Почему нельзя сжигать пластик?_\n\n"
        "Задавайте свой вопрос\\!"
    )
    # Используем MarkdownV2, чтобы работали и жирный шрифт, и курсив.
    bot.reply_to(message, response, parse_mode='MarkdownV2')

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    try:
        text = message.text.strip().lower() # Сразу приводим к нижнему регистру
        material, city, district = extract_entities(text)
        
        response = ""
        
                # --- ИЗМЕНЕНИЕ: Добавляем триггеры для случайного факта ---
        fact_triggers = ["расскажи что-нибудь", "расскажи факт", "удиви меня", "что-нибудь интересное"]
        if any(trigger in text for trigger in fact_triggers):
            if interesting_facts:
                # <-- РЕШЕНИЕ: Экранируем выбранный факт перед отправкой -->
                response = escape_markdown(random.choice(interesting_facts))
            else:
                response = "У меня закончились интересные факты на сегодня, но я могу ответить на другие вопросы об экологии!"
        
        elif city:
            # ... (логика поиска пунктов без изменений) ...
            if not material:
                response = "Пожалуйста, уточните, что именно вы хотите сдать в городе Воронеж?"
            else:
                all_city_points, search_terms = find_recycling_points(material, city)
                safe_material = escape_markdown(material)
                if not all_city_points: response = f"К сожалению, в городе {escape_markdown(city.capitalize())} я не нашел пунктов приема для '{safe_material}'\\."
                else:
                    points_to_show = [];
                    if district: all_city_points = [p for p in all_city_points if district in p.get('address', '').lower()] or all_city_points
                    lebestok_points = [p for p in all_city_points if "седьмой лепесток" in p.get('name', '').lower()]
                    other_points = [p for p in all_city_points if "седьмой лепесток" not in p.get('name', '').lower()]
                    if lebestok_points: points_to_show.append(lebestok_points[0])
                    remaining_slots = MAX_POINTS_TO_SHOW - len(points_to_show)
                    if other_points and remaining_slots > 0: points_to_show.extend(other_points[:remaining_slots])
                    if not points_to_show: response = f"К сожалению, в городе {escape_markdown(city.capitalize())} я не нашел подходящих пунктов\\."
                    else:
                        header = f"✅ Нашел пункты приема для '{safe_material}' в городе {escape_markdown(city.capitalize())}:"
                        if district and any(district in p.get('address', '').lower() for p in points_to_show):
                            safe_district = escape_markdown(district.capitalize()); header = f"✅ Нашел пункты для '{safe_material}' в районе *{safe_district}*:"
                        response = format_points_response(points_to_show, header, search_terms)
        else:
            answer = get_knowledge_answer(text)
            if answer:
                response = escape_markdown(answer)
            else:
                bot.send_chat_action(message.chat.id, 'typing')
                response = get_gigachat_answer(text)
                response = escape_markdown(response).replace(r'\*', '*')

        bot.reply_to(message, response, parse_mode='MarkdownV2')

    except Exception as e:
        print(f"Произошла критическая ошибка: {e}")
        bot.reply_to(message, "Ой, что\\-то пошло не так\\.\\.\\.", parse_mode='MarkdownV2')

if __name__ == "__main__":
    try:
        bot.polling(none_stop=True)
    except Exception as e:
        print(f"Бот остановился из-за ошибки: {e}")