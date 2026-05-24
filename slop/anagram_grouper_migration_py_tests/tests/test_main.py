from __future__ import annotations

import importlib.util
from pathlib import Path

SOURCE_MAIN = (
    Path(__file__).resolve().parents[2].parent / "slop" / "anagram_grouper" / "main.py"
)
SPEC = importlib.util.spec_from_file_location("anagram_grouper_main", SOURCE_MAIN)
assert SPEC is not None
assert SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

group_anagrams = MODULE.group_anagrams


def test_group_anagrams_groups_mixed_words() -> None:
    words = ["eat", "tea", "tan", "ate", "nat", "bat"]

    result = group_anagrams(words)

    assert result == [["eat", "tea", "ate"], ["tan", "nat"], ["bat"]]


def test_group_anagrams_returns_empty_list_for_empty_input() -> None:
    assert group_anagrams([]) == []


def test_group_anagrams_returns_singleton_group_for_one_word() -> None:
    assert group_anagrams(["a"]) == [["a"]]


def test_group_anagrams_preserves_duplicate_words() -> None:
    assert group_anagrams(["ab", "ba", "ab"]) == [["ab", "ba", "ab"]]


def test_group_anagrams_returns_single_group_when_all_are_anagrams() -> None:
    assert group_anagrams(["listen", "silent", "enlist"]) == [
        ["listen", "silent", "enlist"]
    ]


def test_group_anagrams_preserves_first_seen_group_order_and_word_order() -> None:
    words = ["abc", "foo", "bca", "ofo", "cab", "bar"]

    result = group_anagrams(words)

    assert result == [["abc", "bca", "cab"], ["foo", "ofo"], ["bar"]]


def test_group_anagrams_keeps_non_anagrams_in_separate_groups() -> None:
    assert group_anagrams(["ab", "cd", "ef"]) == [["ab"], ["cd"], ["ef"]]


def test_group_anagrams_groups_unicode_words_by_sorted_characters() -> None:
    words = ["åä", "äå", "ö", "o"]

    result = group_anagrams(words)

    assert result == [["åä", "äå"], ["ö"], ["o"]]
