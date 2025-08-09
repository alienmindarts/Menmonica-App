import sqlite3
import sys
from typing import List, Tuple

DB_PATH = "dictionary.db"

def list_tables(cur) -> List[str]:
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    return [r[0] for r in cur.fetchall()]

def table_info(cur, table: str) -> Tuple[int, List[Tuple[int, str, str, int, str, int]]]:
    cur.execute(f"PRAGMA table_info('{table}')")
    cols = cur.fetchall()
    try:
        cur.execute(f"SELECT COUNT(*) FROM '{table}'")
        count = cur.fetchone()[0]
    except Exception as e:
        count = -1
    return count, cols

def main():
    try:
        conn = sqlite3.connect(DB_PATH)
    except Exception as e:
        print(f"ERROR: cannot open DB {DB_PATH}: {e}")
        sys.exit(2)
    cur = conn.cursor()
    tables = list_tables(cur)
    print(f"Tables ({len(tables)}): {tables}")
    for t in tables:
        count, cols = table_info(cur, t)
        col_list = [(cid, name, ctype) for (cid, name, ctype, *_rest) in cols]
        print(f"- {t}: rows={count}, columns={col_list}")
        # Show a small sample of first 5 rows for text-like columns
        text_cols = [name for (_cid, name, ctype) in col_list if (isinstance(ctype, str) and (ctype.upper().startswith('TEXT') or ctype == ''))]
        if text_cols:
            try:
                cur.execute(f"SELECT {', '.join(text_cols[:3])} FROM '{t}' LIMIT 5")
                rows = cur.fetchall()
                print(f"  Sample ({text_cols[:3]}):")
                for r in rows:
                    print(f"   {r}")
            except Exception as e:
                print(f"  Sample read error: {e}")
    conn.close()

if __name__ == '__main__':
    main()