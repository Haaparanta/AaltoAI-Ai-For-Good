use pyo3::prelude::*;
use pyo3::types::PyModule;

fn bubble_sort_impl(numbers: &[i64]) -> Vec<i64> {
    let mut result = numbers.to_vec();
    let n = result.len();

    for i in 0..n {
        let mut swapped = false;
        for j in 0..(n - i).saturating_sub(1) {
            if result[j] > result[j + 1] {
                result.swap(j, j + 1);
                swapped = true;
            }
        }
        if !swapped {
            break;
        }
    }

    result
}

#[pyfunction]
fn bubble_sort(numbers: Vec<i64>) -> PyResult<Vec<i64>> {
    Ok(bubble_sort_impl(&numbers))
}

#[pymodule]
fn main(_py: Python<'_>, module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(bubble_sort, module)?)?;
    Ok(())
}
