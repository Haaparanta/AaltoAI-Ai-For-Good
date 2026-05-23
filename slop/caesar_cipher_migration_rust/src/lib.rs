use pyo3::prelude::*;
use pyo3::types::PyModule;
use pyo3::Bound;

fn cipher_impl(text: &str, shift: i32) -> String {
    let normalized_shift = shift.rem_euclid(26);
    let mut result = String::with_capacity(text.len());

    for ch in text.chars() {
        if ch.is_ascii_lowercase() {
            let offset = b'a';
            let shifted = (((ch as u8 - offset) as i32 + normalized_shift) % 26) as u8 + offset;
            result.push(shifted as char);
        } else if ch.is_ascii_uppercase() {
            let offset = b'A';
            let shifted = (((ch as u8 - offset) as i32 + normalized_shift) % 26) as u8 + offset;
            result.push(shifted as char);
        } else {
            result.push(ch);
        }
    }

    result
}

#[pyfunction]
fn cipher(text: &str, shift: i32) -> PyResult<String> {
    Ok(cipher_impl(text, shift))
}

#[pymodule]
fn main(_py: Python<'_>, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(cipher, m)?)?;
    Ok(())
}
