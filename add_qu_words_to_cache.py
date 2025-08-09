import json
import os
from main import word_to_major_number

def add_word_to_two_digit_cache(word):
    """
    Adds a word to the two_digit_cache.json file based on its first two digits
    """
    # Convert word to number
    number = word_to_major_number(word)
    
    if len(number) < 2:
        print(f"Word '{word}' maps to number '{number}' which is less than 2 digits")
        return
    
    # Get first two digits
    first_two = number[:2]
    
    # Load existing cache
    cache_file = 'two_digit_cache.json'
    if os.path.exists(cache_file):
        with open(cache_file, 'r', encoding='utf-8') as f:
            cache = json.load(f)
    else:
        cache = {}
    
    # Initialize entry for this pair if it doesn't exist
    if first_two not in cache:
        cache[first_two] = []
        print(f"Created new entry for {first_two}")
    
    # Create word data
    word_data = {
        "word": word,
        "number": number
    }
    
    # Check if word already exists in cache
    if not any(w["word"] == word for w in cache[first_two]):
        cache[first_two].append(word_data)
        print(f"Added '{word}' ({number}) to cache under {first_two}")
    else:
        print(f"Word '{word}' already exists in cache")
    
    # Save updated cache
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=4)
    
    return first_two

# Test words that start with "qu"
qu_words = [
    "quacacuja",
    "quebra", 
    "quiabo",
    "quociente",
    "quaderna",
    "quididade",
    "quieto",
    "quimera",
    "quintal",
    "quatorze"
]

print("Adding 'qu' words to cache:")
print("=" * 30)

for word in qu_words:
    try:
        first_two = add_word_to_two_digit_cache(word)
        print(f"  {word} -> {first_two}")
    except Exception as e:
        print(f"  Error adding {word}: {e}")
    print()

print("Done!")