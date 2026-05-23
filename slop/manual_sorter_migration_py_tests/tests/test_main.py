from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "manual_sorter"))

from main import bubble_sort  # noqa: E402


def test_bubble_sort_sorts_typical_unsorted_list() -> None:
    numbers = [3, 1, 4, 1, 5, 9, 2, 6]

    result = bubble_sort(numbers)

    assert result == [1, 1, 2, 3, 4, 5, 6, 9]


def test_bubble_sort_preserves_duplicates_in_sorted_output() -> None:
    numbers = [4, 2, 4, 1, 2]

    result = bubble_sort(numbers)

    assert result == [1, 2, 2, 4, 4]


def test_bubble_sort_returns_empty_list_for_empty_input() -> None:
    assert bubble_sort([]) == []


def test_bubble_sort_returns_singleton_for_single_item_input() -> None:
    assert bubble_sort([42]) == [42]


def test_bubble_sort_sorts_reverse_ordered_input() -> None:
    assert bubble_sort([5, 4, 3, 2, 1]) == [1, 2, 3, 4, 5]


def test_bubble_sort_keeps_already_sorted_values() -> None:
    numbers = [1, 2, 3, 4, 5]

    result = bubble_sort(numbers)

    assert result == [1, 2, 3, 4, 5]


def test_bubble_sort_does_not_mutate_input_list() -> None:
    numbers = [3, 2, 1]

    result = bubble_sort(numbers)

    assert numbers == [3, 2, 1]
    assert result == [1, 2, 3]


def test_bubble_sort_returns_new_list_object() -> None:
    numbers = [2, 1]

    result = bubble_sort(numbers)

    assert result == [1, 2]
    assert result is not numbers
