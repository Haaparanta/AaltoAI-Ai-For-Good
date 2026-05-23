from _typeshed import Incomplete
from qrcode import constants as constants, exceptions as exceptions, util as util
from qrcode.image.base import BaseImage as BaseImage
from qrcode.image.pure import PyPNGImage as PyPNGImage
from typing import Generic, NamedTuple, TypeVar, overload

ModulesType = list[list[bool | None]]
precomputed_qr_blanks: dict[int, ModulesType]

def make(data=None, **kwargs): ...
def copy_2d_array(x): ...

class ActiveWithNeighbors(NamedTuple):
    NW: bool
    N: bool
    NE: bool
    W: bool
    me: bool
    E: bool
    SW: bool
    S: bool
    SE: bool
    def __bool__(self) -> bool: ...
GenericImage = TypeVar('GenericImage', bound=BaseImage)
GenericImageLocal = TypeVar('GenericImageLocal', bound=BaseImage)

class QRCode(Generic[GenericImage]):
    modules: ModulesType
    error_correction: Incomplete
    box_size: Incomplete
    border: Incomplete
    image_factory: Incomplete
    def __init__(self, version=None, error_correction=..., box_size: int = 10, border: int = 4, image_factory: type[GenericImage] | None = None, mask_pattern=None) -> None: ...
    @property
    def version(self) -> int: ...
    @version.setter
    def version(self, value) -> None: ...
    @property
    def mask_pattern(self): ...
    @mask_pattern.setter
    def mask_pattern(self, pattern) -> None: ...
    modules_count: int
    data_cache: Incomplete
    data_list: Incomplete
    def clear(self) -> None:
        """
        Reset the internal data.
        """
    def add_data(self, data, optimize: int = 20) -> None:
        """
        Add data to this QR Code.

        :param optimize: Data will be split into multiple chunks to optimize
            the QR size by finding to more compressed modes of at least this
            length. Set to ``0`` to avoid optimizing at all.
        """
    def make(self, fit: bool = True) -> None:
        """
        Compile the data into a QR Code array.

        :param fit: If ``True`` (or if a size has not been provided), find the
            best fit for the data to avoid data overflow errors.
        """
    def makeImpl(self, mask_pattern) -> None: ...
    def setup_position_probe_pattern(self, row, col) -> None: ...
    def best_fit(self, start=None):
        """
        Find the minimum size required to fit in the data.
        """
    def best_mask_pattern(self):
        """
        Find the most efficient mask pattern.
        """
    def print_tty(self, out=None) -> None:
        """
        Output the QR Code only using TTY colors.

        If the data has not been compiled yet, make it first.
        """
    def print_ascii(self, out=None, tty: bool = False, invert: bool = False):
        """
        Output the QR Code using ASCII characters.

        :param tty: use fixed TTY color codes (forces invert=True)
        :param invert: invert the ASCII characters (solid <-> transparent)
        """
    @overload
    def make_image(self, image_factory: None = None, **kwargs) -> GenericImage: ...
    @overload
    def make_image(self, image_factory: type[GenericImageLocal] | None = None, **kwargs) -> GenericImageLocal: ...
    def is_constrained(self, row: int, col: int) -> bool: ...
    def setup_timing_pattern(self) -> None: ...
    def setup_position_adjust_pattern(self) -> None: ...
    def setup_type_number(self) -> None: ...
    def setup_type_info(self, mask_pattern) -> None: ...
    def map_data(self, data, mask_pattern) -> None: ...
    def get_matrix(self):
        """
        Return the QR Code as a multidimensional array, including the border.

        To return the array without a border, set ``self.border`` to 0 first.
        """
    def active_with_neighbors(self, row: int, col: int) -> ActiveWithNeighbors: ...
