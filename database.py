import sqlite3
import os

DB_PATH = "auto_sms.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 주소록 테이블
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS contacts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT NOT NULL UNIQUE,
        category TEXT,
        memo TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # 발송 로그 테이블
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS sending_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        send_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        recipient_phone TEXT NOT NULL,
        content TEXT NOT NULL,
        msg_type TEXT NOT NULL, -- SMS, LMS, MMS
        status TEXT NOT NULL,   -- Success, Fail
        result_msg TEXT         -- Error details if any
    )
    ''')
    
    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_PATH}")

if __name__ == "__main__":
    init_db()
