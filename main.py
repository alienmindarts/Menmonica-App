import requests
from functools import lru_cache
import asyncio
import aiohttp
import os
import json

# Mapeamento do Sistema Fonético Major
major_system_mapping = {
    "0": ["z", "s", "ss", "ç", "c"],
    "1": ["t", "d"], 
    "2": ["n", "nh"],
    "3": ["m"],
    "4": ["r", "rr"],  # "rr" é agora parte do algarismo 4
    "5": ["l"],
    "6": ["j", "sc", "x", "ch", "g", "ge", "gi"],
    "7": ["q", "c", "g"],  # "g" será tratado separadamente
    "8": ["f", "v"],
    "9": ["p", "b"]
}

# Inverso do mapeamento
inverse_mapping = {v: k for k, vs in major_system_mapping.items() for v in vs}

# In-memory cache for two_digit_cache.json to avoid repeated disk I/O during requests
two_digit_cache = None
two_digit_cache_mtime = 0.0

def load_two_digit_cache():
    global two_digit_cache, two_digit_cache_mtime
    cache_file = 'two_digit_cache.json'
    try:
        mtime = os.path.getmtime(cache_file)
    except OSError:
        two_digit_cache = {}
        two_digit_cache_mtime = 0.0
        return two_digit_cache
    if two_digit_cache is None or two_digit_cache_mtime != mtime:
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                two_digit_cache = json.load(f)
            two_digit_cache_mtime = mtime
        except Exception:
            two_digit_cache = {}
            two_digit_cache_mtime = mtime
    return two_digit_cache

# Função para converter uma palavra em um número pelo sistema fonético Major
@lru_cache(maxsize=8192)
def word_to_major_number(word):
    number = ""
    word = word.lower()
    i = 0
    while i < len(word):
        # Verificar se encontramos "ss", para tratar como "0"
        if i + 1 < len(word) and word[i] == "s" and word[i + 1] == "s":
            number += "0"
            i += 2  # Pular o próximo "s"
        # Verificar se encontramos "ll", para tratar como "5"
        elif i + 1 < len(word) and word[i] == "l" and word[i + 1] == "l":
            number += "5"
            i += 2  # Pular o próximo "l"
        # Verificar se encontramos "rr", para tratar como "4"
        elif i + 1 < len(word) and word[i] == "r" and word[i + 1] == "r":
            number += "4"
            i += 2  # Pular o próximo "r"
        # Verificar se encontramos "ch", para tratar como "6"
        elif i + 1 < len(word) and word[i] == "c" and word[i + 1] == "h":
            number += "6"
            i += 2  # Pular o "h"
        # Verificar se "c" é seguido de "e" ou "i", para tratá-lo como "0"
        elif word[i] == "c" and (i + 1 < len(word) and word[i + 1] in "ei"):
            number += "0"
            i += 2  # Pular o próximo "e" ou "i"
        # Verificar se "g" é seguido de "e" ou "i", para tratá-lo como "6"
        elif word[i] == "g" and (i + 1 < len(word) and word[i + 1] in "ei"):
            number += "6"
            i += 2  # Pular o próximo "e" ou "i"
        # Verificar se "g" é seguido de "a", "o" ou "u", para tratá-lo como "7"
        elif word[i] == "g" and (i + 1 < len(word) and word[i + 1] in "aou"):
            number += "7"
            i += 2  # Pular o próximo "a", "o" ou "u"
        elif word[i] in inverse_mapping:
            number += inverse_mapping[word[i]]
            i += 1
        else:
            i += 1  # Pular letras que não fazem parte do mapeamento
    return number


# Função para gerar combinações de vogais entre consoantes
def generate_vowel_combinations(consonants):
    vowels = ["a", "e", "i", "o", "u"]
    combinations = []

    # Combinações com vogais antes, no meio e depois das consoantes
    for v1 in vowels:
        combinations.append(f"{v1}{consonants[0]}{consonants[1]}")
        for v2 in vowels:
            combinations.append(f"{v1}{consonants[0]}{v2}{consonants[1]}")

    # Combinações de vogal no meio (por exemplo, imp, inc)
    for v1 in vowels:
        combinations.append(f"{consonants[0]}{v1}{consonants[1]}")
        for v2 in vowels:
            combinations.append(f"{consonants[0]}{v1}{v2}{consonants[1]}")

    # Combinações com vogal no final
    for v1 in vowels:
        combinations.append(f"{consonants[0]}{consonants[1]}{v1}")
        for v2 in vowels:
            combinations.append(f"{consonants[0]}{v2}{consonants[1]}{v1}")

    return combinations

# Função para gerar combinações de vogais especiais (duas vogais diferentes)
def generate_special_vowel_combinations(consonant):
    special_vowels = ["ae", "ai", "ao", "au", "ea", "ei", "eo", "eu", "ia", "ie", "io", "iu", "oa", "oe", "oi", "ou", "ua", "ue", "ui", "uo"]
    combinations = []
    for v in special_vowels:
        combinations.append(f"{consonant}{v}")  # Cruzando a primeira consoante com as vogais especiais
        combinations.append(f"{v}{consonant}")  # Vogais especiais + consoante
    return combinations

# Cache API results to avoid redundant requests
@lru_cache(maxsize=None)
def fetch_words_from_api(query, search_type):
    url = f"https://api.dicionario-aberto.net/{search_type}/{query}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.json() if isinstance(response.json(), list) else []
    except Exception as e:
        print(f"Erro ao buscar {query}: {e}")
    return []

def is_cache_complete():
    """
    Verifica se a cache tem todas as combinações de dois dígitos (00-99)
    """
    cache_file = 'two_digit_cache.json'
    if not os.path.exists(cache_file):
        return False
        
    with open(cache_file, 'r', encoding='utf-8') as f:
        cache = json.load(f)
        
    # Verifica se todos os pares de 00 a 99 existem
    for i in range(10):
        for j in range(10):
            pair = f"{i}{j}"
            if pair not in cache:
                return False
    return True

def save_to_cache(words, search_pair):
    """
    Salva palavras na cache organizadas pelos seus dois primeiros dígitos
    """
    global two_digit_cache, two_digit_cache_mtime
    cache_file = 'two_digit_cache.json'

    # Criar ou carregar cache em memória (evita I/O repetido)
    cache = load_two_digit_cache()
    if not isinstance(cache, dict):
        cache = {}

    # Inicializar entrada para o par buscado se não existir
    if search_pair not in cache:
        cache[search_pair] = []
        print(f"Novo par adicionado à cache: {search_pair}")

    # Adicionar todas as palavras encontradas
    for word, _ in words:
        converted_number = word_to_major_number(word)
        word_data = {
            "word": word,
            "number": converted_number
        }
        if not any((isinstance(w, dict) and w.get("word") == word) for w in cache[search_pair]):
            cache[search_pair].append(word_data)
            print(f"✓ Nova palavra adicionada ao cache em {search_pair}: {word} ({converted_number})")

    # Salvar cache atualizado no disco
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=4)

    # Atualizar cache em memória e mtime
    try:
        two_digit_cache = cache
        two_digit_cache_mtime = os.path.getmtime(cache_file)
    except Exception:
        pass

def check_pair_in_cache(pair):
    """
    Verifica se um par específico de dígitos já está na cache
    """
    cache = load_two_digit_cache()
    return pair in cache and len(cache.get(pair, [])) > 0  # Retorna True apenas se tiver palavras

def find_words_by_number(number, exact_match=True):
    """
    Encontra palavras que correspondem ao número, usando a cache se disponível
    """
    if len(number) < 2:
        print("O número deve ter pelo menos dois dígitos.")
        return []

    first_two = number[:2]
    
    # Verificar se este par já está na cache
    if check_pair_in_cache(first_two):
        print(f"Usando cache para {first_two}...")
        cache = load_two_digit_cache()
        matching_words = []
        for word_data in cache.get(first_two, []):
            if exact_match and word_data.get("number") == number:
                matching_words.append((word_data.get("word"), ""))
            elif not exact_match and number.startswith(word_data.get("number", "")):
                matching_words.append((word_data.get("word"), ""))
        return matching_words
    
    # Se não estiver na cache, buscar na API e salvar
    print(f"Buscando novas palavras para {first_two}...")
    # Para pares que começam com 7, procurar especificamente combinações com "qu"
    if first_two.startswith("7"):
        # Procurar palavras que começam com "qu"
        qu_combinations = ["qua", "que", "qui", "quo"]
        found_words = set()
        for comb in qu_combinations:
            prefix_results = fetch_words_from_api(comb, "prefix")
            # Filtrar palavras que começam com "qu"
            for word_data in prefix_results:
                word = word_data.get("word", "")
                if word and word.lower().startswith("qu"):
                    converted_number = word_to_major_number(word)
                    if converted_number.startswith(first_two):
                        found_words.add((word, comb))
        words = list(found_words)
    else:
        # Código original de busca na API para outros pares
        words = []  # Aqui vai o código original de busca na API
    
    # Salvar resultados na cache
    if words:
        save_to_cache(words, first_two)
    
    return words

def find_best_number_combinations(number):
    """
    Encontra a palavra que coincide com o maior número de dígitos do número fornecido.
    """
    best_match = None
    best_match_length = 0
    
    print(f"\nBuscando melhor palavra para {number}...")
    
    # Verificar palavras para os primeiros dois dígitos
    first_two = number[:2]
    words = find_words_by_number(first_two, exact_match=False)
    
    for word, _ in words:
        converted = word_to_major_number(word)
        if len(converted) > best_match_length and number.startswith(converted):
            best_match = word
            best_match_length = len(converted)
            print(f"✓ Melhor palavra encontrada: {word} ({converted})")
    
    if best_match:
        print(f"\nMelhor correspondência encontrada: {best_match}")
    else:
        print("\nNenhuma palavra encontrada.")

@lru_cache(maxsize=32)
def find_single_digit_words(digit):
    """
    Busca palavras que representam um único dígito na API
    """
    cache_file = 'digit_cache.json'
    
    # Carregar ou criar cache
    if os.path.exists(cache_file):
        with open(cache_file, 'r', encoding='utf-8') as f:
            cache = json.load(f)
    else:
        cache = {}
    
    # Se já temos palavras para este dígito na cache, retornar
    if digit in cache:
        return [(word_data["word"], "") for word_data in cache[digit]]
    
    # Buscar na API usando as consoantes do dígito
    consonant_options = major_system_mapping[digit]
    found_words = set()
    searched_combinations = set()
    
    # Vogais simples e compostas
    vowels = ["a", "e", "i", "o", "u"]
    vowel_combinations = [
        "ae", "ai", "ao", "au",
        "ea", "ei", "eo", "eu",
        "ia", "ie", "io", "iu",
        "oa", "oe", "oi", "ou",
        "ua", "ue", "ui", "uo"
    ]
    
    # Para o dígito 7 (que inclui "q"), procurar especificamente combinações com "qu"
    if digit == "7":
        # Procurar palavras que começam com "qu"
        qu_combinations = ["qua", "que", "qui", "quo"]
        for comb in qu_combinations:
            if comb not in searched_combinations:
                searched_combinations.add(comb)
                prefix_results = fetch_words_from_api(comb, "prefix")
                # Filtrar palavras que começam com "qu"
                for word_data in prefix_results:
                    word = word_data.get("word", "")
                    if word and word.lower().startswith("qu") and word_to_major_number(word) == digit:
                        found_words.add((word, comb))
    
    for consonant in consonant_options:
        # Padrão CV (Consoante + Vogal)
        for vowel in vowels + vowel_combinations:
            query = f"{consonant}{vowel}"
            if query not in searched_combinations:
                searched_combinations.add(query)
                prefix_results = fetch_words_from_api(query, "prefix")
                infix_results = fetch_words_from_api(query, "infix")
                
                all_results = {word_data.get("word", "") for word_data in prefix_results + infix_results}
                for word in all_results:
                    if word and word_to_major_number(word) == digit:
                        found_words.add((word, query))
        
        # Padrão VC (Vogal + Consoante)
        for vowel in vowels:
            query = f"{vowel}{consonant}"
            if query not in searched_combinations:
                searched_combinations.add(query)
                prefix_results = fetch_words_from_api(query, "prefix")
                infix_results = fetch_words_from_api(query, "infix")
                
                all_results = {word_data.get("word", "") for word_data in prefix_results + infix_results}
                for word in all_results:
                    if word and word_to_major_number(word) == digit:
                        found_words.add((word, query))
        
        # Padrão VCV (Vogal + Consoante + Vogal)
        for v1 in vowels:
            for v2 in vowels:
                query = f"{v1}{consonant}{v2}"
                if query not in searched_combinations:
                    searched_combinations.add(query)
                    prefix_results = fetch_words_from_api(query, "prefix")
                    infix_results = fetch_words_from_api(query, "infix")
                    
                    all_results = {word_data.get("word", "") for word_data in prefix_results + infix_results}
                    for word in all_results:
                        if word and word_to_major_number(word) == digit:
                            found_words.add((word, query))
    
    # Salvar palavras encontradas na cache
    words = list(found_words)
    if words:
        cache[digit] = [{"word": word, "number": digit} for word, _ in words]
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=4)
    
    return words

def find_pairs_combinations(number, verbose=True):
    best_coverage = {}
    remaining_number = number
    
    if verbose:
        print(f"\nBuscando palavras para {number}...")
    
    while remaining_number:
        best_words = []
        best_length = 0
        
        # Tentar palavras de dois ou mais dígitos primeiro
        if len(remaining_number) >= 2:
            initial_pair = remaining_number[:2]
            
            # Buscar palavras (da cache ou API)
            if check_pair_in_cache(initial_pair):
                cache = load_two_digit_cache()
                words = [(word_data.get("word"), "") for word_data in cache.get(initial_pair, [])]
            else:
                # Para pares que começam com 7, procurar especificamente combinações com "qu"
                if initial_pair.startswith("7"):
                    # Procurar palavras que começam com "qu"
                    qu_combinations = ["qua", "que", "qui", "quo"]
                    found_words = set()
                    for comb in qu_combinations:
                        prefix_results = fetch_words_from_api(comb, "prefix")
                        # Filtrar palavras que começam com "qu"
                        for word_data in prefix_results:
                            word = word_data.get("word", "")
                            if word and word.lower().startswith("qu"):
                                converted_number = word_to_major_number(word)
                                if converted_number.startswith(initial_pair):
                                    found_words.add((word, comb))
                    words = list(found_words)
                else:
                    # Código existente de busca na API
                    words = []
                if words:
                    save_to_cache(words, initial_pair)
            
            # Processar palavras encontradas para o par
            for word, _ in words:
                converted_number = word_to_major_number(word)
                if remaining_number.startswith(converted_number):
                    digits = len(converted_number)
                    if digits > best_length:
                        best_length = digits
                        best_words = [(word, "")]
                    elif digits == best_length:
                        best_words.append((word, ""))
        
        # Se não encontrou palavras para o par, tentar dígito único
        if not best_words and len(remaining_number) >= 1:
            single_digit = remaining_number[0]
            single_digit_words = find_single_digit_words(single_digit)
            
            if single_digit_words:
                if verbose:
                    print(f"Encontrada(s) palavra(s) para o dígito {single_digit}")
                best_words = single_digit_words
                best_length = 1
        
        if best_words:
            covered_part = remaining_number[:best_length]
            best_coverage[covered_part] = best_words
            remaining_number = remaining_number[best_length:]
        else:
            remaining_number = remaining_number[1:]
            if not remaining_number:
                break
    
    # Mostrar resultados
    if best_coverage:
        if verbose:
            print("\nPalavras encontradas:")
        for sequence, words in best_coverage.items():
            word_list = [word[0] for word in words]
            if verbose:
                print(f"• {sequence}: {word_list}")
    elif verbose:
        print("\nNenhuma palavra encontrada.")
    
    return best_coverage

def show_cache_status():
    """
    Mostra informações sobre o estado atual da cache
    """
    if os.path.exists('two_digit_cache.json'):
        with open('two_digit_cache.json', 'r', encoding='utf-8') as f:
            cache = json.load(f)
            total_pairs = len(cache)
            total_words = sum(len(words) for words in cache.values())
            print(f"\nStatus da cache:")
            print(f"• Pares de dígitos salvos: {total_pairs}")
            print(f"• Total de palavras: {total_words}")
    else:
        print("\nCache ainda não existe.")

def clear_screen():
    """Clear the screen in a cross-platform way"""
    os.system('cls' if os.name == 'nt' else 'clear')

def display_interface(current_number, suggestions):
    """Display the current interface state"""
    clear_screen()
    print("\n=== Sistema Fonético Major ===")
    print("\nControles:")
    print("• Backspace: apagar último dígito")
    print("• Esc: sair do programa")
    print("\n" + "="*30)
    print(f"\nNúmero atual: {current_number}")
    
    if suggestions:
        print("\nSugestões:")
        for sequence, words in suggestions.items():
            word_list = [word[0] for word in words]
            print(f"• {sequence}: {', '.join(word_list)}")

def main():
    print("\nBem-vindo ao buscador de palavras pelo Sistema Fonético Major!")
    show_cache_status()
    
    current_number = ""
    
    while True:
        try:
            import msvcrt  # Windows
            char = msvcrt.getch()
            
            # Handle special keys in Windows
            if char == b'\xe0':  # Arrow key prefix
                msvcrt.getch()  # Consume the second byte of arrow key
                continue
            elif char in (b'\x08', b'\x7f'):  # Backspace
                current_number = current_number[:-1]
            elif char == b'\x1b':  # Esc
                break
            else:
                try:
                    char = char.decode('utf-8')
                    if char.isdigit():
                        current_number += char
                except UnicodeDecodeError:
                    continue
                    
        except (ImportError, AttributeError):
            # Unix-like systems
            import sys, tty, termios
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(sys.stdin.fileno())
                char = sys.stdin.read(1)
                
                # Handle special keys in Unix
                if ord(char) == 27:  # ESC or arrow key prefix
                    # Check if it's an arrow key (ESC followed by [ and A/B/C/D)
                    if sys.stdin.read(1) == '[':
                        sys.stdin.read(1)  # Consume the arrow key character
                        continue
                    else:
                        break  # Just ESC key
                elif ord(char) in (8, 127):  # Backspace
                    current_number = current_number[:-1]
                elif char.isdigit():
                    current_number += char
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        
        # Update display after each input
        suggestions = find_pairs_combinations(current_number, verbose=False) if current_number else {}
        display_interface(current_number, suggestions)

    print("\033[H\033[J")  # Clear screen at exit
    print("Programa encerrado.")

if __name__ == "__main__":
    main()
