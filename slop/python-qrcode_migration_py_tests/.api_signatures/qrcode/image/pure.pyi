from _typeshed import Incomplete
from collections.abc import Generator
from qrcode.compat.png import PngWriter as PngWriter
from qrcode.image.base import BaseImage as BaseImage

class PyPNGImage(BaseImage):
    """
    pyPNG image builder.
    """
    kind: str
    allowed_kinds: Incomplete
    needs_drawrect: bool
    def new_image(self, **kwargs): ...
    def drawrect(self, row, col) -> None:
        """
        Not used.
        """
    def save(self, stream, kind=None) -> None: ...
    def rows_iter(self) -> Generator[Incomplete, Incomplete]: ...
    def border_rows_iter(self) -> Generator[Incomplete]: ...
PymagingImage = PyPNGImage
