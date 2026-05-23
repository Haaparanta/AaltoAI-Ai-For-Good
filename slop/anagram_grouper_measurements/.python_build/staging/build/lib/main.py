def group_anagrams(words: list[str]) -> list[list[str]]:
    """Group words that are anagrams of each other into sublists."""
    groups: dict[tuple[str, ...], list[str]] = {}
    for word in words:
        key = tuple(sorted(word))
        groups.setdefault(key, []).append(word)
    return list(groups.values())


if __name__ == "__main__":
    result = group_anagrams(["eat", "tea", "tan", "ate", "nat", "bat"])
    expected = [["eat", "tea", "ate"], ["tan", "nat"], ["bat"]]
    assert sorted([sorted(g) for g in result]) == sorted([sorted(g) for g in expected])
    assert group_anagrams([]) == []
    assert group_anagrams(["a"]) == [["a"]]
    assert group_anagrams(["ab", "ba", "ab"]) == [["ab", "ba", "ab"]]
    assert len(group_anagrams(["listen", "silent", "enlist"])) == 1
