import base64


def to_ascii(s_bytes, prefix="", encoding="base64"):
    assert isinstance(s_bytes, bytes)
    if not isinstance(prefix, bytes):
        prefix = prefix.encode("ascii")
    if encoding == "base64":
        s_ascii = base64.b64encode(s_bytes).decode("ascii").rstrip("=")
    elif encoding == "base32":
        s_ascii = base64.b32encode(s_bytes).decode("ascii").rstrip("=").lower()
    elif encoding in ("base16", "hex"):
        s_ascii = base64.b16encode(s_bytes).decode("ascii").lower()
    else:
        raise NotImplementedError
    return prefix + s_ascii.encode("ascii")


def remove_prefix(s_bytes, prefix):
    assert isinstance(s_bytes, str)
    if s_bytes[: len(prefix)] != prefix:
        raise ValueError("did not see expected '%s' prefix" % (prefix,))
    return s_bytes[len(prefix) :]


def from_ascii(s_ascii, prefix="", encoding="base64"):
    if isinstance(s_ascii, bytes):
        s_ascii = s_ascii.decode("ascii")
    if isinstance(prefix, bytes):
        prefix = prefix.decode("ascii")
    s_ascii = remove_prefix(s_ascii.strip(), prefix)
    if encoding == "base64":
        s_ascii += "=" * ((4 - len(s_ascii) % 4) % 4)
        s_bytes = base64.b64decode(s_ascii.encode("ascii"))
    elif encoding == "base32":
        s_ascii += "=" * ((8 - len(s_ascii) % 8) % 8)
        s_bytes = base64.b32decode(s_ascii.upper().encode("ascii"))
    elif encoding in ("base16", "hex"):
        s_bytes = base64.b16decode(s_ascii.upper().encode("ascii"))
    else:
        raise NotImplementedError
    return s_bytes
