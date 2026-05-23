from qrcode.constants import PIL_AVAILABLE as PIL_AVAILABLE

def __getattr__(name):
    """Lazy import with deprecation warning for PIL drawers."""
