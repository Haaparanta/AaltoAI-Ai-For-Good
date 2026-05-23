def get_primes(n: int) -> list[int]:
    """Return all prime numbers up to and including n using the Sieve of Eratosthenes."""
    if n < 2:
        return []
    is_prime = [True] * (n + 1)
    is_prime[0] = is_prime[1] = False
    for i in range(2, int(n**0.5) + 1):
        if is_prime[i]:
            for j in range(i * i, n + 1, i):
                is_prime[j] = False
    return [i for i in range(2, n + 1) if is_prime[i]]


if __name__ == "__main__":
    assert get_primes(1) == []
    assert get_primes(2) == [2]
    assert get_primes(10) == [2, 3, 5, 7]
    assert get_primes(20) == [2, 3, 5, 7, 11, 13, 17, 19]
    assert get_primes(0) == []
