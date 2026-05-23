use pyo3::prelude::*;

#[pyfunction]
fn get_primes(n: isize) -> PyResult<Vec<isize>> {
    if n < 2 {
        return Ok(Vec::new());
    }

    let n = n as usize;
    let mut is_prime = vec![true; n + 1];
    is_prime[0] = false;
    is_prime[1] = false;

    let mut i = 2usize;
    while i * i <= n {
        if is_prime[i] {
            let mut j = i * i;
            while j <= n {
                is_prime[j] = false;
                j += i;
            }
        }
        i += 1;
    }

    let primes = (2..=n)
        .filter(|&idx| is_prime[idx])
        .map(|idx| idx as isize)
        .collect();

    Ok(primes)
}

#[pymodule]
fn prime_generator(_py: Python<'_>, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(get_primes, m)?)?;
    Ok(())
}
