#!/usr/bin/env python3
"""Read-only evidence collector for the three extracted LuaScript.luac files.

This script does not load a DLL, execute Lua, invoke a PE, or modify any input.
It records the byte-level header observations and the PE locations already
identified by the manual static scan.  It deliberately does not assign a
semantic name to the custom flag or to the first post-header byte.
"""
from __future__ import annotations

import hashlib
import json
import struct
import argparse
from pathlib import Path

VERSIONS = ("ARCHIVE-0604", "ARCHIVE-260718", "ARCHIVE-260804")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_luac(path: Path) -> dict:
    b = path.read_bytes()
    if len(b) < 41:
        raise ValueError(f"{path}: shorter than observed header length")
    return {
        "path": str(path),
        "size": len(b),
        "sha256": sha256(path),
        "signature_version": b[:6].hex(" "),
        "format_byte_offset_5": b[5],
        "extra_8_offset_6_hex": b[6:14].hex(" "),
        "extra_8_le_uint64": int.from_bytes(b[6:14], "little"),
        "luac_data_offset_14_19": b[14:20].hex(" "),
        "size_bytes_offset_20_24": b[20:25].hex(" "),
        "luac_int_offset_25_32": b[25:33].hex(" "),
        "luac_number_offset_33_40": b[33:41].hex(" "),
        "first_post_header_byte_offset_41": b[41],
        "first_post_header_byte_hex": b[41:45].hex(" "),
    }


def rva_to_file(dll: Path, rva: int) -> int | None:
    b = dll.read_bytes()
    e_lfanew = struct.unpack_from("<I", b, 0x3C)[0]
    fh = e_lfanew + 4
    nsec = struct.unpack_from("<H", b, fh + 2)[0]
    opt = fh + 20
    opt_size = struct.unpack_from("<H", b, fh + 16)[0]
    out = []
    for i in range(nsec):
        o = opt + opt_size + 40 * i
        va, vs, raw_size, raw_ptr = struct.unpack_from("<IIII", b, o + 12)
        name = b[o:o + 8].split(b"\0", 1)[0].decode("ascii", "replace")
        out.append((name, va, max(vs, raw_size), raw_ptr))
    for _, va, span, raw_ptr in out:
        if va <= rva < va + span:
            return raw_ptr + (rva - va)
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent,
                        help="directory containing ARCHIVE-* finalized folders")
    args = parser.parse_args()
    root = args.root.resolve()
    dll = root / "ARCHIVE-260804" / "lua53-64.dll"
    samples = [parse_luac(root / v / "LuaScript.luac") for v in VERSIONS]
    dll_hash = sha256(dll)
    strings = {
        "LUA_DUMP_STRINGSIZE_FORMAT2": {"rva": "0x157678", "file_offset": hex(0xEC878)},
        "int": {"rva": "0x157674", "file_offset": hex(0xEC874)},
        "size_t": {"rva": "0x15769c", "file_offset": hex(0xEC89C)},
        "Instruction": {"rva": "0x1576a8", "file_offset": hex(0xEC8A8)},
        "lua_Integer": {"rva": "0x1576b8", "file_offset": hex(0xEC8B8)},
        "lua_Number": {"rva": "0x1576c8", "file_offset": hex(0xEC8C8)},
    }
    evidence = {
        "dll": {"path": str(dll), "sha256": dll_hash, "machine": "PE32+ x64"},
        "header_check_function_rva": "0xbbce0-0xbbefd",
        "format2_reference_instruction_rva": "0xbbe18",
        "format2_reference_file_offset": hex(0x51218),
        "size_t_alternate_reference_instruction_rva": "0xbbe30",
        "size_check_helper_rva": "0xbc140",
        "undump_caller_rva": "0xbc2e0",
        "post_header_byte_reader_rva": "0xbad10",
        "post_header_read_call_rva": "0xbc2e9",
        "strings": strings,
        "interpretation": {
            "confirmed": [
                "The custom label is referenced inside the header-check function.",
                "It is selected on one branch and passed to the common size-check helper.",
                "All three samples have a byte at offset 41 equal to 0xcf.",
            ],
            "unknown": [
                "The semantic identity of the branch value is unknown.",
                "The exact mapping of the extra eight bytes at offsets 6..13 is not proven.",
                "The semantic identity of the byte at offset 41 is not proven.",
            ],
        },
    }
    out = {"samples": samples, "dll_evidence": evidence}
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
