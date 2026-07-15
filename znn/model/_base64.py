"""Model-wire base64 decoding shared by handwritten and generated models."""

import base64
import binascii
import re


_STANDARD_BASE64 = re.compile(r"[A-Za-z0-9+/]*={0,2}")


def decode_model_base64(value, field_name):
    """Decode padded or unpadded standard base64 with strict alphabet checks."""
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a base64 string")
    if not _STANDARD_BASE64.fullmatch(value):
        raise ValueError(f"{field_name} must use standard base64")

    unpadded = value.rstrip("=")
    supplied_padding = len(value) - len(unpadded)
    required_padding = (-len(unpadded)) % 4
    if required_padding == 3 or (
        supplied_padding and supplied_padding != required_padding
    ):
        raise ValueError(f"{field_name} must use valid base64 padding")

    try:
        return base64.b64decode(
            unpadded + "=" * required_padding,
            validate=True,
        )
    except (ValueError, binascii.Error) as error:
        raise ValueError(f"{field_name} must use standard base64") from error
