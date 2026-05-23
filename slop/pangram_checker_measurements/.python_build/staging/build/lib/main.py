def is_pangram(text: str) -> bool:
    """Return True if text contains every English letter at least once."""
    letters = {char.lower() for char in text if char.isalpha()}
    return len(letters) == 26


if __name__ == "__main__":
    assert is_pangram("The quick brown fox jumps over the lazy dog") is True
    assert is_pangram("Pack my box with five dozen liquor jugs.") is True
    assert is_pangram("Hello, World!") is False
    assert is_pangram("") is False
    assert is_pangram("abcdefghijklmnopqrstuvwxyz") is True
