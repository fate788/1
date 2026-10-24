from __future__ import annotations

import hashlib
import struct
import zlib
from pathlib import Path


class CETRAINERFormatError(ValueError):
    pass


MAGIC = b"CHEAT"
MAX_XML = 64 * 1024 * 1024


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _inverse_protection(raw: bytes) -> bytes:
    data = bytearray(raw)
    # Inverse of protecttrainer's final reverse pass.
    for i in range(2, len(data)):
        data[i] ^= data[i - 2]
    # Inverse of the forward adjacent-byte pass.
    for i in range(len(data) - 2, -1, -1):
        data[i] ^= data[i + 1]
    # Inverse of the incrementing XOR pass.
    key = 0xCE
    for i in range(len(data)):
        data[i] ^= key
        key = (key + 1) & 0xFF
    return bytes(data)


def _apply_protection(plain: bytes) -> bytes:
    data = bytearray(plain)
    key = 0xCE
    for i in range(len(data)):
        data[i] ^= key
        key = (key + 1) & 0xFF
    for i in range(len(data) - 1):
        data[i] ^= data[i + 1]
    for i in range(len(data) - 1, 1, -1):
        data[i] ^= data[i - 2]
    return bytes(data)


def decode_cetrainer(raw: bytes) -> dict:
    plain = _inverse_protection(raw)
    if not plain.startswith(MAGIC):
        raise CETRAINERFormatError(f"unexpected header: {plain[:8].hex()}")
    stream_and_tail = plain[len(MAGIC):]
    try:
        inflater = zlib.decompressobj(-15)
        inflated = inflater.decompress(stream_and_tail, MAX_XML + 5)
        if len(inflated) > MAX_XML + 4 or inflater.unconsumed_tail:
            raise CETRAINERFormatError("inflated payload exceeds limit")
        if not inflater.eof:
            raise CETRAINERFormatError("incomplete raw deflate stream")
    except zlib.error as exc:
        raise CETRAINERFormatError(f"raw deflate decode failed: {exc}") from exc
    if len(inflated) < 4:
        raise CETRAINERFormatError("inflated payload shorter than length field")
    expected_size = struct.unpack_from("<i", inflated, 0)[0]
    xml = inflated[4:]
    if expected_size < 0 or expected_size > MAX_XML or expected_size != len(xml):
        raise CETRAINERFormatError(f"length field {expected_size} != XML bytes {len(xml)}")
    return {
        "magic": plain[: len(MAGIC)],
        "length_bytes": inflated[:4],
        "inflated": inflated,
        "compressed": stream_and_tail[:len(stream_and_tail) - len(inflater.unused_data)],
        "trailing": inflater.unused_data,
        "xml": xml,
        "xml_length": len(xml),
        "compressed_length": len(stream_and_tail) - len(inflater.unused_data),
        "inflated_length": len(inflated),
        "raw_sha256": sha256_bytes(raw),
    }


def encode_cetrainer(xml: bytes, *, trailing: bytes = b"", level: int = 9) -> bytes:
    if not isinstance(xml, bytes):
        raise TypeError("xml must be bytes")
    if len(xml) > MAX_XML:
        raise CETRAINERFormatError("XML exceeds limit")
    payload = struct.pack("<i", len(xml)) + xml
    compressor = zlib.compressobj(level=level, wbits=-15)
    compressed = compressor.compress(payload) + compressor.flush()
    return _apply_protection(MAGIC + compressed + trailing)


def decode_file(path: Path) -> dict:
    result = decode_cetrainer(path.read_bytes())
    result["path"] = str(path)
    return result

