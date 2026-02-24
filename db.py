import sqlite3

conn = sqlite3.connect("bot.db", check_same_thread=False)

conn.execute(
    "INSERT OR IGNORE INTO keywords (user_id, keyword) VALUES (?, ?)",
    (user_id, keyword)
)
""")

conn.commit()

def add_keyword(user_id, keyword):
    conn.execute("INSERT OR IGNORE INTO keywords VALUES (?, ?)", (user_id, keyword))
    conn.commit()

def list_keywords(user_id):
    cursor = conn.execute("SELECT keyword FROM keywords WHERE user_id=?", (user_id,))
    return [row[0] for row in cursor.fetchall()]
def list_all_keywords():
    cursor = conn.execute("SELECT user_id, keyword FROM keywords")
    return cursor.fetchall()
