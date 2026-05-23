import qrcode.image.base
from _typeshed import Incomplete
from qrcode.image.styles.colormasks import QRColorMask as QRColorMask, SolidFillColorMask as SolidFillColorMask
from qrcode.image.styles.moduledrawers.pil import SquareModuleDrawer as SquareModuleDrawer
from typing import overload

class StyledPilImage(qrcode.image.base.BaseImageWithDrawer):
    '''
    Styled PIL image builder, default format is PNG.

    This differs from the PilImage in that there is a module_drawer, a
    color_mask, and an optional image

    The module_drawer should extend the QRModuleDrawer class and implement the
    drawrect_context(self, box, active, context), and probably also the
    initialize function. This will draw an individual "module" or square on
    the QR code.

    The color_mask will extend the QRColorMask class and will at very least
    implement the get_fg_pixel(image, x, y) function, calculating a color to
    put on the image at the pixel location (x,y) (more advanced functionality
    can be gotten by instead overriding other functions defined in the
    QRColorMask class)

    The Image can be specified either by path or with a Pillow Image, and if it
    is there will be placed in the middle of the QR code. No effort is done to
    ensure that the QR code is still legible after the image has been placed
    there; Q or H level error correction levels are recommended to maintain
    data integrity A resampling filter can be specified (defaulting to
    PIL.Image.Resampling.LANCZOS) for resizing; see PIL.Image.resize() for possible
    options for this parameter.
    The image size can be controlled by `embedded_image_ratio` which is a ratio
    between 0 and 1 that\'s set in relation to the overall width of the QR code.
    '''
    kind: str
    needs_processing: bool
    color_mask: QRColorMask
    default_drawer_class = SquareModuleDrawer
    embedded_image: Incomplete
    embedded_image_ratio: Incomplete
    embedded_image_resample: Incomplete
    paint_color: Incomplete
    def __init__(self, *args, **kwargs) -> None: ...
    @overload
    def drawrect(self, row, col) -> None:
        """
        Not used.
        """
    def new_image(self, **kwargs): ...
    def init_new_image(self) -> None: ...
    def process(self) -> None: ...
    def draw_embeded_image(self): ...
    def draw_embedded_image(self) -> None: ...
    def save(self, stream, format=None, **kwargs) -> None: ...
    def __getattr__(self, name): ...
