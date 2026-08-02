"""Just enough OSC to talk to Bitwig.

OSC is a tiny format — a padded address string, a padded type tag, then packed
arguments — and the two things this bridge sends are a string and a handful of
ints. A dependency for that would be a dependency to install, pin, and explain
in a repo whose rule is that a new third-party package has to justify itself.

Only the types Bitwig's OscMessage getters expose are handled: s, i, f, d, plus
blobs on the way in. Anything else raises rather than guessing, because a
silently mis-decoded argument is a note in the wrong place.
"""
from __future__ import annotations

import struct


def _pad(n: int) -> int:
    return (4 - (n % 4)) % 4


def _put_string(s: str) -> bytes:
    b = s.encode("utf-8") + b"\0"
    return b + b"\0" * _pad(len(b))


def _take_string(buf: bytes, i: int) -> tuple[str, int]:
    end = buf.index(b"\0", i)
    s = buf[i:end].decode("utf-8", "replace")
    n = end - i + 1
    return s, i + n + _pad(n)


def encode(address: str, *args) -> bytes:
    tags = ","
    body = b""
    for a in args:
        if isinstance(a, bool):
            raise TypeError("OSC booleans are type-tag only; send an int")
        if isinstance(a, int):
            tags += "i"
            body += struct.pack(">i", a)
        elif isinstance(a, float):
            tags += "d"                      # Bitwig reads these with getDouble
            body += struct.pack(">d", a)
        elif isinstance(a, str):
            tags += "s"
            body += _put_string(a)
        elif isinstance(a, (bytes, bytearray)):
            tags += "b"
            body += struct.pack(">i", len(a)) + bytes(a) + b"\0" * _pad(len(a))
        else:
            raise TypeError(f"cannot send {type(a).__name__} over OSC")
    return _put_string(address) + _put_string(tags) + body


def decode(data: bytes) -> tuple[str, list]:
    """-> (address, args). Bundles are unwrapped to their first message."""
    if data.startswith(b"#bundle"):
        # 8 bytes '#bundle\0', 8 bytes timetag, then size-prefixed elements
        i = 16
        size = struct.unpack_from(">i", data, i)[0]
        return decode(data[i + 4:i + 4 + size])

    address, i = _take_string(data, 0)
    if i >= len(data):
        return address, []
    tags, i = _take_string(data, i)
    args: list = []
    for t in tags[1:]:
        if t == "i":
            args.append(struct.unpack_from(">i", data, i)[0]); i += 4
        elif t == "f":
            args.append(struct.unpack_from(">f", data, i)[0]); i += 4
        elif t == "d":
            args.append(struct.unpack_from(">d", data, i)[0]); i += 8
        elif t == "s":
            s, i = _take_string(data, i)
            args.append(s)
        elif t == "b":
            n = struct.unpack_from(">i", data, i)[0]; i += 4
            args.append(data[i:i + n]); i += n + _pad(n)
        elif t in "TF":
            args.append(t == "T")
        elif t == "N":
            args.append(None)
        else:
            raise ValueError(f"unsupported OSC type tag {t!r} in {address}")
    return address, args
