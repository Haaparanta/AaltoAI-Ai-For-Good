import qrcode.image.base
from _typeshed import Incomplete
from decimal import Decimal
from qrcode.compat.etree import ET as ET
from qrcode.image.styles.moduledrawers.base import QRModuleDrawer as QRModuleDrawer
from typing import Literal, overload

class SvgFragmentImage(qrcode.image.base.BaseImageWithDrawer):
    """
    SVG image builder

    Creates a QR-code image as a SVG document fragment.
    """
    kind: str
    allowed_kinds: Incomplete
    default_drawer_class: type[QRModuleDrawer]
    unit_size: Incomplete
    def __init__(self, *args, **kwargs) -> None: ...
    @overload
    def drawrect(self, row, col) -> None:
        """
        Not used.
        """
    @overload
    def units(self, pixels: int | Decimal, text: Literal[False]) -> Decimal: ...
    @overload
    def units(self, pixels: int | Decimal, text: Literal[True] = True) -> str: ...
    def save(self, stream, kind=None) -> None: ...
    def to_string(self, **kwargs): ...
    def new_image(self, **kwargs): ...

class SvgImage(SvgFragmentImage):
    """
    Standalone SVG image builder

    Creates a QR-code image as a standalone SVG document.
    """
    background: str | None
    drawer_aliases: qrcode.image.base.DrawerAliases

class SvgPathImage(SvgImage):
    """
    SVG image builder with one single <path> element (removes white spaces
    between individual QR points).
    """
    QR_PATH_STYLE: Incomplete
    needs_processing: bool
    path: ET.Element | None
    default_drawer_class: type[QRModuleDrawer]
    drawer_aliases: Incomplete
    def __init__(self, *args, **kwargs) -> None: ...
    def process(self) -> None: ...

class SvgFillImage(SvgImage):
    """
    An SvgImage that fills the background to white.
    """
    background: str

class SvgPathFillImage(SvgPathImage):
    """
    An SvgPathImage that fills the background to white.
    """
    background: str
