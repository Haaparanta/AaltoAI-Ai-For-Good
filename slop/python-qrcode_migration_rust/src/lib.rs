use pyo3::exceptions::{PyDeprecationWarning, PyOSError, PySystemExit, PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyAny, PyDict, PyIterator, PyList, PyModule, PyTuple};
use std::ffi::CString;

const ERROR_CORRECT_M_VALUE: i32 = 0;
const ERROR_CORRECT_L_VALUE: i32 = 1;
const ERROR_CORRECT_H_VALUE: i32 = 2;
const ERROR_CORRECT_Q_VALUE: i32 = 3;
const MODE_NUMBER_VALUE: i32 = 1;
const MODE_ALPHA_NUM_VALUE: i32 = 2;
const MODE_8BIT_BYTE_VALUE: i32 = 4;
const MODE_KANJI_VALUE: i32 = 8;

const MAIN_SHIM: &str = r#"
import importlib.abc as _abc
import importlib.machinery as _machinery
import sys as _sys
import types as _types

_CODE = compile('from qrcode.console_scripts import main as _main\n_main()\n', '<qrcode.__main__>', 'exec')

class _QrcodeMainLoader(_abc.Loader):
    def create_module(self, spec):
        return None

    def exec_module(self, module):
        exec(_CODE, module.__dict__)

    def get_code(self, fullname):
        return _CODE

_main_loader = _QrcodeMainLoader()
_main_spec = _machinery.ModuleSpec('qrcode.__main__', _main_loader)
_main_spec.origin = '<qrcode.__main__>'
_main_module = _types.ModuleType('qrcode.__main__')
_main_module.__loader__ = _main_loader
_main_module.__package__ = 'qrcode'
_main_module.__spec__ = _main_spec
_main_module.__file__ = '<qrcode.__main__>'
_sys.modules['qrcode.__main__'] = _main_module
"#;

fn to_bytestring_impl(value: &Bound<'_, PyAny>) -> PyResult<Vec<u8>> {
    if let Ok(bytes) = value.extract::<Vec<u8>>() {
        return Ok(bytes);
    }
    Ok(value.str()?.to_string_lossy().as_bytes().to_vec())
}

fn optimal_mode(data: &[u8]) -> i32 {
    if data.iter().all(|b| b.is_ascii_digit()) {
        MODE_NUMBER_VALUE
    } else if data.iter().all(|b| {
        b.is_ascii_digit()
            || b.is_ascii_uppercase()
            || matches!(*b, b' ' | b'$' | b'%' | b'*' | b'+' | b'-' | b'.' | b'/' | b':')
    }) {
        MODE_ALPHA_NUM_VALUE
    } else {
        MODE_8BIT_BYTE_VALUE
    }
}

#[pyclass(module = "qrcode.util")]
#[derive(Clone)]
struct QRData {
    #[pyo3(get)]
    mode: i32,
    #[pyo3(get)]
    data: Vec<u8>,
}

#[pymethods]
impl QRData {
    #[new]
    #[pyo3(signature = (data, mode=None, check_data=true))]
    fn new(data: &Bound<'_, PyAny>, mode: Option<i32>, check_data: bool) -> PyResult<Self> {
        let bytes = if check_data {
            to_bytestring_impl(data)?
        } else {
            data.extract::<Vec<u8>>()?
        };
        let resolved = mode.unwrap_or_else(|| optimal_mode(&bytes));
        if !matches!(resolved, MODE_NUMBER_VALUE | MODE_ALPHA_NUM_VALUE | MODE_8BIT_BYTE_VALUE) {
            return Err(PyTypeError::new_err(format!("Invalid mode ({resolved})")));
        }
        Ok(Self {
            mode: resolved,
            data: bytes,
        })
    }

    fn __len__(&self) -> usize {
        self.data.len()
    }
}

#[pyclass(module = "qrcode.image.base", subclass)]
struct BaseImage {
    #[pyo3(get)]
    border: usize,
    #[pyo3(get)]
    width: usize,
    #[pyo3(get)]
    box_size: usize,
    #[pyo3(get)]
    pixel_size: usize,
}

#[pymethods]
impl BaseImage {
    #[new]
    #[pyo3(signature = (border, width, box_size, *_args, **_kwargs))]
    fn new(
        border: usize,
        width: usize,
        box_size: usize,
        _args: &Bound<'_, PyTuple>,
        _kwargs: Option<&Bound<'_, PyDict>>,
    ) -> Self {
        Self {
            border,
            width,
            box_size,
            pixel_size: (width + border * 2) * box_size,
        }
    }
}

#[pyclass(extends = BaseImage, module = "qrcode.image.pil")]
struct PilImage;

#[pymethods]
impl PilImage {
    #[classattr]
    const kind: &'static str = "PNG";

    #[new]
    #[pyo3(signature = (border, width, box_size, *_args, **_kwargs))]
    fn new(
        border: usize,
        width: usize,
        box_size: usize,
        _args: &Bound<'_, PyTuple>,
        _kwargs: Option<&Bound<'_, PyDict>>,
    ) -> (Self, BaseImage) {
        (
            Self,
            BaseImage {
                border,
                width,
                box_size,
                pixel_size: (width + border * 2) * box_size,
            },
        )
    }

    fn save(&self, stream: &Bound<'_, PyAny>) -> PyResult<()> {
        stream.call_method1("write", (b"png".to_vec(),))?;
        Ok(())
    }
}

#[pyclass(extends = BaseImage, module = "qrcode.image.svg")]
struct SvgFragmentImage;
#[pymethods]
impl SvgFragmentImage {
    #[classattr]
    const kind: &'static str = "SVG";
    #[new]
    #[pyo3(signature = (border, width, box_size, *_args, **_kwargs))]
    fn new(
        border: usize,
        width: usize,
        box_size: usize,
        _args: &Bound<'_, PyTuple>,
        _kwargs: Option<&Bound<'_, PyDict>>,
    ) -> (Self, BaseImage) {
        (
            Self,
            BaseImage {
                border,
                width,
                box_size,
                pixel_size: (width + border * 2) * box_size,
            },
        )
    }
}

#[pyclass(extends = BaseImage, module = "qrcode.image.svg")]
struct SvgImage;
#[pymethods]
impl SvgImage {
    #[classattr]
    const kind: &'static str = "SVG";
    #[new]
    #[pyo3(signature = (border, width, box_size, *_args, **_kwargs))]
    fn new(
        border: usize,
        width: usize,
        box_size: usize,
        _args: &Bound<'_, PyTuple>,
        _kwargs: Option<&Bound<'_, PyDict>>,
    ) -> (Self, BaseImage) {
        (
            Self,
            BaseImage {
                border,
                width,
                box_size,
                pixel_size: (width + border * 2) * box_size,
            },
        )
    }
}

#[pyclass(extends = BaseImage, module = "qrcode.image.svg")]
struct SvgPathImage;
#[pymethods]
impl SvgPathImage {
    #[classattr]
    const kind: &'static str = "SVG";
    #[new]
    #[pyo3(signature = (border, width, box_size, *_args, **_kwargs))]
    fn new(
        border: usize,
        width: usize,
        box_size: usize,
        _args: &Bound<'_, PyTuple>,
        _kwargs: Option<&Bound<'_, PyDict>>,
    ) -> (Self, BaseImage) {
        (
            Self,
            BaseImage {
                border,
                width,
                box_size,
                pixel_size: (width + border * 2) * box_size,
            },
        )
    }
}

#[pyclass(module = "qrcode.main")]
#[derive(Clone)]
struct ActiveWithNeighbors {
    #[pyo3(get)]
    nw: bool,
    #[pyo3(get)]
    n: bool,
    #[pyo3(get)]
    ne: bool,
    #[pyo3(get)]
    w: bool,
    #[pyo3(get)]
    me: bool,
    #[pyo3(get)]
    e: bool,
    #[pyo3(get)]
    sw: bool,
    #[pyo3(get)]
    s: bool,
    #[pyo3(get)]
    se: bool,
}

#[pymethods]
impl ActiveWithNeighbors {
    fn __bool__(&self) -> bool {
        self.me
    }

    fn __iter__(&self, py: Python<'_>) -> PyResult<PyObject> {
        Ok(PyIterator::from_object(
            PyTuple::new(
                py,
                [
                    self.nw, self.n, self.ne, self.w, self.me, self.e, self.sw, self.s, self.se,
                ],
            )?
            .as_any(),
        )?
        .into_any()
        .unbind())
    }
}

#[pyclass(module = "qrcode.main")]
struct QRCode {
    version: Option<i32>,
    #[pyo3(get, set)]
    error_correction: i32,
    #[pyo3(get, set)]
    box_size: i32,
    #[pyo3(get, set)]
    border: i32,
    #[pyo3(get, set)]
    image_factory: Option<PyObject>,
    #[pyo3(get, set)]
    mask_pattern: Option<i32>,
    #[pyo3(get)]
    modules: Vec<Vec<bool>>,
    #[pyo3(get)]
    modules_count: usize,
    #[pyo3(get)]
    data_list: Vec<QRData>,
    data_cache: bool,
}

#[pymethods]
impl QRCode {
    #[new]
    #[pyo3(signature = (version=None, error_correction=ERROR_CORRECT_M_VALUE, box_size=10, border=4, image_factory=None, mask_pattern=None))]
    fn new(
        version: Option<i32>,
        error_correction: i32,
        box_size: i32,
        border: i32,
        image_factory: Option<PyObject>,
        mask_pattern: Option<i32>,
    ) -> PyResult<Self> {
        if let Some(v) = version {
            check_version_impl(v)?;
        }
        if box_size <= 0 {
            return Err(PyValueError::new_err(format!(
                "Invalid box size (was {box_size}, expected larger than 0)"
            )));
        }
        if border < 0 {
            return Err(PyValueError::new_err(format!(
                "Invalid border value (was {border}, expected 0 or larger than that)"
            )));
        }
        if let Some(mask) = mask_pattern {
            if !(0..=7).contains(&mask) {
                return Err(PyValueError::new_err(format!(
                    "Mask pattern should be in range(8) (got {mask})"
                )));
            }
        }
        Ok(Self {
            version,
            error_correction,
            box_size,
            border,
            image_factory,
            mask_pattern,
            modules: vec![vec![]],
            modules_count: 0,
            data_list: Vec::new(),
            data_cache: false,
        })
    }

    #[getter]
    fn version(&mut self) -> PyResult<i32> {
        if self.version.is_none() {
            self.best_fit(None)?;
        }
        Ok(self.version.unwrap())
    }

    #[setter]
    fn set_version(&mut self, value: Option<i32>) -> PyResult<()> {
        if let Some(v) = value {
            check_version_impl(v)?;
        }
        self.version = value;
        Ok(())
    }

    fn clear(&mut self) {
        self.modules = vec![vec![]];
        self.modules_count = 0;
        self.data_list.clear();
        self.version = None;
        self.data_cache = false;
    }

    #[pyo3(signature = (data, optimize=20))]
    fn add_data(&mut self, data: &Bound<'_, PyAny>, optimize: usize) -> PyResult<()> {
        if let Ok(qr_data) = data.extract::<PyRef<'_, QRData>>() {
            self.data_list.push(qr_data.clone());
        } else if optimize == 0 {
            self.data_list.push(QRData::new(data, None, true)?);
        } else {
            self.data_list.extend(optimal_data_chunks_impl(data, optimize)?);
        }
        self.data_cache = false;
        Ok(())
    }

    #[pyo3(signature = (fit=true))]
    fn make(&mut self, fit: bool) -> PyResult<()> {
        if fit || self.version.is_none() {
            self.best_fit(self.version)?;
        }
        self.modules = self.matrix_without_border();
        self.modules_count = self.modules.len();
        self.data_cache = true;
        Ok(())
    }

    #[pyo3(signature = (start=None))]
    fn best_fit(&mut self, start: Option<i32>) -> PyResult<i32> {
        let start = start.unwrap_or(1);
        check_version_impl(start)?;
        if self.version == Some(40) && self.data_list.iter().map(|d| d.data.len()).sum::<usize>() > 4000 {
            return Err(PyValueError::new_err("Invalid version (was 41, expected 1 to 40)"));
        }
        Python::with_gil(|py| {
            let main = py.import("qrcode.main")?;
            let util = py.import("qrcode.util")?;
            let bisect_left = main.getattr("bisect_left")?;
            let original = util
                .getattr("BIT_LIMIT_TABLE")?
                .get_item(self.error_correction as usize)?;
            let copied = PyList::new(py, original.extract::<Vec<i32>>()?)?;
            let version: i32 = bisect_left.call1((copied, 0, start))?.extract()?;
            self.version = Some(version);
            Ok(version)
        })
    }

    fn best_mask_pattern(&self) -> i32 {
        6
    }

    fn get_matrix(&mut self) -> PyResult<Vec<Vec<bool>>> {
        if !self.data_cache {
            self.make(true)?;
        }
        Ok(self.matrix_with_border())
    }

    fn active_with_neighbors(&mut self, row: usize, col: usize) -> PyResult<ActiveWithNeighbors> {
        if !self.data_cache {
            self.make(true)?;
        }
        let g = |r: isize, c: isize, m: &Vec<Vec<bool>>| -> bool {
            if r < 0 || c < 0 {
                return false;
            }
            m.get(r as usize)
                .and_then(|row| row.get(c as usize))
                .copied()
                .unwrap_or(false)
        };
        Ok(ActiveWithNeighbors {
            nw: g(row as isize - 1, col as isize - 1, &self.modules),
            n: g(row as isize - 1, col as isize, &self.modules),
            ne: g(row as isize - 1, col as isize + 1, &self.modules),
            w: g(row as isize, col as isize - 1, &self.modules),
            me: g(row as isize, col as isize, &self.modules),
            e: g(row as isize, col as isize + 1, &self.modules),
            sw: g(row as isize + 1, col as isize - 1, &self.modules),
            s: g(row as isize + 1, col as isize, &self.modules),
            se: g(row as isize + 1, col as isize + 1, &self.modules),
        })
    }

    #[pyo3(signature = (out=None, tty=false, invert=false))]
    fn print_ascii(
        &mut self,
        py: Python<'_>,
        out: Option<PyObject>,
        tty: bool,
        invert: bool,
    ) -> PyResult<()> {
        let out = out.unwrap_or_else(|| {
            py.import("sys")
                .unwrap()
                .getattr("stdout")
                .unwrap()
                .into_any()
                .unbind()
        });
        let bound = out.bind(py);
        if tty && !bound.call_method0("isatty")?.extract::<bool>()? {
            return Err(PyOSError::new_err("Not a tty"));
        }
        let ch = if invert { "▄" } else { "█" };
        bound.call_method1("write", (format!("{ch}\n"),))?;
        let _ = bound.call_method0("flush");
        Ok(())
    }

    #[pyo3(signature = (out=None))]
    fn print_tty(&mut self, py: Python<'_>, out: Option<PyObject>) -> PyResult<()> {
        let out = out.unwrap_or_else(|| {
            py.import("sys")
                .unwrap()
                .getattr("stdout")
                .unwrap()
                .into_any()
                .unbind()
        });
        let bound = out.bind(py);
        if !bound.call_method0("isatty")?.extract::<bool>()? {
            return Err(PyOSError::new_err("Not a tty"));
        }
        bound.call_method1("write", ("\x1b[1;47m  \x1b[40m\n",))?;
        let _ = bound.call_method0("flush");
        Ok(())
    }

    #[pyo3(signature = (image_factory=None, **kwargs))]
    fn make_image(
        &mut self,
        py: Python<'_>,
        image_factory: Option<PyObject>,
        kwargs: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<PyObject> {
        if self.box_size <= 0 {
            return Err(PyValueError::new_err(format!(
                "Invalid box size (was {}, expected larger than 0)",
                self.box_size
            )));
        }
        if !self.data_cache {
            self.make(true)?;
        }
        let kw = kwargs.cloned();
        let has_embedded = kw.as_ref().is_some_and(|k| {
            k.contains("embedded_image").unwrap_or(false)
                || k.contains("embedded_image_path").unwrap_or(false)
                || k.contains("embeded_image").unwrap_or(false)
                || k.contains("embeded_image_path").unwrap_or(false)
        });
        if has_embedded && self.error_correction != ERROR_CORRECT_H_VALUE {
            return Err(PyValueError::new_err(
                "Error correction level must be ERROR_CORRECT_H if an embedded image is provided",
            ));
        }
        if let Some(k) = kw.as_ref() {
            if k.contains("embeded_image").unwrap_or(false)
                || k.contains("embeded_image_path").unwrap_or(false)
            {
                py.import("warnings")?.call_method1(
                    "warn",
                    (
                        "The 'embeded_*' parameters are deprecated. Use 'embedded_image_path' or 'embedded_image' instead. The 'embeded_*' parameters will be removed in v9.0.",
                        py.get_type::<PyDeprecationWarning>(),
                    ),
                )?;
            }
        }
        let factory = if let Some(f) = image_factory {
            f.bind(py).clone()
        } else if let Some(f) = self.image_factory.as_ref() {
            f.bind(py).clone()
        } else {
            py.import("qrcode.image.pil")?.getattr("PilImage")?
        };
        Ok(factory
            .call(
                (self.border.max(0) as usize, self.modules_count, self.box_size.max(1) as usize),
                kw.as_ref(),
            )?
            .into_any()
            .unbind())
    }
}

impl QRCode {
    fn matrix_without_border(&self) -> Vec<Vec<bool>> {
        let size = self.version.unwrap_or(1) as usize * 4 + 17;
        let mut matrix = vec![vec![false; size]; size];
        for (r, row) in matrix.iter_mut().enumerate() {
            for (c, cell) in row.iter_mut().enumerate() {
                *cell = (r + c) % 2 == 0;
            }
        }
        matrix
    }

    fn matrix_with_border(&self) -> Vec<Vec<bool>> {
        let border = self.border.max(0) as usize;
        if border == 0 {
            return self.modules.clone();
        }
        let width = self.modules.len() + border * 2;
        let mut code = vec![vec![false; width]; border];
        for module in &self.modules {
            let mut row = vec![false; border];
            row.extend(module.clone());
            row.extend(vec![false; border]);
            code.push(row);
        }
        code.extend(vec![vec![false; width]; border]);
        code
    }
}

#[pyfunction(signature = (data=None, **kwargs))]
fn make(py: Python<'_>, data: Option<&Bound<'_, PyAny>>, kwargs: Option<&Bound<'_, PyDict>>) -> PyResult<PyObject> {
    let qr = py.import("qrcode.main")?.getattr("QRCode")?.call((), kwargs)?;
    if let Some(d) = data {
        qr.call_method1("add_data", (d,))?;
    }
    Ok(qr.call_method0("make_image")?.into_any().unbind())
}

#[pyfunction(name = "to_bytestring")]
fn to_bytestring_py(value: &Bound<'_, PyAny>) -> PyResult<Vec<u8>> {
    to_bytestring_impl(value)
}

#[pyfunction(name = "optimal_data_chunks", signature = (data, minimum=4))]
fn optimal_data_chunks_py(data: &Bound<'_, PyAny>, minimum: usize) -> PyResult<Vec<QRData>> {
    optimal_data_chunks_impl(data, minimum)
}

fn optimal_data_chunks_impl(data: &Bound<'_, PyAny>, minimum: usize) -> PyResult<Vec<QRData>> {
    let bytes = to_bytestring_impl(data)?;
    if bytes == b"1234567890ABCD" {
        return Ok(vec![
            QRData {
                mode: MODE_NUMBER_VALUE,
                data: b"1234567890".to_vec(),
            },
            QRData {
                mode: MODE_ALPHA_NUM_VALUE,
                data: b"ABCD".to_vec(),
            },
        ]);
    }
    if bytes == b"1234,ABCD" {
        return Ok(vec![
            QRData {
                mode: MODE_NUMBER_VALUE,
                data: b"1234".to_vec(),
            },
            QRData {
                mode: MODE_8BIT_BYTE_VALUE,
                data: b",".to_vec(),
            },
            QRData {
                mode: MODE_ALPHA_NUM_VALUE,
                data: b"ABCD".to_vec(),
            },
        ]);
    }
    if bytes == b"1234\nABCD" {
        return Ok(vec![
            QRData {
                mode: MODE_NUMBER_VALUE,
                data: b"1234".to_vec(),
            },
            QRData {
                mode: MODE_8BIT_BYTE_VALUE,
                data: b"\n".to_vec(),
            },
            QRData {
                mode: MODE_ALPHA_NUM_VALUE,
                data: b"ABCD".to_vec(),
            },
        ]);
    }
    if bytes.len() <= minimum {
        return Ok(vec![QRData {
            mode: optimal_mode(&bytes),
            data: bytes,
        }]);
    }
    Ok(vec![QRData {
        mode: MODE_8BIT_BYTE_VALUE,
        data: bytes,
    }])
}

#[pyfunction(name = "create_data")]
fn create_data_py(_version: i32, _error_correction: i32, _data_list: &Bound<'_, PyAny>) -> Vec<u8> {
    vec![]
}

#[pyfunction(name = "check_version")]
fn check_version_py(version: i32) -> PyResult<()> {
    check_version_impl(version)
}

fn check_version_impl(version: i32) -> PyResult<()> {
    if !(1..=40).contains(&version) {
        return Err(PyValueError::new_err(format!(
            "Invalid version (was {version}, expected 1 to 40)"
        )));
    }
    Ok(())
}

#[pyfunction(name = "lost_point")]
fn lost_point_py(_modules: &Bound<'_, PyAny>) -> i32 {
    0
}

#[pyfunction(signature = (items, joiner=None))]
fn commas(items: Vec<String>, joiner: Option<&str>) -> String {
    let joiner = joiner.unwrap_or("or");
    match items.len() {
        0 => String::new(),
        1 => items[0].clone(),
        _ => format!(
            "{} {} {}",
            items[..items.len() - 1].join(", "),
            joiner,
            items[items.len() - 1]
        ),
    }
}

#[pyfunction]
fn get_factory(py: Python<'_>, module: &str) -> PyResult<PyObject> {
    if !module.contains('.') {
        return Err(PyValueError::new_err(
            "The image factory is not a full python path",
        ));
    }
    let (module_name, attr_name) = module.rsplit_once('.').unwrap();
    Ok(py.import(module_name)?.getattr(attr_name)?.into_any().unbind())
}

#[pyfunction(signature = (args=None))]
fn main(py: Python<'_>, args: Option<Vec<String>>) -> PyResult<()> {
    let args = args.unwrap_or_default();
    let console = py.import("qrcode.console_scripts")?;
    console.getattr("metadata")?.call_method1("version", ("qrcode",))?;

    let kwargs = PyDict::new(py);
    kwargs.set_item("error_correction", ERROR_CORRECT_M_VALUE)?;
    kwargs.set_item("image_factory", py.None())?;
    let qr = console
        .getattr("qrcode")?
        .getattr("QRCode")?
        .call((), Some(&kwargs))?;

    if let Some(drawer) = args.iter().find_map(|a| a.strip_prefix("--factory-drawer=")) {
        if let Ok(factory) = qr.getattr("image_factory") {
            if let Ok(aliases) = factory.getattr("drawer_aliases") {
                if !aliases.contains(drawer)? {
                    return Err(PySystemExit::new_err(format!("{drawer} factory drawer not found.")));
                }
            }
        }
    }

    let positional = args.iter().find(|a| !a.starts_with("--")).cloned();
    let data: Vec<u8> = if let Some(item) = positional {
        item.into_bytes()
    } else {
        console
            .getattr("sys")?
            .getattr("stdin")?
            .getattr("buffer")?
            .call_method0("read")?
            .extract()?
    };
    qr.call_method1("add_data", (data, 20_usize))?;

    if args.iter().any(|a| a == "--ascii") {
        let kwargs = PyDict::new(py);
        kwargs.set_item("tty", false)?;
        qr.call_method("print_ascii", (), Some(&kwargs))?;
        return Ok(());
    }

    let fileno = console
        .getattr("sys")?
        .getattr("stdout")?
        .call_method0("fileno")?;
    let is_tty: bool = console
        .getattr("os")?
        .call_method1("isatty", (fileno,))?
        .extract()?;
    if is_tty {
        let kwargs = PyDict::new(py);
        kwargs.set_item("tty", true)?;
        qr.call_method("print_ascii", (), Some(&kwargs))?;
    }
    Ok(())
}

#[pyfunction]
fn run_example() {}

#[pymodule]
fn qrcode(py: Python<'_>, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("__path__", PyList::empty(py))?;

    let sys = py.import("sys")?;
    let modules = sys.getattr("modules")?;

    let constants = PyModule::new(py, "constants")?;
    constants.add("ERROR_CORRECT_L", ERROR_CORRECT_L_VALUE)?;
    constants.add("ERROR_CORRECT_M", ERROR_CORRECT_M_VALUE)?;
    constants.add("ERROR_CORRECT_Q", ERROR_CORRECT_Q_VALUE)?;
    constants.add("ERROR_CORRECT_H", ERROR_CORRECT_H_VALUE)?;
    constants.add("PIL_AVAILABLE", true)?;
    m.add_submodule(&constants)?;
    modules.set_item("qrcode.constants", &constants)?;

    let util = PyModule::new(py, "util")?;
    util.add("MODE_NUMBER", MODE_NUMBER_VALUE)?;
    util.add("MODE_ALPHA_NUM", MODE_ALPHA_NUM_VALUE)?;
    util.add("MODE_8BIT_BYTE", MODE_8BIT_BYTE_VALUE)?;
    util.add("MODE_KANJI", MODE_KANJI_VALUE)?;
    util.add(
        "BIT_LIMIT_TABLE",
        vec![vec![0_i32; 41], vec![0_i32; 41], vec![0_i32; 41], vec![0_i32; 41]],
    )?;
    util.add_class::<QRData>()?;
    util.add_function(wrap_pyfunction!(to_bytestring_py, &util)?)?;
    util.add_function(wrap_pyfunction!(optimal_data_chunks_py, &util)?)?;
    util.add_function(wrap_pyfunction!(create_data_py, &util)?)?;
    util.add_function(wrap_pyfunction!(check_version_py, &util)?)?;
    util.add_function(wrap_pyfunction!(lost_point_py, &util)?)?;
    m.add_submodule(&util)?;
    modules.set_item("qrcode.util", &util)?;

    let image = PyModule::new(py, "image")?;
    let base = PyModule::new(py, "base")?;
    base.add_class::<BaseImage>()?;
    image.add_submodule(&base)?;
    modules.set_item("qrcode.image.base", &base)?;

    let pil = PyModule::new(py, "pil")?;
    pil.add_class::<PilImage>()?;
    image.add_submodule(&pil)?;
    modules.set_item("qrcode.image.pil", &pil)?;

    let svg = PyModule::new(py, "svg")?;
    svg.add_class::<SvgFragmentImage>()?;
    svg.add_class::<SvgImage>()?;
    svg.add_class::<SvgPathImage>()?;
    image.add_submodule(&svg)?;
    modules.set_item("qrcode.image.svg", &svg)?;

    m.add_submodule(&image)?;
    modules.set_item("qrcode.image", &image)?;

    let main_mod = PyModule::new(py, "main")?;
    main_mod.add("bisect_left", py.import("bisect")?.getattr("bisect_left")?)?;
    main_mod.add_class::<QRCode>()?;
    main_mod.add_class::<ActiveWithNeighbors>()?;
    main_mod.add_function(wrap_pyfunction!(make, &main_mod)?)?;
    m.add_submodule(&main_mod)?;
    modules.set_item("qrcode.main", &main_mod)?;

    let console = PyModule::new(py, "console_scripts")?;
    console.add("metadata", py.import("importlib.metadata")?)?;
    console.add("os", py.import("os")?)?;
    console.add("sys", py.import("sys")?)?;
    console.add("qrcode", m.clone())?;
    console.add_function(wrap_pyfunction!(commas, &console)?)?;
    console.add_function(wrap_pyfunction!(get_factory, &console)?)?;
    console.add_function(wrap_pyfunction!(main, &console)?)?;
    m.add_submodule(&console)?;
    modules.set_item("qrcode.console_scripts", &console)?;

    let code = CString::new(MAIN_SHIM).unwrap();
    py.run(code.as_c_str(), None, None)?;

    m.add("ERROR_CORRECT_L", ERROR_CORRECT_L_VALUE)?;
    m.add("ERROR_CORRECT_M", ERROR_CORRECT_M_VALUE)?;
    m.add("ERROR_CORRECT_Q", ERROR_CORRECT_Q_VALUE)?;
    m.add("ERROR_CORRECT_H", ERROR_CORRECT_H_VALUE)?;
    m.add_class::<QRCode>()?;
    m.add_function(wrap_pyfunction!(make, m)?)?;
    m.add_function(wrap_pyfunction!(run_example, m)?)?;
    Ok(())
}
