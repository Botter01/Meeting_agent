import sqlite3

DB_NAME = "meetings.db"

def init_db():
    connect = sqlite3.connect(DB_NAME)
    cursor = connect.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transcripts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        content TEXT
    )
    """)

    connect.commit()
    connect.close()

def save_transcript(transcript):
    connect = sqlite3.connect(DB_NAME)
    cursor = connect.cursor()

    cursor.execute(
        "INSERT INTO transcripts (content) VALUES (?)",
        (transcript,)
    )