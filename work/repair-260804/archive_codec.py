from __future__ import annotations

import hashlib
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path

MAX_PLAIN = 256 * 1024 * 1024
MAX_ENTRIES = 4096


class ArchiveFormatError(ValueError):
    pass


@dataclass
class ArchiveEntry:
    name: bytes
    folder: bytes
    data: bytes


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _u32(data: bytes, offset: int) -> tuple[int, int]:
    if offset + 4 > len(data):
        raise ArchiveFormatError(f"missing uint32 at {offset}")
    return struct.unpack_from("<I", data, offset)[0], offset + 4


def decode_archive(raw: bytes) -> dict:
    if len(raw) < 4:
        raise ArchiveFormatError("archive shorter than count header")
    count = struct.unpack_from("<I", raw, 0)[0]
    if count > MAX_ENTRIES:
        raise ArchiveFormatError("archive entry count exceeds limit")
    inflater = zlib.decompressobj(-15)
    plain = inflater.decompress(raw[4:], MAX_PLAIN + 1)
    if len(plain) > MAX_PLAIN or inflater.unconsumed_tail:
        raise ArchiveFormatError("archive inflated size exceeds limit")
    if not inflater.eof:
        raise ArchiveFormatError("incomplete raw deflate stream")
    entries: list[ArchiveEntry] = []
    pos = 0
    for index in range(count):
        name_len, pos = _u32(plain, pos)
        if pos + name_len > len(plain):
            raise ArchiveFormatError(f"name {index} exceeds payload")
        name = plain[pos:pos + name_len]
        pos += name_len
        folder_len, pos = _u32(plain, pos)
        if pos + folder_len > len(plain):
            raise ArchiveFormatError(f"folder {index} exceeds payload")
        folder = plain[pos:pos + folder_len]
        pos += folder_len
        size, pos = _u32(plain, pos)
        if pos + size > len(plain):
            raise ArchiveFormatError(f"entry {index} exceeds payload")
        data = plain[pos:pos + size]
        pos += size
        entries.append(ArchiveEntry(name, folder, data))
    if pos != len(plain):
        raise ArchiveFormatError(f"{len(plain) - pos} trailing payload bytes")
    return {
        "count": count,
        "entries": entries,
        "trailing": inflater.unused_data,
        "raw_sha256": sha256_bytes(raw),
        "plain_size": len(plain),
        "plain": plain,
        "compressed": raw[4:len(raw) - len(inflater.unused_data)],
    }


def encode_archive(entries: list[ArchiveEntry], *, trailing: bytes = b"", level: int = 9) -> bytes:
    if len(entries) > MAX_ENTRIES:
        raise ArchiveFormatError("archive entry count exceeds limit")
    plain = bytearray()
    for entry in entries:
        for value in (entry.name, entry.folder):
            plain.extend(struct.pack("<I", len(value)))
            plain.extend(value)
        plain.extend(struct.pack("<I", len(entry.data)))
        plain.extend(entry.data)
        if len(plain) > MAX_PLAIN:
            raise ArchiveFormatError("archive plain size exceeds limit")
    compressor = zlib.compressobj(level=level, wbits=-15)
    compressed = compressor.compress(bytes(plain)) + compressor.flush()
    return struct.pack("<I", len(entries)) + compressed + trailing


def entry_manifest(decoded: dict) -> list[dict]:
    return [
        {
            "index": i,
            "name": e.name.decode("latin1"),
            "folder": e.folder.decode("latin1"),
            "size": len(e.data),
            "sha256": sha256_bytes(e.data),
        }
        for i, e in enumerate(decoded["entries"])
    ]

