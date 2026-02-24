import sqlite3

# SQLite connection (Render/Threads safe)
conn = sqlite3.connect("bot.db", check_same_thread=False)

# Create table
conn.execute("""
CREATE TABLE IF NOT EXISTS keywords (
    user_id INTEGER,
    keyword TEXT,
    UNIQUE(user_id, keyword)
)
""")
conn.commit()


def add_keyword(user_id, keyword):
    """Add keyword for a user (ignore duplicates)."""
    conn.execute(
        "INSERT OR IGNORE INTO keywords (user_id, keyword) VALUES (?, ?)",
        (user_id, keyword)
    )
    conn.commit()


def remove_keyword(user_id, keyword):
    """Remove a keyword for a user."""
    conn.execute(
        "DELETE FROM keywords WHERE user_id=? AND keyword=?",
        (user_id, keyword)
    )
    conn.commit()


def list_keywords(user_id):
    """List keywords of a user."""
    cursor = conn.execute(
        "SELECT keyword FROM keywords WHERE user_id=? ORDER BY keyword",
        (user_id,)
    )
    return [row[0] for row in cursor.fetchall()]


def list_all_keywords():
    """Return list of (user_id, keyword) pairs for all users."""
    cursor = conn.execute(
        "SELECT user_id, keyword FROM keywords ORDER BY user_id"
    )
    return cursor.fetchall()
