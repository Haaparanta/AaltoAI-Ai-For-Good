def cipher(text: str, shift: int) -> str:
    """Shift each letter in text by shift positions, preserving case and non-letters."""
    result = []
    for char in text:
        if "a" <= char <= "z":
            offset = ord("a")
            result.append(chr((ord(char) - offset + shift) % 26 + offset))
        elif "A" <= char <= "Z":
            offset = ord("A")
            result.append(chr((ord(char) - offset + shift) % 26 + offset))
        else:
            result.append(char)
    return "".join(result)


if __name__ == "__main__":
    assert cipher("abc", 1) == "bcd"
    assert cipher("xyz", 3) == "abc"
    assert cipher("Hello, World!", 13) == "Uryyb, Jbeyq!"
    assert cipher("ABC", -1) == "ZAB"
    assert cipher("", 5) == ""
