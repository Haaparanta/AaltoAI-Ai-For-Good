use pyo3::exceptions::PyKeyError;
use pyo3::prelude::*;

mod roman;

#[pyfunction]
fn roman_to_int(roman: &str) -> PyResult<i32> {
    roman::roman_to_int_impl(roman).map_err(PyKeyError::new_err)
}

#[pymodule]
fn roman_numeral(_py: Python<'_>, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(roman_to_int, m)?)?;
    Ok(())
}
