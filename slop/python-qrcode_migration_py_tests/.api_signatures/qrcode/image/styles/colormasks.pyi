from _typeshed import Incomplete

class QRColorMask:
    """
    QRColorMask is used to color in the QRCode.

    By the time apply_mask is called, the QRModuleDrawer of the StyledPilImage
    will have drawn all of the modules on the canvas (the color of these
    modules will be mostly black, although antialiasing may result in
    gradients) In the base class, apply_mask is implemented such that the
    background color will remain, but the foreground pixels will be replaced by
    a color determined by a call to get_fg_pixel. There is additional
    calculation done to preserve the gradient artifacts of antialiasing.

    All QRColorMask objects should be careful about RGB vs RGBA color spaces.

    For examples of what these look like, see doc/color_masks.png
    """
    back_color: Incomplete
    has_transparency: bool
    paint_color = back_color
    def initialize(self, styledPilImage, image) -> None: ...
    def apply_mask(self, image, use_cache: bool = False) -> None: ...
    def get_fg_pixel(self, image, x, y) -> None: ...
    def get_bg_pixel(self, image, x, y): ...
    def interp_num(self, n1, n2, norm): ...
    def interp_color(self, col1, col2, norm): ...
    def extrap_num(self, n1, n2, interped_num): ...
    def extrap_color(self, col1, col2, interped_color): ...

class SolidFillColorMask(QRColorMask):
    """
    Just fills in the background with one color and the foreground with another
    """
    back_color: Incomplete
    front_color: Incomplete
    has_transparency: Incomplete
    def __init__(self, back_color=(255, 255, 255), front_color=(0, 0, 0)) -> None: ...
    def apply_mask(self, image): ...
    def get_fg_pixel(self, image, x, y): ...

class RadialGradiantColorMask(QRColorMask):
    """
    Fills in the foreground with a radial gradient from the center to the edge
    """
    back_color: Incomplete
    center_color: Incomplete
    edge_color: Incomplete
    has_transparency: Incomplete
    def __init__(self, back_color=(255, 255, 255), center_color=(0, 0, 0), edge_color=(0, 0, 255)) -> None: ...
    def get_fg_pixel(self, image, x, y): ...

class SquareGradiantColorMask(QRColorMask):
    """
    Fills in the foreground with a square gradient from the center to the edge
    """
    back_color: Incomplete
    center_color: Incomplete
    edge_color: Incomplete
    has_transparency: Incomplete
    def __init__(self, back_color=(255, 255, 255), center_color=(0, 0, 0), edge_color=(0, 0, 255)) -> None: ...
    def get_fg_pixel(self, image, x, y): ...

class HorizontalGradiantColorMask(QRColorMask):
    """
    Fills in the foreground with a gradient sweeping from the left to the right
    """
    back_color: Incomplete
    left_color: Incomplete
    right_color: Incomplete
    has_transparency: Incomplete
    def __init__(self, back_color=(255, 255, 255), left_color=(0, 0, 0), right_color=(0, 0, 255)) -> None: ...
    def get_fg_pixel(self, image, x, y): ...

class VerticalGradiantColorMask(QRColorMask):
    """
    Fills in the forefround with a gradient sweeping from the top to the bottom
    """
    back_color: Incomplete
    top_color: Incomplete
    bottom_color: Incomplete
    has_transparency: Incomplete
    def __init__(self, back_color=(255, 255, 255), top_color=(0, 0, 0), bottom_color=(0, 0, 255)) -> None: ...
    def get_fg_pixel(self, image, x, y): ...

class ImageColorMask(QRColorMask):
    """
    Fills in the foreground with pixels from another image, either passed by
    path or passed by image object.
    """
    back_color: Incomplete
    color_img: Incomplete
    has_transparency: Incomplete
    def __init__(self, back_color=(255, 255, 255), color_mask_path=None, color_mask_image=None) -> None: ...
    paint_color: Incomplete
    def initialize(self, styledPilImage, image) -> None: ...
    def get_fg_pixel(self, image, x, y): ...
