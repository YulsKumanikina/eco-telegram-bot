# db_manager.py

import sqlite3
from datetime import date
from config import DB_PATH # <-- Импортируем абсолютный путь

def get_connection():
    """Возвращает соединение с базой данных."""
    return sqlite3.connect(DB_PATH)

def init_db():
    """Инициализирует базу данных и создает таблицы, если их нет."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS user_challenges (...)')
    cursor.execute('CREATE TABLE IF NOT EXISTS subscribers (...)')
    conn.commit()
    conn.close()
    print("База данных успешно инициализирована.")

# ... (все остальные функции в этом файле должны использовать get_connection() вместо sqlite3.connect(DB_NAME))

# Пример:
def start_challenge(user_id: int, challenge_id: str):
    conn = get_connection()
    # ... остальной код функции ...
    conn.close()

# Просто замените весь файл на этот код:

import sqlite3
from datetime import date
from config import DB_PATH

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_challenges (
            user_id INTEGER PRIMARY KEY, challenge_id TEXT NOT NULL, start_date TEXT NOT NULL
        )''')
    cursor.execute('CREATE TABLE IF NOT EXISTS subscribers (user_id INTEGER PRIMARY KEY)')
    conn.commit()
    conn.close()
    print("База данных успешно инициализирована.")

def start_challenge(user_id: int, challenge_id: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO user_challenges VALUES (?, ?, ?)', (user_id, challenge_id, date.today().isoformat()))
    conn.commit()
    conn.close()

def get_user_challenge(user_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT challenge_id, start_date FROM user_challenges WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return {"challenge_id": result[0], "start_date": result[1]} if result else None

def get_all_active_challenges():
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, challenge_id, start_date FROM user_challenges')
    results = cursor.fetchall()
    conn.close()
    return results

def end_challenge(user_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM user_challenges WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def add_subscriber(user_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO subscribers (user_id) VALUES (?)', (user_id,))
    conn.commit()
    conn.close()

def remove_subscriber(user_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM subscribers WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def is_subscribed(user_id: int) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM subscribers WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def get_all_subscribers() -> list:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM subscribers')
    results = [row[0] for row in cursor.fetchall()]
    conn.close()
    return results