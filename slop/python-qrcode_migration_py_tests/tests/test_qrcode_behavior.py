from __future__ import annotations

import importlib
import io
import runpy
import sys
import types
import warnings
from pathlib import Path
from typing import Any

import pytest

import qrcode
from qrcode import constants, util
from qrcode.console_scripts import commas, get_factory, main
from qrcode.image.base import BaseImage
from qrcode.image.pil import PilImage
from qrcode.image.svg import SvgFragmentImage, SvgImage, SvgPathImage
from qrcode.main import QRCode


class DummyImage(BaseImage):
    kind = "DUMMY"
    allowed_kinds = ("DUMMY",)

    def new_image(self, **kwargs: Any) -> dict[str, Any]:
        return {"kwargs": kwargs}

    def drawrect(self, row: int, col: int) -> None:
        return None

    def save(self, stream: Any, kind: object = None) -> None:
        stream.write(b"dummy")


class FakeTTY(io.StringIO):
    def __init__(self, is_tty: bool) -> None:
        super().__init__()
        self._is_tty = is_tty
        self.flushed = False

    def isatty(self) -> bool:
        return self._is_tty

    def flush(self) -> None:
        self.flushed = True
        super().flush()


def test_make_returns_renderable_image() -> None:
    image = qrcode.make("hello world")

    assert hasattr(image, "save")
    assert image.kind == "PNG"


def test_add_data_optimize_zero_keeps_single_chunk_and_auto_mode() -> None:
    qr: QRCode[Any] = QRCode()

    qr.add_data("12345ABCde", optimize=0)

    assert len(qr.data_list) == 1
    assert qr.data_list[0].mode == util.MODE_8BIT_BYTE
    assert qr.data_list[0].data == b"12345ABCde"


@pytest.mark.parametrize(
    ("data", "expected_modes"),
    [
        ("1234567890ABCD", [util.MODE_NUMBER, util.MODE_ALPHA_NUM]),
        ("1234,ABCD", [util.MODE_NUMBER, util.MODE_8BIT_BYTE, util.MODE_ALPHA_NUM]),
        ("1234\nABCD", [util.MODE_NUMBER, util.MODE_8BIT_BYTE, util.MODE_ALPHA_NUM]),
    ],
)
def test_add_data_optimize_splits_chunks_by_content(
    data: str, expected_modes: list[int]
) -> None:
    qr: QRCode[Any] = QRCode()

    qr.add_data(data, optimize=4)

    assert [chunk.mode for chunk in qr.data_list] == expected_modes


def test_best_fit_uses_copy_of_bit_limit_table(monkeypatch: pytest.MonkeyPatch) -> None:
    qr: QRCode[Any] = QRCode(error_correction=constants.ERROR_CORRECT_M)
    qr.add_data("hello")

    original = util.BIT_LIMIT_TABLE[constants.ERROR_CORRECT_M]
    seen: dict[str, object] = {}

    def fake_bisect_left(a: object, x: object, lo: int = 0, hi: object = None) -> int:
        seen["sequence"] = a
        return 1

    monkeypatch.setattr("qrcode.main.bisect_left", fake_bisect_left)

    version = qr.best_fit()

    assert version == 1
    assert seen["sequence"] is not original
    assert seen["sequence"] == original


def test_best_fit_overflow_currently_raises_invalid_version_value_error() -> None:
    qr: QRCode[Any] = QRCode(version=40)
    qr.add_data(b"A" * 5000, optimize=0)

    with pytest.raises(ValueError, match=r"Invalid version \(was 41"):
        qr.best_fit(start=40)


def test_best_mask_pattern_for_hello_error_correct_h() -> None:
    qr: QRCode[Any] = QRCode(error_correction=constants.ERROR_CORRECT_H)
    qr.add_data("hello")

    assert qr.best_mask_pattern() == 6


def test_get_matrix_includes_border_by_default_and_can_exclude_it() -> None:
    qr: QRCode[Any] = QRCode(border=2)
    qr.add_data("hello")

    with_border = qr.get_matrix()
    without_border_qr: QRCode[Any] = QRCode(border=0)
    without_border_qr.add_data("hello")
    without_border = without_border_qr.get_matrix()

    assert len(with_border) == len(without_border) + 4
    assert all(cell is False for cell in with_border[0])
    assert all(cell is False for cell in with_border[-1])
    assert with_border[2][2] == without_border[0][0]


def test_active_with_neighbors_returns_context_and_bool_matches_center() -> None:
    qr: QRCode[Any] = QRCode(border=0)
    qr.add_data("hello")
    qr.make()

    context = qr.active_with_neighbors(0, 0)

    assert isinstance(bool(context), bool)
    assert bool(context) == context.me
    assert len(tuple(context)) == 9


def test_print_ascii_writes_cp437_blocks_and_flushes() -> None:
    qr: QRCode[Any] = QRCode(border=1)
    qr.add_data("hello")
    out = FakeTTY(is_tty=False)

    qr.print_ascii(out=out)

    text = out.getvalue()
    assert out.flushed is True
    assert "\n" in text
    assert any(ch in text for ch in ("█", "▀", "▄", "\xa0"))


def test_print_ascii_tty_requires_tty_stream() -> None:
    qr: QRCode[Any] = QRCode()
    qr.add_data("hello")

    with pytest.raises(OSError, match="Not a tty"):
        qr.print_ascii(out=FakeTTY(is_tty=False), tty=True)


def test_print_tty_requires_tty_stream() -> None:
    qr: QRCode[Any] = QRCode()
    qr.add_data("hello")

    with pytest.raises(OSError, match="Not a tty"):
        qr.print_tty(out=FakeTTY(is_tty=False))


def test_print_tty_writes_ansi_sequences() -> None:
    qr: QRCode[Any] = QRCode()
    qr.add_data("hello")
    out = FakeTTY(is_tty=True)

    qr.print_tty(out=out)

    text = out.getvalue()
    assert out.flushed is True
    assert text.startswith("\x1b[1;47m")
    assert "\x1b[40m" in text


def test_make_image_chooses_explicit_factory() -> None:
    qr: QRCode[Any] = QRCode(image_factory=PilImage)
    qr.add_data("hello")

    image = qr.make_image(image_factory=SvgImage)

    assert isinstance(image, SvgImage)


def test_make_image_requires_error_correct_h_for_embedded_image() -> None:
    qr: QRCode[Any] = QRCode(error_correction=constants.ERROR_CORRECT_M)
    qr.add_data("hello")

    with pytest.raises(ValueError, match="ERROR_CORRECT_H"):
        qr.make_image(embedded_image=object())


def test_make_image_embeded_typo_warns_and_still_works() -> None:
    qr: QRCode[Any] = QRCode(
        error_correction=constants.ERROR_CORRECT_H, image_factory=DummyImage
    )
    qr.add_data("hello")

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        image = qr.make_image(embeded_image=object())

    assert isinstance(image, DummyImage)
    assert any("embeded_*" in str(item.message) for item in caught)


@pytest.mark.parametrize(
    ("factory", "expected_type"),
    [
        (SvgFragmentImage, SvgFragmentImage),
        (SvgImage, SvgImage),
        (SvgPathImage, SvgPathImage),
    ],
)
def test_svg_factories_render_expected_types(
    factory: type[BaseImage], expected_type: type[BaseImage]
) -> None:
    qr: QRCode[Any] = QRCode(image_factory=factory)
    qr.add_data("hello")

    image = qr.make_image()

    assert isinstance(image, expected_type)


def test_to_bytestring_uses_utf8_string_conversion() -> None:
    class Convertible:
        def __str__(self) -> str:
            return "héllo"

    assert util.to_bytestring(Convertible()) == "héllo".encode("utf-8")


def test_commas_formats_empty_single_and_multiple_items() -> None:
    assert commas([]) == ""
    assert commas(["png"]) == "png"
    assert commas(["pil", "png", "svg"]) == "pil, png or svg"
    assert commas(["pil", "png"], joiner="and") == "pil and png"


def test_get_factory_requires_full_python_path() -> None:
    with pytest.raises(ValueError, match="full python path"):
        get_factory("pil")


def test_console_main_uses_positional_arg_and_ascii_branch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}

    class FakeQRCode:
        def __init__(self, **kwargs: Any) -> None:
            calls["init_kwargs"] = kwargs

        def add_data(self, data: bytes, optimize: int = 20) -> None:
            calls["data"] = data
            calls["optimize"] = optimize

        def print_ascii(self, tty: bool = False) -> None:
            calls["printed_tty"] = tty

    monkeypatch.setattr("qrcode.console_scripts.metadata.version", lambda _: "1.0")
    monkeypatch.setattr("qrcode.console_scripts.qrcode.QRCode", FakeQRCode)
    monkeypatch.setattr("qrcode.console_scripts.os.isatty", lambda _: True)

    main(["hello"])

    assert calls["data"] == b"hello"
    assert calls["optimize"] == 20
    assert calls["printed_tty"] is True
    assert calls["init_kwargs"] == {
        "error_correction": qrcode.ERROR_CORRECT_M,
        "image_factory": None,
    }


def test_console_main_reads_stdin_when_no_positional_arg(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}

    class FakeBuffer:
        def read(self) -> bytes:
            return b"from-stdin"

    class FakeQRCode:
        def __init__(self, **kwargs: Any) -> None:
            self.image_factory = None

        def add_data(self, data: bytes, optimize: int = 20) -> None:
            calls["data"] = data
            calls["optimize"] = optimize

        def print_ascii(self, tty: bool = False) -> None:
            calls["printed_tty"] = tty

    monkeypatch.setattr("qrcode.console_scripts.metadata.version", lambda _: "1.0")
    monkeypatch.setattr("qrcode.console_scripts.qrcode.QRCode", FakeQRCode)
    monkeypatch.setattr("qrcode.console_scripts.os.isatty", lambda _: False)
    monkeypatch.setattr(
        "qrcode.console_scripts.sys.stdin", types.SimpleNamespace(buffer=FakeBuffer())
    )

    main(["--ascii"])

    assert calls["data"] == b"from-stdin"
    assert calls["optimize"] == 20
    assert calls["printed_tty"] is False


def test_console_main_invalid_factory_drawer_exits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeImageFactory:
        drawer_aliases: dict[str, tuple[object, dict[str, object]]] = {
            "circle": (object, {})
        }

    class FakeQRCode:
        def __init__(self, **kwargs: Any) -> None:
            self.image_factory = FakeImageFactory

        def add_data(self, data: bytes, optimize: int = 20) -> None:
            return None

        def make_image(self, **kwargs: Any) -> object:
            raise AssertionError("make_image should not be called")

    monkeypatch.setattr("qrcode.console_scripts.metadata.version", lambda _: "1.0")
    monkeypatch.setattr("qrcode.console_scripts.qrcode.QRCode", FakeQRCode)
    monkeypatch.setattr("qrcode.console_scripts.os.isatty", lambda _: False)
    monkeypatch.setattr(
        "qrcode.console_scripts.sys.stdout", types.SimpleNamespace(fileno=lambda: 1)
    )

    with pytest.raises(SystemExit):
        main(["--factory-drawer=gapped", "hello"])


def test_python_m_qrcode_delegates_to_console_main(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = {"count": 0}

    fake_console = types.ModuleType("qrcode.console_scripts")

    def fake_main() -> None:
        called["count"] += 1

    fake_console.main = fake_main  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "qrcode.console_scripts", fake_console)
    monkeypatch.setitem(sys.modules, "qrcode", importlib.import_module("qrcode"))

    source_root = Path(__file__).resolve().parents[2] / "python-qrcode"
    old_argv = sys.argv[:]
    old_path = sys.path[:]
    sys.argv = [str(source_root / "qrcode")]
    sys.path.insert(0, str(source_root))
    try:
        runpy.run_module("qrcode", run_name="__main__", alter_sys=True)
    finally:
        sys.argv = old_argv
        sys.path[:] = old_path

    assert called["count"] == 1
