# db_manager.py

import sqlite3
from datetime import date

DB_NAME = 'eco_bot.db'

def init_db():
    """Инициализирует базу данных и создает таблицу, если ее нет."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_challenges (
            user_id INTEGER PRIMARY KEY,
            challenge_id TEXT NOT NULL,
            start_date TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()
    print("База данных успешно инициализирована.")

def start_challenge(user_id: int, challenge_id: str):
    """Начинает новый челлендж для пользователя."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    today = date.today().isoformat()
    # INSERT OR REPLACE обновит запись, если пользователь решит сменить челлендж
    cursor.execute('''
        INSERT OR REPLACE INTO user_challenges (user_id, challenge_id, start_date)
        VALUES (?, ?, ?)
    ''', (user_id, challenge_id, today))
    conn.commit()
    conn.close()

def get_user_challenge(user_id: int):
    """Возвращает активный челлендж пользователя или None."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT challenge_id, start_date FROM user_challenges WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    if result:
        return {"challenge_id": result[0], "start_date": result[1]}
    return None

def get_all_active_challenges():
    """Возвращает все активные челленджи для проверки планировщиком."""
    conn = sqlite3.connect(DB_NAME)
    # Позволяет обращаться к столбцам по имени
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, challenge_id, start_date FROM user_challenges')
    results = cursor.fetchall()
    conn.close()
    return results

def end_challenge(user_id: int):
    """Завершает челлендж для пользователя."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM user_challenges WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()