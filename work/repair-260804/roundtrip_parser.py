#!/usr/bin/env python3
"""Bounded, read-only parser for the custom Lua chunk samples.

The parser follows the call boundaries identified in lua53-64.dll. It never
loads the DLL, executes Lua, invokes an EXE, or changes an input file.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from dataclasses import dataclass, field
from pathlib import Path

VERSIONS = ("ARCHIVE-0604", "ARCHIVE-260718", "ARCHIVE-260804")
MAX_DEPTH = 64
MAX_COUNT = 1_000_000
MAX_ALLOC = 64 * 1024 * 1024


class ParseFailure(Exception):
    pass


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass
class Reader:
    data: bytes
    key32: int
    pos: int = 0
    enabled: bool = False
    records: list[dict] = field(default_factory=list)

    def fail(self, message: str) -> None:
        raise ParseFailure(f"offset {self.pos}: {message}")

    def read_block(self, n: int, kind: str) -> bytes:
        if not isinstance(n, int) or n < 0:
            self.fail(f"invalid read length {n!r} for {kind}")
        if n > MAX_ALLOC:
            self.fail(f"read length {n} exceeds MAX_ALLOC")
        end = self.pos + n
        if end > len(self.data):
            self.fail(f"{kind} length {n} exceeds remaining {len(self.data) - self.pos}")
        start = self.pos
        raw = self.data[start:end]
        out = bytearray(raw)
        keys: list[int] = []
        if self.enabled and self.key32:
            signed = self.key32 if self.key32 < 0x80000000 else self.key32 - 0x100000000
            for i in range(n):
                if i % 8 == 0:
                    k = 0xCE
                else:
                    # The DLL uses a 32-bit arithmetic right shift (SAR).
                    k = (signed >> (i % 14)) & 0xFF
                keys.append(k)
                out[i] ^= k
        self.pos = end
        self.records.append({
            "kind": kind,
            "offset": start,
            "length": n,
            "raw_hex": raw.hex(" "),
            "decoded_hex": bytes(out).hex(" "),
            "transform_enabled": self.enabled and bool(self.key32),
            "key_preview_hex": bytes(keys[:32]).hex(" "),
        })
        return bytes(out)

    def byte(self, kind: str = "byte") -> int:
        return self.read_block(1, kind)[0]

    def int32(self, kind: str = "int32") -> int:
        return struct.unpack("<i", self.read_block(4, kind))[0]

    def uint32(self, kind: str = "uint32") -> int:
        return struct.unpack("<I", self.read_block(4, kind))[0]

    def uint64(self, kind: str = "uint64") -> int:
        return struct.unpack("<Q", self.read_block(8, kind))[0]

    def integer(self, kind: str = "lua_Integer") -> int:
        return struct.unpack("<q", self.read_block(8, kind))[0]

    def number(self, kind: str = "lua_Number") -> float:
        return struct.unpack("<d", self.read_block(8, kind))[0]

    def literal(self, expected: bytes, kind: str) -> None:
        got = self.read_block(len(expected), kind)
        if got != expected:
            self.fail(f"{kind} mismatch: got {got.hex()} expected {expected.hex()}")

    def count(self, kind: str) -> int:
        n = self.int32(kind)
        if n < 0 or n > MAX_COUNT:
            self.fail(f"{kind} count {n} outside 0..{MAX_COUNT}")
        return n


def read_string(r: Reader, kind: str) -> dict | None:
    prefix = r.byte(f"{kind}.size_prefix")
    if prefix == 0:
        return None
    if prefix == 0xFF:
        total = r.uint64(f"{kind}.extended_size")
    else:
        total = prefix
    if total == 0:
        return None
    if total > MAX_ALLOC + 1:
        r.fail(f"{kind} size {total} exceeds MAX_ALLOC+1")
    payload = r.read_block(total - 1, f"{kind}.payload")
    return {"size_including_nul": total, "size_prefix": prefix, "text_hex": payload.hex(" "),
            "text": payload.decode("utf-8", "replace")}


# Values are obtained from the DLL's constants switch at 0xbaf00. The
# standard Lua names are labels for the observed case values, not assumptions
# about a different loader.
CONST_TAGS = {
    0: "nil",
    1: "boolean",
    3: "float",
    4: "short_string",
    19: "integer",
    20: "long_string",
}

OPNAMES = [
    "MOVE", "LOADK", "LOADKX", "LOADBOOL", "LOADNIL", "GETUPVAL",
    "GETTABUP", "GETTABLE", "SETTABUP", "SETUPVAL", "SETTABLE", "NEWTABLE",
    "SELF", "ADD", "SUB", "MUL", "MOD", "POW", "DIV", "IDIV", "BAND",
    "BOR", "BXOR", "SHL", "SHR", "UNM", "BNOT", "NOT", "LEN", "CONCAT",
    "JMP", "EQ", "LT", "LE", "TEST", "TESTSET", "CALL", "TAILCALL",
    "RETURN", "FORLOOP", "FORPREP", "TFORCALL", "TFORLOOP", "SETLIST",
    "CLOSURE", "VARARG", "EXTRAARG",
]

# Instructions whose B or C operand can carry a constant index through RK.
RK_B = {8, 10} | set(range(13, 25)) | {31, 32, 33}
RK_C = {6, 7, 8, 10, 12} | set(range(13, 25)) | {31, 32, 33}


def parse_code(r: Reader, version: str) -> dict:
    n = r.count("code_count")
    raw = r.read_block(n * 4, "code_vector")
    words = list(struct.unpack("<" + "I" * n, raw)) if n else []
    # The DLL's LoadCode post-pass subtracts i mod 4 from each instruction
    # word when the custom key state is nonzero (0xbae8d..0xbaeaa).
    decoded = [(w - (i % 4)) & 0xFFFFFFFF for i, w in enumerate(words)] if r.key32 else words
    instructions = []
    invalid = []
    for pc, word in enumerate(decoded):
        opcode = word & 0x3F
        a = (word >> 6) & 0xFF
        c = (word >> 14) & 0x1FF
        b = (word >> 23) & 0x1FF
        bx = (word >> 14) & 0x3FFFF
        # Lua 5.3 uses OFFSET_sBx = (MAXARG_Bx >> 1) = 131071,
        # not 2^17. This is only an instruction-field interpretation; the
        # byte stream itself is still decoded according to the DLL.
        sbx = bx - ((1 << 17) - 1)
        if opcode > 46:
            invalid.append({"pc": pc, "word": word, "opcode": opcode})
        instructions.append({"pc": pc, "word": word, "opcode": opcode,
                             "A": a, "B": b, "C": c, "Bx": bx, "sBx": sbx})
    return {"count": n, "words": decoded, "instructions": instructions,
            "invalid_opcodes": invalid}


def parse_constants(r: Reader, version: str) -> list[dict]:
    n = r.count("constant_count")
    if n * 16 > MAX_ALLOC:
        r.fail(f"constant allocation {n * 16} exceeds MAX_ALLOC")
    out = []
    for i in range(n):
        tag = r.byte(f"constant[{i}].tag")
        name = CONST_TAGS.get(tag, f"unknown_0x{tag:02x}")
        item = {"index": i, "tag": tag, "kind": name}
        if tag == 0:
            item["value"] = None
        elif tag == 1:
            item["boolean_byte"] = r.byte(f"constant[{i}].boolean")
            item["value"] = bool(item["boolean_byte"])
        elif tag == 3:
            bits = r.read_block(8, f"constant[{i}].float")
            item["float_bits_hex"] = bits.hex()
            item["value"] = struct.unpack('<d', bits)[0]
        elif tag == 19:
            item["value"] = r.integer(f"constant[{i}].integer")
        elif tag in (4, 20):
            item["value"] = read_string(r, f"constant[{i}].string")
        else:
            r.fail(f"unsupported constant tag 0x{tag:02x} at constant {i}")
        out.append(item)
    return out


def parse_debug(r: Reader) -> dict:
    nline = r.count("lineinfo_count")
    line_raw = r.read_block(nline * 4, "lineinfo_vector")
    lineinfo = list(struct.unpack("<" + "i" * nline, line_raw)) if nline else []
    nloc = r.count("locvar_count")
    locvars = []
    for i in range(nloc):
        locvars.append({"index": i, "name": read_string(r, f"locvar[{i}].name"),
                        "startpc": r.int32(f"locvar[{i}].startpc"),
                        "endpc": r.int32(f"locvar[{i}].endpc")})
    nupnames = r.count("upvalue_name_count")
    upnames = [read_string(r, f"upvalue_name[{i}]") for i in range(nupnames)]
    return {"lineinfo_count": nline, "lineinfo": lineinfo,
            "locvar_count": nloc, "locvars": locvars,
            "upvalue_name_count": nupnames, "upvalue_names": upnames}


def parse_function(r: Reader, depth: int, version: str, parent_source: dict | None = None) -> dict:
    if depth > MAX_DEPTH:
        r.fail(f"prototype recursion depth exceeds {MAX_DEPTH}")
    source_value = read_string(r, f"proto[{depth}].source")
    source_present = source_value is not None
    source = source_value if source_present else parent_source
    linedefined = r.int32(f"proto[{depth}].linedefined")
    lastlinedefined = r.int32(f"proto[{depth}].lastlinedefined")
    numparams = r.byte(f"proto[{depth}].numparams")
    is_vararg = r.byte(f"proto[{depth}].is_vararg")
    maxstacksize = r.byte(f"proto[{depth}].maxstacksize")
    code = parse_code(r, version)
    constants = parse_constants(r, version)
    upcount = r.count(f"proto[{depth}].upvalue_count")
    upvalues = []
    for i in range(upcount):
        upvalues.append({"instack": r.byte(f"upvalue[{i}].instack"),
                         "idx": r.byte(f"upvalue[{i}].idx")})
    pcount = r.count(f"proto[{depth}].proto_count")
    children = [parse_function(r, depth + 1, version, source) for _ in range(pcount)]
    debug = parse_debug(r)
    return {
        "depth": depth, "source": source,
        "source_present": source_present,
        "linedefined": linedefined, "lastlinedefined": lastlinedefined,
        "numparams": numparams, "is_vararg": is_vararg,
        "maxstacksize": maxstacksize, "code": code,
        "constants": constants, "upvalue_count": upcount,
        "upvalues": upvalues, "proto_count": pcount,
        "children": children, "debug": debug,
    }


def validate_function(proto: dict, path: str = "root") -> list[str]:
    errors: list[str] = []
    code = proto["code"]["instructions"]
    ncode = len(code)
    nconst = len(proto["constants"])
    nup = proto["upvalue_count"]
    nchild = proto["proto_count"]
    for ins in code:
        pc = ins["pc"]
        op = ins["opcode"]
        if op >= len(OPNAMES):
            errors.append(f"{path}: pc {pc} invalid opcode {op}")
            continue
        ins["opname"] = OPNAMES[op]
        if op == 1 and ins["Bx"] >= nconst:
            errors.append(f"{path}: pc {pc} LOADK Bx={ins['Bx']} >= constants {nconst}")
        if op == 2:
            if pc + 1 >= ncode or code[pc + 1]["opcode"] != 46:
                errors.append(f"{path}: pc {pc} LOADKX not followed by EXTRAARG")
        if op == 44 and ins["Bx"] >= nchild:
            errors.append(f"{path}: pc {pc} CLOSURE Bx={ins['Bx']} >= protos {nchild}")
        for field, rkset in (("B", RK_B), ("C", RK_C)):
            if op in rkset:
                value = ins[field]
                if value & 0x100:
                    index = value & 0xFF
                    if index >= nconst:
                        errors.append(f"{path}: pc {pc} {OPNAMES[op]} {field} constant {index} >= {nconst}")
        if op in (30, 39, 40, 42):
            target = pc + 1 + ins["sBx"]
            if not (0 <= target < ncode):
                errors.append(f"{path}: pc {pc} {OPNAMES[op]} target {target} outside 0..{ncode - 1}")
            ins["jump_target"] = target
        if op == 2 and pc + 1 < ncode and code[pc + 1]["opcode"] == 46:
            ax = code[pc + 1]["word"] >> 14
            if ax >= nconst:
                errors.append(f"{path}: pc {pc} LOADKX EXTRAARG Ax={ax} >= constants {nconst}")
            ins["extraarg_constant"] = ax
        if op == 3 and ins["C"] and pc + 1 >= ncode:
            errors.append(f"{path}: pc {pc} LOADBOOL skips beyond code")
    for i, child in enumerate(proto["children"]):
        errors.extend(validate_function(child, f"{path}.child[{i}]"))
    return errors


def flatten_functions(proto: dict) -> list[dict]:
    out = [proto]
    for child in proto["children"]:
        out.extend(flatten_functions(child))
    return out


def summarize_structure(proto: dict) -> dict:
    funcs = flatten_functions(proto)
    validation_errors = validate_function(proto)
    return {
        "function_count": len(funcs),
        "instruction_count": sum(x["code"]["count"] for x in funcs),
        "constant_count": sum(len(x["constants"]) for x in funcs),
        "invalid_opcode_count": sum(len(x["code"]["invalid_opcodes"]) for x in funcs),
        "max_depth": max(x["depth"] for x in funcs),
        "validation_error_count": len(validation_errors),
        "validation_errors": validation_errors[:32],
    }


def parse_sample(path: Path) -> dict:
    data = path.read_bytes()
    if len(data) < 41:
        raise ParseFailure("sample shorter than fixed header")
    # Header reads are made through the same bounded reader, but the transform
    # is disabled until the DLL writes state +0x24 at header completion.
    r = Reader(data, 0)
    r.literal(b"\x1bLua", "signature")
    version_byte = r.byte("version")
    format_byte = r.byte("format")
    if version_byte != 0x53:
        r.fail(f"version {version_byte:#x} != 0x53")
    if format_byte != 1:
        r.fail(f"only observed format=1 path is supported, got {format_byte}")
    extra = r.uint64("format1_extra_qword")
    r.key32 = extra & 0xFFFFFFFF
    r.literal(bytes.fromhex("19 93 0d 0a 1a 0a"), "LUAC_DATA")
    sizes = [r.byte(f"header_size[{i}]") for i in range(5)]
    if sizes != [4, 8, 4, 8, 8]:
        r.fail(f"size bytes {sizes!r} do not match observed DLL checks")
    luac_int = r.integer("LUAC_INT")
    luac_num = r.number("LUAC_NUM")
    if luac_int != 0x5678 or luac_num != 370.5:
        r.fail(f"header constants mismatch int={luac_int} num={luac_num}")
    # DLL writes state +0x24=1 here, enabling read_block transformation.
    r.enabled = True
    root_upvalues = r.byte("root_closure_upvalue_count")
    root = parse_function(r, 0, path.parent.name)
    if root_upvalues != root["upvalue_count"]:
        raise ParseFailure(f"root closure upvalues {root_upvalues} != root proto count {root['upvalue_count']}")
    result = {
        "path": str(path), "sha256": sha256(path), "size": len(data),
        "header": {"version": version_byte, "format": format_byte,
                    "extra_qword": extra, "extra_low32": r.key32,
                    "sizes": sizes, "luac_int": luac_int, "luac_num": luac_num,
                    "root_closure_upvalue_count": root_upvalues},
        "structure": summarize_structure(root),
        "final_offset": r.pos, "remaining": len(data) - r.pos,
        "trailing_hex": data[r.pos:].hex(),
        "root": root, "read_records": r.records,
    }
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parent,
                    help="directory containing ARCHIVE-* finalized folders")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    results = []
    for version in VERSIONS:
        path = args.root.resolve() / version / "LuaScript.luac"
        try:
            results.append({"version": version, "status": "ok", **parse_sample(path)})
        except (ParseFailure, struct.error, ValueError) as exc:
            results.append({"version": version, "status": "failed", "error": str(exc),
                            "path": str(path), "sha256": sha256(path)})
    out = {"parser": "bounded DLL-call-order parser; no execution", "samples": results}
    text = json.dumps(out, ensure_ascii=False, indent=2)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)


if __name__ == "__main__":
    main()
