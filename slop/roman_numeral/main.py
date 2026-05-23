def roman_to_int(roman: str) -> int:
    """Convert a Roman numeral string to an integer."""
    values = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    total = 0
    prev = 0
    for char in reversed(roman):
        value = values[char]
        if value < prev:
            total -= value
        else:
            total += value
            prev = value
    return total


if __name__ == "__main__":
    assert roman_to_int("III") == 3
    assert roman_to_int("IV") == 4
    assert roman_to_int("IX") == 9
    assert roman_to_int("MCMXCIV") == 1994
    assert roman_to_int("LVIII") == 58
