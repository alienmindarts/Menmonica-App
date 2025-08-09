import sqlite3

DB_PATH = "dictionary.db"

WORDS = [
    # Start with 46 exactly (r + j/x/ch/gi/ge)
    "racha",
    "racho",
    "rachar",
    "rachado",
    "rachadura",
    "racharia",
    "rijo",
    "rixa",
    "regime",
    "região",
    "rejeito",
    "rejeitar",
    "rejeição",
    "rigidez",
    "rígido",
    "rijamente",
]

def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Ensure 'words' table exists (matches current schema: id INTEGER, word TEXT)
    cur.execute("CREATE TABLE IF NOT EXISTS words (id INTEGER PRIMARY KEY AUTOINCREMENT, word TEXT)")
    conn.commit()

    inserted = 0
    for w in WORDS:
        w = (w or "").strip()
        if not w:
            continue
        # Avoid duplicates by checking existence
        cur.execute("SELECT 1 FROM words WHERE word = ? LIMIT 1", (w,))
        if cur.fetchone() is None:
            cur.execute("INSERT INTO words(word) VALUES (?)", (w,))
            inserted += 1

    conn.commit()
    conn.close()
    print(f"Inserted {inserted} new words into 'words' table out of {len(WORDS)} candidates.")

if __name__ == "__main__":
    main()