def bubble_sort(numbers: list[int]) -> list[int]:
    """Sort numbers in ascending order using bubble sort with early-exit optimization."""
    result = numbers[:]
    n = len(result)
    for i in range(n):
        swapped = False
        for j in range(n - i - 1):
            if result[j] > result[j + 1]:
                result[j], result[j + 1] = result[j + 1], result[j]
                swapped = True
        if not swapped:
            break
    return result


if __name__ == "__main__":
    assert bubble_sort([3, 1, 4, 1, 5, 9, 2, 6]) == [1, 1, 2, 3, 4, 5, 6, 9]
    assert bubble_sort([]) == []
    assert bubble_sort([42]) == [42]
    assert bubble_sort([5, 4, 3, 2, 1]) == [1, 2, 3, 4, 5]
    assert bubble_sort([1, 2, 3, 4, 5]) == [1, 2, 3, 4, 5]
