use pyo3::prelude::*;

#[pyfunction]
fn is_pangram(text: &str) -> bool {
    let letters = text
        .chars()
        .filter(|c| c.is_alphabetic())
        .flat_map(|c| c.to_lowercase())
        .collect::<std::collections::HashSet<char>>();
    letters.len() == 26
}

#[pymodule]
fn pangram_checker(_py: Python<'_>, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(is_pangram, m)?)?;
    Ok(())
}
