from flask import Flask, request, jsonify, render_template
from main import find_pairs_combinations, check_pair_in_cache, find_single_digit_words, word_to_major_number, load_two_digit_cache
from itertools import product
import os, json, random, threading, re, unicodedata

app = Flask(__name__, template_folder='templates')

# CORS for API when served from a different origin (e.g., GitHub Pages frontend)
@app.after_request
def add_cors_headers(response):
    try:
        if request.path.startswith('/api/'):
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
            response.headers['Access-Control-Allow-Methods'] = 'GET,POST,OPTIONS'
    except Exception:
        pass
    return response

# CORS preflight handlers (so POST with JSON works cross-origin)
@app.route('/api/convert', methods=['OPTIONS'])
def options_convert():
    return ('', 204)

@app.route('/api/random_phrase', methods=['OPTIONS'])
def options_random_phrase():
    return ('', 204)

# Simple health endpoint for Render health checks
# Additionally, it triggers a non-blocking cache warm-up to reduce cold-start latency
@app.get('/api/health')
def health():
    try:
        if not app.config.get('WARMING', False):
            app.config['WARMING'] = True
            def warm():
                try:
                    # Warm two_digit_cache.json (heavy) and digit_cache.json (light) if present
                    try:
                        load_two_digit_cache()
                    except Exception:
                        pass
                    try:
                        with open('digit_cache.json', 'r', encoding='utf-8') as f:
                            json.load(f)
                    except Exception:
                        pass
                finally:
                    app.config['WARMING'] = False
            threading.Thread(target=warm, daemon=True).start()
    except Exception:
        app.config['WARMING'] = False
    return jsonify({'status': 'ok'})

@app.get('/')
def index():
    return render_template('index.html')

@app.get('/learn')
def learn():
    return render_template('learn.html')

@app.get('/practice')
def practice():
    return render_template('practice.html')

# Helpers for words/phrases → digits mode
def strip_diacritics(s: str) -> str:
    try:
        nfkd = unicodedata.normalize('NFD', s)
        return ''.join(ch for ch in nfkd if not unicodedata.combining(ch))
    except Exception:
        return s

def tokenize_phrase(text: str):
    """
    Tokenize a phrase into word tokens:
    - Treat hyphens as separators
    - Split on whitespace
    - Remove punctuation and digits (keep letters incl. diacritics pre-normalization)
    - Strip diacritics and lowercase for normalized form
    Returns list of (original, normalized) tuples.
    """
    if not isinstance(text, str):
        return []
    raw = text.strip()
    # Treat hyphens as separators
    raw = raw.replace('-', ' ')
    # Split on whitespace
    parts = [p for p in re.split(r'\s+', raw) if p]
    tokens = []
    for p in parts:
        original = p
        # Keep letters only (Unicode Latin ranges)
        cleaned = re.sub(r'[^A-Za-zÀ-ÖØ-öø-ÿ]', '', p, flags=re.UNICODE).strip()
        if not cleaned:
            continue
        normalized = strip_diacritics(cleaned).lower()
        tokens.append((original, normalized))
    return tokens
@app.post('/api/convert')
def api_convert():
    data = request.get_json(silent=True) or {}
    number = str(data.get('number', '')).strip()
    blocks = data.get('blocks')
    # Words/Phrases → Digits (auto-detect by presence of letters in 'text')
    text = str((data.get('text') or '')).strip()
    if text:
        try:
            has_letters = any((ch.isalpha() for ch in text))
        except Exception:
            has_letters = False
        if has_letters:
            try:
                token_pairs = tokenize_phrase(text)
            except Exception:
                token_pairs = []
            items = []
            for orig, norm in token_pairs:
                try:
                    num = word_to_major_number(norm)
                except Exception:
                    num = ""
                items.append({'original': orig, 'normalized': norm, 'number': str(num or "")})
            full_number = ''.join(it['number'] for it in items)
            return jsonify({
                'mode': 'words',
                'input': text,
                'tokens': items,
                'tokenCount': len(items),
                'fullNumber': full_number,
                'digitCount': len(full_number),
            })

    # Cache em memória por requisição para evitar leituras repetidas do disco
    two_digit_cache = None
    def get_two_digit_cache():
        nonlocal two_digit_cache
        if two_digit_cache is None:
            try:
                with open('two_digit_cache.json', 'r', encoding='utf-8') as f:
                    two_digit_cache = json.load(f)
            except Exception:
                two_digit_cache = {}
        return two_digit_cache

    # Normalizar blocks se vierem como string
    if isinstance(blocks, str):
        blocks = [b for b in blocks.split() if b]
    # Se number contém espaços, considerar como blocks também
    if not blocks and (' ' in number):
        blocks = [b for b in number.split() if b]

    max_combos = data.get('maxCombos', 50)
    try:
        max_combos = int(max_combos)
    except (ValueError, TypeError):
        max_combos = 50

    # Se nada foi enviado
    if not number and not blocks:
        return jsonify({
            'input': '',
            'partitions': [],
            'totalResults': 0,
            'combosPreview': [],
            'combosPreviewCount': 0
        })

    # Validação de dígitos
    def only_digits(s: str) -> bool:
        return s.isdigit()

    if blocks:
        # Validação dos blocos
        if not all(isinstance(b, str) and only_digits(b) for b in blocks):
            return jsonify({'error': 'Blocos inválidos. Use apenas dígitos e espaços.'}), 400

        # Função auxiliar para obter palavras para um bloco específico
        def words_for_block(block: str):
            block = block.strip()
            words: list[str] = []
            if not block:
                return words
            if len(block) == 1:
                # Dígito único: usar cache/rotina existente
                try:
                    words = [w for (w, _) in find_single_digit_words(block)]
                except Exception:
                    words = []
            else:
                first_two = block[:2]
                try:
                    # 1) Tentar via cache de dois dígitos
                    cache = get_two_digit_cache()
                    if first_two in cache:
                        # Aceitar correspondências que começam com o bloco (mais abrangente)
                        words = [
                            wd.get('word')
                            for wd in cache.get(first_two, [])
                            if isinstance(wd, dict) and isinstance(wd.get('word'), str)
                            and isinstance(wd.get('number'), str) and wd.get('number') == block
                        ]
                    # 2) Fallback: usar algoritmo existente e filtrar pelo bloco (igualdade exata)
                    if not words:
                        sugg = find_pairs_combinations(block, verbose=False) or {}
                        collected = set()
                        for _, pairs in sugg.items():
                            for w, _src in pairs:
                                try:
                                    if isinstance(w, str) and word_to_major_number(w) == block:
                                        collected.add(w)
                                except Exception:
                                    continue
                        words = list(collected)
                except Exception:
                    # Em qualquer erro, garantir retorno seguro
                    words = []
            # Normalizar e ordenar
            words = sorted({w for w in words if isinstance(w, str) and w}, key=lambda w: w.lower())
            return words

        partitions = []
        total_results = 0
        for b in blocks:
            words_only = words_for_block(b)
            if words_only:
                total_results += len(words_only)
                partitions.append({'sequence': b, 'words': words_only})
            else:
                # Divisão gulosa esquerda->direita do bloco em sub-blocos exatos
                i = 0
                n = len(b)
                while i < n:
                    best_seq = None
                    best_words = []
                    for j in range(n, i, -1):
                        seg = b[i:j]
                        ws = words_for_block(seg)
                        if ws:
                            best_seq = seg
                            best_words = ws
                            break
                    if best_seq:
                        partitions.append({'sequence': best_seq, 'words': best_words})
                        total_results += len(best_words)
                        i += len(best_seq)
                    else:
                        # tentar dígito único para progredir
                        d = b[i]
                        ws = words_for_block(d)
                        if ws:
                            partitions.append({'sequence': d, 'words': ws})
                            total_results += len(ws)
                        i += 1
        
        # Gerar combinações apenas se todos os blocos/partições tiverem pelo menos uma palavra
        combos = []
        if partitions and all(p['words'] for p in partitions):
            for combo in product(*[p['words'] for p in partitions]):
                combos.append(' '.join(combo))
                if len(combos) >= max_combos:
                    break
        
        return jsonify({
            'input': ' '.join(blocks),
            'partitions': partitions,
            'totalResults': total_results,
            'combosPreview': combos,
            'combosPreviewCount': len(combos),
        })

    # Fluxo antigo (sem blocks): usar partições automáticas
    if not only_digits(number):
        return jsonify({'error': 'Número inválido. Use apenas dígitos.'}), 400

    suggestions = find_pairs_combinations(number, verbose=False) or {}

    partitions = []
    total_results = 0
    for seq, words in suggestions.items():
        # filtrar por correspondência exata ao bloco/segmento
        words_only = sorted(
            { w[0] for w in words if isinstance(w, (list, tuple)) and len(w) > 0 and word_to_major_number(w[0]) == seq },
            key=lambda w: w.lower()
        )
        total_results += len(words_only)
        partitions.append({'sequence': seq, 'words': words_only})

    # Fallback: se nada foi encontrado para a sequência inteira,
    # dividir a sequência em sub-blocos exatos (guloso esquerda->direita)
    if total_results == 0 and number:
        def exact_words(block: str):
            block = block.strip()
            if not block:
                return []
            # Dígito único
            if len(block) == 1:
                try:
                    return sorted({w for (w, _) in find_single_digit_words(block)}, key=lambda w: w.lower())
                except Exception:
                    return []
            # Dois+ dígitos
            words = []
            first_two = block[:2]
            try:
                cache = get_two_digit_cache()
                if first_two in cache:
                    words = [
                        wd.get('word')
                        for wd in cache.get(first_two, [])
                        if isinstance(wd, dict) and isinstance(wd.get('word'), str)
                        and isinstance(wd.get('number'), str) and wd.get('number') == block
                    ]
                if not words:
                    sugg_local = find_pairs_combinations(block, verbose=False) or {}
                    collected = set()
                    for _, pairs in sugg_local.items():
                        for w, _src in pairs:
                            try:
                                if isinstance(w, str) and word_to_major_number(w) == block:
                                    collected.add(w)
                            except Exception:
                                continue
                    words = list(collected)
            except Exception:
                words = []
            return sorted({w for w in words if isinstance(w, str) and w}, key=lambda w: w.lower())

        n = len(number)
        i = 0
        greedy_partitions = []
        while i < n:
            best_seq = None
            best_words = []
            for j in range(n, i, -1):
                seg = number[i:j]
                ws = exact_words(seg)
                if ws:
                    best_seq = seg
                    best_words = ws
                    break
            if best_seq:
                greedy_partitions.append({'sequence': best_seq, 'words': best_words})
                i += len(best_seq)
            else:
                # fallback para dígito único (para progredir e ainda tentar dar sugestões)
                d = number[i]
                ws = exact_words(d)
                if ws:
                    greedy_partitions.append({'sequence': d, 'words': ws})
                i += 1

        partitions = greedy_partitions
        total_results = sum(len(p['words']) for p in partitions)
    
    combos = []
    if partitions and all(p['words'] for p in partitions):
        for combo in product(*[p['words'] for p in partitions]):
            combos.append(' '.join(combo))
            if len(combos) >= max_combos:
                break
    
    return jsonify({
        'input': number,
        'partitions': partitions,
        'totalResults': total_results,
        'combosPreview': combos,
        'combosPreviewCount': len(combos),
    })

@app.get('/api/random_phrase')
def api_random_phrase():
    """
    Devolve uma frase (lista de palavras) escolhida aleatoriamente a partir da base (two_digit_cache.json).
    Parâmetros:
      - words: quantidade de palavras (1-6). Default: 2.
      - level: (opcional) por agora ignorado; futuro ajuste de dificuldade.
    """
    # parâmetros
    try:
        words_count = int(request.args.get('words', '2'))
    except (TypeError, ValueError):
        words_count = 2
    words_count = max(1, min(6, words_count))

    # carregar cache
    cache_file = 'two_digit_cache.json'
    try:
        with open(cache_file, 'r', encoding='utf-8') as f:
            cache = json.load(f)
    except Exception:
        return jsonify({'error': 'Cache indisponível para gerar frases.'}), 503

    # recolher palavras únicas válidas
    unique = {}
    if isinstance(cache, dict):
        for entries in cache.values():
            if not isinstance(entries, list):
                continue
            for wd in entries:
                if not isinstance(wd, dict):
                    continue
                w = wd.get('word')
                num = wd.get('number')
                if isinstance(w, str) and isinstance(num, str) and w and num:
                    # excluir palavras compostas/traços/apóstrofos
                    if (' ' in w) or ('-' in w) or ("'" in w):
                        continue
                    lw = w.strip().lower()
                    # manter única por minúsculas
                    if lw not in unique:
                        unique[lw] = {'word': w, 'number': num}

    pool = list(unique.values())
    if not pool:
        return jsonify({'error': 'Sem palavras disponíveis na cache para gerar frases.'}), 503

    # amostrar aleatoriamente
    if len(pool) <= words_count:
        chosen = pool
    else:
        chosen = random.sample(pool, words_count)

    phrase_words = [it['word'] for it in chosen]
    return jsonify({'words': phrase_words})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', '').lower() in ('1', 'true', 'yes', 'on')
    app.run(debug=debug, host='0.0.0.0', port=port)