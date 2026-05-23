use pyo3::prelude::*;

mod anagram;

type PyModuleBound<'py> = Bound<'py, PyModule>;

#[pyfunction]
fn group_anagrams(words: Vec<String>) -> PyResult<Vec<Vec<String>>> {
    Ok(anagram::group_anagrams(words))
}

#[pymodule]
fn main(_py: Python<'_>, m: &PyModuleBound<'_>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(group_anagrams, m)?)?;
    Ok(())
}
