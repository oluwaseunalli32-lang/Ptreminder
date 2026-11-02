import sqlite3
import datetime

DB_NAME = "reminders.db"

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        # Table for one-time personal reminders
        c.execute('''CREATE TABLE IF NOT EXISTS reminders
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      chat_id INTEGER, text TEXT, remind_at TEXT)''')
        # Table for recurring group announcements
        c.execute('''CREATE TABLE IF NOT EXISTS recurring
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      chat_id INTEGER, text TEXT, hour INTEGER, minute INTEGER, days TEXT)''')
        conn.commit()

def add_reminder(chat_id, text, remind_at):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("INSERT INTO reminders (chat_id, text, remind_at) VALUES (?, ?, ?)",
                  (chat_id, text, remind_at))
        conn.commit()

def get_due_reminders(now_iso):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT id, chat_id, text FROM reminders WHERE remind_at <= ?", (now_iso,))
        return c.fetchall()

def delete_reminder(reminder_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
        conn.commit()
