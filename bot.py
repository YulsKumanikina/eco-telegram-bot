# bot_polling.py
import telebot
import pandas as pd
import json
import re
from typing import List, Tuple # <-- ИЗМЕНЕНИЕ: добавили импорт для современного синтаксиса

# --- КОНФИГУРАЦИЯ ---
try:
    from config import TELEGRAM_TOKEN, KNOLEDGE_BASE_PATH, RECYCLING_POINTS_PATH
except ImportError:
    print("Ошибка: не удалось найти файл config.py или переменные в нем.")
    exit()

# --- Инициализация бота ---
bot = telebot.TeleBot(TELEGRAM_TOKEN)
print("Бот (в режиме polling) запущен...")

# --- Загрузка данных ---
def load_data() -> Tuple[pd.DataFrame, List[dict]]: # <-- ИЗМЕНЕНИЕ: уточнили, что возвращается
    """Загружает базы данных из файлов."""
    try:
        points = pd.read_csv(RECYCLING_POINTS_PATH)
        with open(KNOLEDGE_BASE_PATH, 'r', encoding='utf-8') as f:
            knowledge = json.load(f)
        print("Данные успешно загружены.")
        return points, knowledge
    except Exception as e:
        print(f"Ошибка загрузки данных: {e}")
        return pd.DataFrame(), []

points_df, knowledge_base = load_data()

# --- Функции поиска ---
def find_recycling_points(material: str, city: str) -> List[dict]: # <-- ИЗМЕНЕНИЕ: заменили list на List[dict]
    """Поиск пунктов приема по городу и материалу."""
    if points_df.empty: return []
    try:
        city_points = points_df[points_df['city'].str.lower() == city.lower()]
        if city_points.empty: return []
        # Проверяем, что столбец 'accepts' не пустой (не NaN), чтобы избежать ошибок
        valid_points = city_points.dropna(subset=['accepts'])
        found_points = valid_points[valid_points['accepts'].str.lower().str.contains(material.lower())]
        return found_points.to_dict('records')
    except Exception as e:
        print(f"Ошибка поиска: {e}")
        return []

def get_knowledge_answer(question: str) -> str:
    """Поиск ответа в базе знаний по ключевым словам."""
    clean_question = re.sub(r'[^\w\s]', '', question.lower())
    for item in knowledge_base:
        clean_item_question = re.sub(r'[^\w\s]', '', item['question'].lower())
        if clean_question in clean_item_question:
            return item['answer']
    return ""

def extract_material_and_city(text: str) -> Tuple[str | None, str | None]: # <-- ИЗМЕНЕНИЕ: уточнили синтаксис
    """Извлекает материал и город из текста запроса."""
    text_lower = text.lower()
    city = None
    material = None
    if 'воронеж' in text_lower: city = 'воронеж'
    elif 'екатеринбург' in text_lower: city = 'екатеринбург'
    if city:
        material = text_lower.replace(city, '')
        triggers = ['куда сдать', 'где принимают', 'в', 'можно сдать']
        for trigger in triggers:
            material = material.replace(trigger, '')
        material = material.strip()
        # Убираем простые окончания для лучшего поиска
        if material.endswith('и') or material.endswith('ы') or material.endswith('у'):
            material = material[:-1]
    return material, city

def format_points_response(points: List[dict], city: str, material: str) -> str: # <-- ИЗМЕНЕНИЕ: list на List[dict]
    """Форматирование списка пунктов в красивый ответ."""
    response_parts = [f"✅ Нашел пункты приема для '{material}' в городе {city.capitalize()}:\n"]
    for idx, point in enumerate(points[:5], 1): # Ограничиваем до 5 пунктов
        name = point.get('name', 'Без названия')
        address = point.get('address', 'не указан')
        work_hours = point.get('work_hours', 'не указаны')
        # Осторожно обрезаем описание, чтобы не было ошибок
        accepts_raw = point.get('accepts', 'не указано')
        accepts = (str(accepts_raw)[:100] + '...') if len(str(accepts_raw)) > 100 else str(accepts_raw)
        
        response_parts.append(
            f"📍 *{idx}. {name}*\n"
            f"   *Адрес:* {address}\n"
            f"   *Время работы:* {work_hours}\n"
            f"   *Что принимает:* {accepts}"
        )
    return "\n\n".join(response_parts)

# --- Обработчики команд Telebot ---

@bot.message_handler(commands=['start'])
def send_welcome(message):
    """Обработчик команды /start."""
    response = (
        "♻️ Привет! Я бот для поиска пунктов приема вторсырья в Воронеже и Екатеринбурге.\n\n"
        "Вы можете задать мне вопрос, например:\n"
        "➡️ Куда сдать пластик в Воронеже?\n"
        "➡️ Где принимают батарейки в Екатеринбурге?\n"
        "➡️ Как подготовить макулатуру к сдаче?"
    )
    bot.reply_to(message, response)

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    """Обработчик всех текстовых сообщений."""
    try:
        text = message.text.strip()
        material, city = extract_material_and_city(text)
        
        if city and material:
            points = find_recycling_points(material, city)
            if points:
                response = format_points_response(points, city, material)
            else:
                response = f"К сожалению, в городе {city.capitalize()} я не нашел пунктов приема для '{material}'."
        else:
            answer = get_knowledge_answer(text)
            response = answer if answer else "Извините, я не понял ваш вопрос. Попробуйте спросить о пунктах приема в Воронеже или Екатеринбурге, или задайте общий вопрос об экологии."

        bot.reply_to(message, response, parse_mode='Markdown')
    except Exception as e:
        print(f"Произошла ошибка при обработке сообщения: {e}")
        bot.reply_to(message, "Ой, что-то пошло не так. Я уже разбираюсь с проблемой!")

# --- Запуск бота ---
if __name__ == "__main__":
    bot.polling(none_stop=True)