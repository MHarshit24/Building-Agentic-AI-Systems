import os
import sqlite3
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import psycopg2

# Load `.env` (if present) so we can configure DB credentials without changing code.
load_dotenv(".env.secrets")

DB_PATH = Path("code_mentor.db")

# PostgreSQL

def _postgres_conn_args():
    return dict(
        dbname=os.getenv("POSTGRES_DB", "code_mentor_db"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "postgre@!1234"),
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432"),
    )


def get_postgres_connection():
    conn = psycopg2.connect(**_postgres_conn_args())

    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ai_logs (
        id SERIAL PRIMARY KEY,
        code TEXT,
        language TEXT,
        experience_level TEXT,
        task TEXT,
        response TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS feedback_logs (
        id SERIAL PRIMARY KEY,
        code TEXT,
        rating INTEGER,
        comment TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()



def save_ai_log(code, language, experience_level, task, response):

    conn = None

    try:
        conn = psycopg2.connect(**_postgres_conn_args())

        cursor = conn.cursor()

        cursor.execute("""
        INSERT INTO ai_logs (code, language, experience_level, task, response)
        VALUES (%s, %s, %s, %s, %s)
        """, (
            code,
            language,
            experience_level,
            task,
            response
        ))

        conn.commit()
        conn.close()

        print("✅ AI log saved")

    except Exception as e:
        print("❌ AI LOG ERROR:", e)

    finally:
        if conn:
            conn.close()


def save_feedback_db(code, rating, comment):

    conn = None   # 🔥 ADD THIS (CRITICAL)

    try:
        conn = psycopg2.connect(**_postgres_conn_args())

        cursor = conn.cursor()

        print("🔍 Connected to DB")

        cursor.execute("SELECT current_database();")
        print("DB:", cursor.fetchone())

        cursor.execute("""
        INSERT INTO feedback_logs (code, rating, comment)
        VALUES (%s, %s, %s)
        """, (
            code,
            int(rating),
            comment
        ))

        conn.commit()
        print("✅ Feedback committed")

    except Exception as e:
        print("❌ FEEDBACK DB ERROR:", e)
        raise e

    finally:
        if conn:   # ✅ now safe
            conn.close()



'''
def save_feedback_db(code, rating, comment):
    """
    Save user feedback into PostgreSQL database.
    """

    conn = None  # ✅ Initialize

    try:
        conn = psycopg2.connect(
            dbname="code_mentor_db",
            user="postgres",
            password="postgre@!1234",
            host="localhost",
            port="5432"
        )

        cursor = conn.cursor()

        cursor.execute("""
        INSERT INTO feedback_logs (code, rating, comment)
        VALUES (%s, %s, %s)
        """, (
            code,
            rating,
            comment
        ))

        conn.commit()
        conn.close()

        print("✅ Feedback saved to PostgreSQL")

    except Exception as e:
        print("❌ FEEDBACK DB ERROR:", e)
        raise e  # optional (for API response)

    finally:
        if conn:
            conn.close()  # ✅ Safe close





def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ai_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT,
        language TEXT,
        experience_level TEXT,
        task TEXT,
        response TEXT,
        created_at TEXT
    )
    """)

    conn.commit()
    conn.close()

def save_ai_log(code, language, experience_level, task, response):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO ai_logs (code, language, experience_level, task, response, created_at)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (
        code,
        language,
        experience_level,
        task,
        response,
        datetime.utcnow().isoformat()
    ))

    conn.commit()
    conn.close()

'''