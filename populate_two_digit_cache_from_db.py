import argparse
import json
import os
import re
import sqlite3
from typing import Optional, Tuple, List, Dict, Set

# Reuse the exact conversion logic already used by the app
from main import word_to_major_number


DEFAULT_DB_PATH = "dictionary.db"
DEFAULT_CACHE_PATH = "two_digit_cache.json"
CANDIDATE_WORD_COLUMN_NAMES = {
    "word", "lemma", "term", "palavra", "entrada", "lexeme", "form", "token", "texto", "texto_base"
}


def detect_word_source(conn: sqlite3.Connection) -> Optional[Tuple[str, str]]:
    """
    Try to automatically detect the table and column that contain words in the DB.
    Returns a tuple (table_name, column_name) or None if not found.
    """
    cur = conn.cursor()

    # 1) List tables
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]

    # Prefer tables whose name hints at dictionary/words
    preferred_order: List[str] = sorted(
        tables,
        key=lambda t: (
            0 if re.search(r"(word|lemma|dict|entry|palavr|lex|term|token)", t, re.I) else 1,
            t.lower()
        )
    )

    for table in preferred_order:
        try:
            cur.execute(f"PRAGMA table_info('{table}')")
            cols = cur.fetchall()  # cid, name, type, notnull, dflt_value, pk
        except sqlite3.DatabaseError:
            continue

        # Try exact/best column name matches first
        text_cols: List[Tuple[str, str]] = []
        for _, col_name, col_type, *_ in cols:
            if isinstance(col_type, str):
                is_text = col_type.upper().startswith("TEXT") or col_type == ""  # SQLite typeless may show ""
            else:
                is_text = True
            text_cols.append((col_name, "TEXT" if is_text else (col_type or "")))

        # Rank columns by name match to common word column names first, then by TEXT type
        ranked_cols = sorted(
            text_cols,
            key=lambda c: (
                0 if c[0].lower() in CANDIDATE_WORD_COLUMN_NAMES else
                1 if re.search(r"(word|lemma|term|palavr|lex|form|token|texto)", c[0], re.I) else
                2,
                0 if c[1].upper().startswith("TEXT") else 1
            )
        )

        # Test the top 3 ranked columns with a quick sample to see if they look like words
        for col_name, _ in ranked_cols[:3]:
            try:
                cur.execute(f"SELECT {col_name} FROM '{table}' LIMIT 50")
                sample = [row[0] for row in cur.fetchall()]
            except sqlite3.DatabaseError:
                continue

            def looks_like_word(v: object) -> bool:
                if not isinstance(v, str):
                    return False
                s = v.strip()
                if not s:
                    return False
                # Reject very long paragraphs
                if len(s) > 64:
                    return False
                # Accept words or short terms including diacritics and basic punctuation
                return bool(re.match(r"^[\wÀ-ÖØ-öø-ÿ' -]{1,64}$", s))

            matches = sum(1 for v in sample if looks_like_word(v))
            if matches >= max(3, len(sample) // 5):  # heuristic: enough items look like words
                return table, col_name

    return None


def load_cache(cache_path: str) -> Dict[str, List[Dict[str, str]]]:
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {}


def save_cache(cache_path: str, data: Dict[str, List[Dict[str, str]]]) -> None:
    tmp_path = cache_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    os.replace(tmp_path, cache_path)


def should_include_number(number: str, pair: str, mode: str) -> bool:
    if mode == "exact":
        return number == pair
    # default: startswith
    return number.startswith(pair)


def normalize_word(w: str) -> Optional[str]:
    if not isinstance(w, str):
        return None
    s = w.strip()
    if not s:
        return None
    return s


def main():
    parser = argparse.ArgumentParser(
        description="Populate/repair two_digit_cache.json with words from dictionary.db for a specific two-digit pair."
    )
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="Path to SQLite DB file (default: dictionary.db)")
    parser.add_argument("--cache", default=DEFAULT_CACHE_PATH, help="Path to two_digit_cache.json (default: two_digit_cache.json)")
    parser.add_argument("--pair", default="46", help="Two-digit pair to (re)populate, e.g. 46")
    parser.add_argument("--mode", choices=["startswith", "exact"], default="startswith",
                        help="Filter mode: 'startswith' includes numbers beginning with the pair; 'exact' only exact two-digit matches")
    parser.add_argument("--table", help="Optional table name override")
    parser.add_argument("--column", help="Optional column name override (word/lemma column)")
    parser.add_argument("--limit", type=int, default=0, help="Optional limit of words processed from DB (0 = no limit)")
    parser.add_argument("--dry-run", action="store_true", help="Run detection and show counts without writing cache")
    parser.add_argument("--print", dest="print_count", type=int, default=0,
                        help="Print up to N matching words with their computed numbers (for inspection). 0 = no print")
    args = parser.parse_args()

    if not re.fullmatch(r"\d{2}", args.pair):
        print(f"ERROR: --pair must be exactly two digits, got '{args.pair}'")
        raise SystemExit(2)

    if not os.path.exists(args.db):
        print(f"ERROR: DB file not found at {args.db}")
        raise SystemExit(2)

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Detect table/column if not provided
    table = args.table
    column = args.column
    if not table or not column:
        detected = detect_word_source(conn)
        if detected:
            table, column = detected
            print(f"Detected words source: table='{table}', column='{column}'")
        else:
            print("ERROR: Could not auto-detect a word source table/column in the database.")
            print("Hint: re-run with --table TABLE --column COLUMN")
            raise SystemExit(2)
    else:
        print(f"Using explicit source: table='{table}', column='{column}'")

    # Stream words
    sql = f"SELECT {column} AS w FROM '{table}'"
    if args.limit and args.limit > 0:
        sql += f" LIMIT {args.limit}"

    print(f"Querying words from DB...")
    try:
        cur.execute(sql)
    except sqlite3.DatabaseError as e:
        print(f"ERROR executing query: {e}")
        raise SystemExit(2)

    cache = load_cache(args.cache)
    cache.setdefault(args.pair, [])
    existing_words_lower: Set[str] = { (e.get("word") or "").strip().lower() for e in cache.get(args.pair, []) if isinstance(e, dict) }

    added = 0
    scanned = 0
    candidates = 0
    exact_for_pair = 0

    new_entries: List[Dict[str, str]] = []
    sample_print: List[Tuple[str, str]] = []

    while True:
        rows = cur.fetchmany(5000)
        if not rows:
            break
        for row in rows:
            scanned += 1
            w_raw = row["w"]
            w = normalize_word(w_raw)
            if not w:
                continue

            try:
                number = word_to_major_number(w)
            except Exception:
                # Ignore words that cause issues in mapping
                continue

            if not number:
                continue

            if should_include_number(number, args.pair, args.mode):
                candidates += 1
                if number == args.pair:
                    exact_for_pair += 1
                # capture sample for printing
                if args.print_count and len(sample_print) < args.print_count:
                    sample_print.append((w, number))
                lw = w.lower()
                if lw not in existing_words_lower:
                    new_entries.append({"word": w, "number": number})
                    existing_words_lower.add(lw)

    print(f"Scanned rows: {scanned}")
    print(f"Matching candidates (mode={args.mode}, pair={args.pair}): {candidates}")
    print(f"Exact equals '{args.pair}': {exact_for_pair}")
    print(f"New unique entries to add: {len(new_entries)}")

    if args.dry_run:
        print("Dry-run: not writing to cache.")
        return

    if new_entries:
        cache[args.pair].extend(new_entries)
        # Optional: keep entries unique and sorted by word lower
        # Uniqueness by word text
        seen: Set[str] = set()
        deduped: List[Dict[str, str]] = []
        for e in cache[args.pair]:
            if not isinstance(e, dict):
                continue
            w = (e.get("word") or "").strip()
            n = (e.get("number") or "").strip()
            if not w or not n:
                continue
            lw = w.lower()
            if lw in seen:
                continue
            seen.add(lw)
            deduped.append({"word": w, "number": n})
        cache[args.pair] = sorted(deduped, key=lambda x: x["word"].lower())

        save_cache(args.cache, cache)
        print(f"Wrote {len(new_entries)} new entries. Total now under '{args.pair}': {len(cache[args.pair])}")
    else:
        print("No new entries to add.")


if __name__ == "__main__":
    main()