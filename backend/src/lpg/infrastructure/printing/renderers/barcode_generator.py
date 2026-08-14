from __future__ import annotations

import io
from typing import TYPE_CHECKING

import barcode
import qrcode
from qrcode.image.pil import PilImage

if TYPE_CHECKING:
    pass


def generate_qr_png(data: str, *, size: int = 200) -> bytes:
    """Generate a QR code as PNG bytes."""
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img: PilImage = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def generate_barcode_png(data: str) -> bytes:
    """Generate a Code 128 barcode as PNG bytes."""
    code128 = barcode.get_barcode_class("code128")
    barcode_instance = code128(data, writer=barcode.writer.ImageWriter())
    buf = io.BytesIO()
    barcode_instance.write(buf)
    return buf.getvalue()
