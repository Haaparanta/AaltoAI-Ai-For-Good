import abc
from _typeshed import Incomplete
from qrcode.image.styles.moduledrawers.base import QRModuleDrawer as QRModuleDrawer
from qrcode.main import ActiveWithNeighbors as ActiveWithNeighbors, QRCode as QRCode
from typing import Any

DrawerAliases = dict[str, tuple[type[QRModuleDrawer], dict[str, Any]]]

class BaseImage(abc.ABC, metaclass=abc.ABCMeta):
    """
    Base QRCode image output class.
    """
    kind: str | None
    allowed_kinds: tuple[str, ...] | None
    needs_context: bool
    needs_processing: bool
    needs_drawrect: bool
    border: Incomplete
    width: Incomplete
    box_size: Incomplete
    pixel_size: Incomplete
    modules: Incomplete
    def __init__(self, border, width, box_size, *args, **kwargs) -> None: ...
    @abc.abstractmethod
    def drawrect(self, row, col):
        """
        Draw a single rectangle of the QR code.
        """
    def drawrect_context(self, row: int, col: int, qr: QRCode):
        """
        Draw a single rectangle of the QR code given the surrounding context
        """
    def process(self) -> None:
        """
        Processes QR code after completion
        """
    @abc.abstractmethod
    def save(self, stream, kind=None):
        """
        Save the image file.
        """
    def pixel_box(self, row, col):
        """
        A helper method for pixel-based image generators that specifies the
        four pixel coordinates for a single rect.
        """
    @abc.abstractmethod
    def new_image(self, **kwargs) -> Any:
        """
        Build the image class. Subclasses should return the class created.
        """
    def init_new_image(self) -> None: ...
    def get_image(self, **kwargs):
        """
        Return the image class for further processing.
        """
    def check_kind(self, kind, transform=None):
        """
        Get the image type.
        """
    def is_eye(self, row: int, col: int):
        """
        Find whether the referenced module is in an eye.
        """

class BaseImageWithDrawer(BaseImage, metaclass=abc.ABCMeta):
    default_drawer_class: type[QRModuleDrawer]
    drawer_aliases: DrawerAliases
    def get_default_module_drawer(self) -> QRModuleDrawer: ...
    def get_default_eye_drawer(self) -> QRModuleDrawer: ...
    needs_context: bool
    module_drawer: QRModuleDrawer
    eye_drawer: QRModuleDrawer
    def __init__(self, *args, module_drawer: QRModuleDrawer | str | None = None, eye_drawer: QRModuleDrawer | str | None = None, **kwargs) -> None: ...
    def get_drawer(self, drawer: QRModuleDrawer | str | None) -> QRModuleDrawer | None: ...
    def init_new_image(self): ...
    def drawrect_context(self, row: int, col: int, qr: QRCode): ...
