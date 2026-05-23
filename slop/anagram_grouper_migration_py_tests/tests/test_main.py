from main import group_anagrams


def test_group_anagrams_groups_common_example_in_first_seen_order() -> None:
    words = ["eat", "tea", "tan", "ate", "nat", "bat"]

    result = group_anagrams(words)

    assert result == [["eat", "tea", "ate"], ["tan", "nat"], ["bat"]]


def test_group_anagrams_returns_empty_list_for_empty_input() -> None:
    assert group_anagrams([]) == []


def test_group_anagrams_returns_singleton_group_for_single_word() -> None:
    assert group_anagrams(["a"]) == [["a"]]


def test_group_anagrams_preserves_duplicate_words() -> None:
    assert group_anagrams(["ab", "ba", "ab"]) == [["ab", "ba", "ab"]]


def test_group_anagrams_returns_single_group_when_all_words_are_anagrams() -> None:
    assert group_anagrams(["listen", "silent", "enlist"]) == [
        ["listen", "silent", "enlist"]
    ]


def test_group_anagrams_keeps_same_length_non_anagrams_separate() -> None:
    words = ["ab", "cd", "bc", "dc"]

    result = group_anagrams(words)

    assert result == [["ab"], ["cd", "dc"], ["bc"]]


def test_group_anagrams_is_case_sensitive() -> None:
    words = ["ab", "ba", "Ab", "bA"]

    result = group_anagrams(words)

    assert result == [["ab", "ba"], ["Ab", "bA"]]
