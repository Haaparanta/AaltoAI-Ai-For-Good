import abc
from _typeshed import Incomplete
from qrcode.image.styledpil import StyledPilImage as StyledPilImage
from qrcode.image.styles.moduledrawers.base import QRModuleDrawer as QRModuleDrawer
from qrcode.main import ActiveWithNeighbors as ActiveWithNeighbors

ANTIALIASING_FACTOR: int

class StyledPilQRModuleDrawer(QRModuleDrawer, metaclass=abc.ABCMeta):
    """
    A base class for StyledPilImage module drawers.

    NOTE: the color that this draws in should be whatever is equivalent to
    black in the color space, and the specified QRColorMask will handle adding
    colors as necessary to the image
    """
    img: StyledPilImage

class SquareModuleDrawer(StyledPilQRModuleDrawer):
    """
    Draws the modules as simple squares
    """
    imgDraw: Incomplete
    def initialize(self, *args, **kwargs) -> None: ...
    def drawrect(self, box, is_active: bool): ...

class GappedSquareModuleDrawer(StyledPilQRModuleDrawer):
    """
    Draws the modules as simple squares that are not contiguous.

    The size_ratio determines how wide the squares are relative to the width of
    the space they are printed in
    """
    size_ratio: Incomplete
    def __init__(self, size_ratio: float = 0.8) -> None: ...
    imgDraw: Incomplete
    delta: Incomplete
    def initialize(self, *args, **kwargs) -> None: ...
    def drawrect(self, box, is_active: bool): ...

class CircleModuleDrawer(StyledPilQRModuleDrawer):
    """
    Draws the modules as circles
    """
    circle: Incomplete
    def initialize(self, *args, **kwargs) -> None: ...
    def drawrect(self, box, is_active: bool): ...

class GappedCircleModuleDrawer(StyledPilQRModuleDrawer):
    """
    Draws the modules as circles that are not contiguous.

    The size_ratio determines how wide the circles are relative to the width of
    the space they are printed in
    """
    circle: Incomplete
    size_ratio: Incomplete
    def __init__(self, size_ratio: float = 0.9) -> None: ...
    def initialize(self, *args, **kwargs) -> None: ...
    def drawrect(self, box, is_active: bool): ...

class RoundedModuleDrawer(StyledPilQRModuleDrawer):
    """
    Draws the modules with all 90 degree corners replaced with rounded edges.

    radius_ratio determines the radius of the rounded edges - a value of 1
    means that an isolated module will be drawn as a circle, while a value of 0
    means that the radius of the rounded edge will be 0 (and thus back to 90
    degrees again).
    """
    needs_neighbors: bool
    radius_ratio: Incomplete
    def __init__(self, radius_ratio: int = 1) -> None: ...
    corner_width: Incomplete
    def initialize(self, *args, **kwargs) -> None: ...
    SQUARE: Incomplete
    NW_ROUND: Incomplete
    SW_ROUND: Incomplete
    SE_ROUND: Incomplete
    NE_ROUND: Incomplete
    def setup_corners(self) -> None: ...
    def drawrect(self, box: list[list[int]], is_active: ActiveWithNeighbors): ...

class VerticalBarsDrawer(StyledPilQRModuleDrawer):
    """
    Draws vertically contiguous groups of modules as long rounded rectangles,
    with gaps between neighboring bands (the size of these gaps is inversely
    proportional to the horizontal_shrink).
    """
    needs_neighbors: bool
    horizontal_shrink: Incomplete
    def __init__(self, horizontal_shrink: float = 0.8) -> None: ...
    half_height: Incomplete
    delta: Incomplete
    def initialize(self, *args, **kwargs) -> None: ...
    SQUARE: Incomplete
    ROUND_TOP: Incomplete
    ROUND_BOTTOM: Incomplete
    def setup_edges(self) -> None: ...
    def drawrect(self, box, is_active: ActiveWithNeighbors): ...

class HorizontalBarsDrawer(StyledPilQRModuleDrawer):
    """
    Draws horizontally contiguous groups of modules as long rounded rectangles,
    with gaps between neighboring bands (the size of these gaps is inversely
    proportional to the vertical_shrink).
    """
    needs_neighbors: bool
    vertical_shrink: Incomplete
    def __init__(self, vertical_shrink: float = 0.8) -> None: ...
    half_width: Incomplete
    delta: Incomplete
    def initialize(self, *args, **kwargs) -> None: ...
    SQUARE: Incomplete
    ROUND_LEFT: Incomplete
    ROUND_RIGHT: Incomplete
    def setup_edges(self) -> None: ...
    def drawrect(self, box, is_active: ActiveWithNeighbors): ...
