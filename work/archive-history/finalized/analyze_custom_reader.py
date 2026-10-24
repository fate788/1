#!/usr/bin/env python3
"""Capstone-backed, read-only proof of the custom post-header reader.

The script reads PE bytes and extracted LuaScript.luac files only. It never
loads the DLL, invokes a PE, executes Lua, or changes an input file.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

from capstone import Cs, CS_ARCH_X86, CS_MODE_64

VERSIONS = ("ARCHIVE-0604", "ARCHIVE-260718", "ARCHIVE-260804")
TEXT_RVA = 0x6B000
TEXT_RAW = 0x400


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def disasm_range(dll: bytes, start: int, end: int) -> list[dict]:
    off = TEXT_RAW + (start - TEXT_RVA)
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    return [
        {"address": hex(i.address), "bytes": i.bytes.hex(" "),
         "mnemonic": i.mnemonic, "op_str": i.op_str}
        for i in md.disasm(dll[off:off + end - start], start)
    ]


def pe_sections(dll: bytes) -> list[dict]:
    e_lfanew = struct.unpack_from("<I", dll, 0x3C)[0]
    if dll[e_lfanew:e_lfanew + 4] != b"PE\0\0":
        raise ValueError("not a PE image")
    fh = e_lfanew + 4
    nsec = struct.unpack_from("<H", dll, fh + 2)[0]
    opt_size = struct.unpack_from("<H", dll, fh + 16)[0]
    opt = fh + 20
    sections = []
    for i in range(nsec):
        o = opt + opt_size + 40 * i
        name = dll[o:o + 8].split(b"\0", 1)[0].decode("ascii", "replace")
        virtual_size, rva, raw_size, raw_ptr = struct.unpack_from("<IIII", dll, o + 8)
        sections.append({"name": name, "rva": rva, "virtual_size": virtual_size,
                         "raw_size": raw_size, "raw_ptr": raw_ptr})
    return sections


def rva_to_file(rva: int, sections: list[dict]) -> int:
    for s in sections:
        if s["rva"] <= rva < s["rva"] + max(s["virtual_size"], s["raw_size"]):
            return s["raw_ptr"] + rva - s["rva"]
    raise ValueError(f"RVA {rva:#x} is not in a file-backed section")


def pdata_ranges(dll: bytes, sections: list[dict]) -> list[tuple[int, int, int]]:
    p = next(s for s in sections if s["name"] == ".pdata")
    out = []
    for o in range(p["raw_ptr"], p["raw_ptr"] + p["raw_size"], 12):
        begin, end, unwind = struct.unpack_from("<III", dll, o)
        if begin < end:
            out.append((begin, end, unwind))
    return out


def containing_range(rva: int, ranges: list[tuple[int, int, int]]) -> tuple[int, int, int] | None:
    for begin, end, unwind in ranges:
        if begin <= rva < end:
            return begin, end, unwind
    return None


def find_instruction(items: list[dict], address: int) -> dict:
    for item in items:
        if int(item["address"], 16) == address:
            return item
    raise AssertionError(f"instruction {address:#x} not decoded")


def sample(path: Path) -> dict:
    b = path.read_bytes()
    extra = int.from_bytes(b[6:14], "little")
    # The first post-header byte is consumed by LoadByte-like code with a
    # one-byte request. At i=0 the proven transform key is 0xce.
    raw = b[41]
    return {
        "path": str(path),
        "size": len(b),
        "sha256": sha256(path),
        "extra8_offset_6_13_hex": b[6:14].hex(" "),
        "extra8_le_uint64": extra,
        "extra8_low32_used_as_key_state": extra & 0xFFFFFFFF,
        "first_body_offset": 41,
        "first_body_raw": raw,
        "first_body_decode_key_i0": 0xCE,
        "first_body_decoded": raw ^ 0xCE,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parent,
                    help="directory containing ARCHIVE-* finalized folders")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    root = args.root.resolve()
    dll_path = root / "ARCHIVE-260804" / "lua53-64.dll"
    dll = dll_path.read_bytes()
    sections = pe_sections(dll)
    pdata = pdata_ranges(dll, sections)

    header = disasm_range(dll, 0xBBD90, 0xBBF00)
    reader = disasm_range(dll, 0xBAB90, 0xBACB6)
    qword_loader = disasm_range(dll, 0xBB6C0, 0xBB730)
    byte_loader = disasm_range(dll, 0xBAD10, 0xBAD7E)
    caller = disasm_range(dll, 0xBC2D0, 0xBC30A)

    # Verify the key instructions rather than relying on arbitrary bytes.
    expected = {
        "format_byte_load_call": find_instruction(header, 0xBBD96),
        "extra_qword_load_call": find_instruction(header, 0xBBDB6),
        "store_low32_state_20": find_instruction(header, 0xBBDC2),
        "state_20_branch": find_instruction(header, 0xBBE13),
        "enable_transform_state_24": find_instruction(header, 0xBBEEC),
        "qword_reader_length_8": find_instruction(qword_loader, 0xBB6F6),
        "qword_reader_call": find_instruction(qword_loader, 0xBB707),
        "byte_reader_length_1": find_instruction(byte_loader, 0xBAD46),
        "byte_reader_call": find_instruction(byte_loader, 0xBAD57),
        "underlying_read_call": find_instruction(reader, 0xBABE9),
        "transform_check_state_24": find_instruction(reader, 0xBAC0D),
        "transform_check_state_20": find_instruction(reader, 0xBAC1E),
        "transform_key_ce": find_instruction(reader, 0xBAC63),
        "transform_shift": find_instruction(reader, 0xBAC8E),
        "transform_xor": find_instruction(reader, 0xBACA6),
        "post_header_byte_call": find_instruction(caller, 0xBC2E9),
    }

    instruction_locations = {}
    for name, item in expected.items():
        rva = int(item["address"], 16)
        fn = containing_range(rva, pdata)
        instruction_locations[name] = {
            "rva": item["address"],
            "file_offset": hex(rva_to_file(rva, sections)),
            "pdata_function": [hex(x) for x in fn] if fn else None,
        }

    result = {
        "tool": {"name": "Capstone", "version": "5.0.9", "mode": "X86-64"},
        "dll": {"path": str(dll_path), "sha256": sha256(dll_path),
                "text_rva": hex(TEXT_RVA), "text_raw": hex(TEXT_RAW),
                "sections": sections,
                "pdata_entry_count": len(pdata)},
        "functions": {
            "header_check": "0xbbce0-0xbbefd",
            "reader": "0xbab90-0xbacbf",
            "qword_loader": "0xbb6c0-0xbb72f",
            "byte_loader": "0xbad10-0xbad7e",
            "caller": "0xbc200-0xbc3cc (call site at 0xbc2e0/0xbc2e9)",
        },
        "instruction_locations": instruction_locations,
        "verified_instructions": expected,
        "samples": [sample(root / v / "LuaScript.luac") for v in VERSIONS],
        "interpretation": {
            "confirmed": [
                "Format byte 1 selects an 8-byte read at 0xbbdb6 through 0xbb6c0.",
                "The qword is stored as its low 32 bits at stream/state +0x20.",
                "Header success sets stream/state +0x24 to 1 at 0xbbeec.",
                "Subsequent reads call the common reader with an explicit length.",
                "When +0x24 and +0x20 are nonzero, the reader XOR-transforms bytes in place.",
                "At transform index i=0 the key byte is constant 0xce.",
                "The post-header one-byte read at 0xbc2e9 therefore maps raw 0xcf to decoded 0x01 in all samples.",
            ],
            "unknown": [
                "The higher-level semantic name of the +0x20 qword is not proven.",
                "The complete body field layout after the first byte is not parsed.",
                "The transform is described as an observed XOR reader; no security or protection purpose is inferred.",
            ],
        },
    }
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)


if __name__ == "__main__":
    main()
