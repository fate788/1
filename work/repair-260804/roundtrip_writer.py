from __future__ import annotations

import hashlib
import json
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import roundtrip_parser as parser  # noqa: E402


VERSIONS = ("ARCHIVE-0604", "ARCHIVE-260718", "ARCHIVE-260804")
BASE = Path(r"C:\Users\13162\Documents\Codex\2026-10-18\di\work\archive-history\finalized")
OUT = HERE / "roundtrip"


class WriteFailure(Exception):
    pass


class Writer:
    def __init__(self, key32: int):
        self.key32 = key32 & 0xFFFFFFFF
        self.out = bytearray()

    def transform(self, plain: bytes) -> bytes:
        if not self.key32:
            return plain
        signed = self.key32 if self.key32 < 0x80000000 else self.key32 - 0x100000000
        result = bytearray(plain)
        for i in range(len(result)):
            key = 0xCE if i % 8 == 0 else ((signed >> (i % 14)) & 0xFF)
            result[i] ^= key
        return bytes(result)

    def block(self, plain: bytes) -> None:
        self.out.extend(self.transform(plain))

    def byte(self, value: int) -> None:
        if not isinstance(value, int) or not 0 <= value <= 255:
            raise WriteFailure(f"byte out of range: {value!r}")
        self.block(bytes([value]))

    def int32(self, value: int) -> None:
        self.block(struct.pack("<i", int(value)))

    def uint32(self, value: int) -> None:
        self.block(struct.pack("<I", int(value) & 0xFFFFFFFF))

    def uint64(self, value: int) -> None:
        self.block(struct.pack("<Q", int(value) & 0xFFFFFFFFFFFFFFFF))

    def integer(self, value: int) -> None:
        self.block(struct.pack("<q", int(value)))

    def number(self, value: float) -> None:
        self.block(struct.pack("<d", float(value)))

    def string(self, value: dict | None) -> None:
        if value is None:
            self.byte(0)
            return
        total = int(value["size_including_nul"])
        raw_hex = value.get("text_hex", "")
        payload = bytes.fromhex(raw_hex)
        if total != len(payload) + 1 or total <= 0:
            raise WriteFailure(f"string size mismatch total={total} payload={len(payload)}")
        if total >= 0xFF or value.get('size_prefix') == 0xFF:
            self.byte(0xFF)
            self.uint64(total)
        else:
            self.byte(total)
        self.block(payload)

    def code(self, code: dict) -> None:
        words = [int(x) for x in code["words"]]
        if code['count'] != len(words) or any(not 0 <= x <= 0xFFFFFFFF for x in words):
            raise WriteFailure('instruction word count/range mismatch')
        self.int32(len(words))
        encoded = [(word + (i % 4)) & 0xFFFFFFFF for i, word in enumerate(words)] if self.key32 else words
        self.block(struct.pack("<" + "I" * len(encoded), *encoded) if encoded else b"")

    def constant(self, c: dict) -> None:
        tag = int(c["tag"])
        self.byte(tag)
        value = c.get("value")
        if tag == 0:
            return
        if tag == 1:
            original = c.get('boolean_byte')
            self.byte(original if original is not None and bool(original) == bool(value) else (1 if value else 0))
            return
        if tag == 3:
            # Preserve exact IEEE payload (including NaN bits) unless changed.
            import math
            bits = bytes.fromhex(c.get('float_bits_hex', ''))
            same = len(bits) == 8 and (struct.unpack('<d', bits)[0] == value or
                   (math.isnan(struct.unpack('<d', bits)[0]) and math.isnan(value)))
            self.block(bits) if same else self.number(value)
            return
        if tag == 19:
            self.integer(value)
            return
        if tag in (4, 20):
            self.string(value)
            return
        raise WriteFailure(f"unsupported constant tag {tag}")

    def debug(self, debug: dict) -> None:
        lineinfo = [int(x) for x in debug["lineinfo"]]
        self.int32(len(lineinfo))
        self.block(struct.pack("<" + "i" * len(lineinfo), *lineinfo) if lineinfo else b"")
        locvars = debug["locvars"]
        self.int32(len(locvars))
        for loc in locvars:
            self.string(loc.get("name"))
            self.int32(loc["startpc"])
            self.int32(loc["endpc"])
        names = debug["upvalue_names"]
        self.int32(len(names))
        for name in names:
            self.string(name)

    def function(self, proto: dict, parent_source: dict | None = None) -> None:
        source = proto.get("source") if proto.get("source_present", True) else None
        self.string(source)
        self.int32(proto["linedefined"])
        self.int32(proto["lastlinedefined"])
        self.byte(proto["numparams"])
        self.byte(proto["is_vararg"])
        self.byte(proto["maxstacksize"])
        self.code(proto["code"])
        constants = proto["constants"]
        self.int32(len(constants))
        for c in constants:
            self.constant(c)
        upvalues = proto["upvalues"]
        self.int32(len(upvalues))
        for up in upvalues:
            self.byte(up["instack"])
            self.byte(up["idx"])
        children = proto["children"]
        self.int32(len(children))
        for child in children:
            self.function(child, proto.get("source"))
        self.debug(proto["debug"])


def write_sample(parsed: dict) -> bytes:
    h = parsed["header"]
    w = Writer(h["extra_low32"])
    # Header is outside the transformed read_block region.
    w.out.extend(b"\x1bLua")
    w.out.append(h["version"])
    w.out.append(h["format"])
    w.out.extend(struct.pack("<Q", h["extra_qword"]))
    w.out.extend(bytes.fromhex("19 93 0d 0a 1a 0a"))
    w.out.extend(bytes(h["sizes"]))
    w.out.extend(struct.pack("<q", h["luac_int"]))
    w.out.extend(struct.pack("<d", h["luac_num"]))
    w.byte(h["root_closure_upvalue_count"])
    w.function(parsed["root"])
    w.out.extend(bytes.fromhex(parsed.get('trailing_hex', '')))
    return bytes(w.out)


def structural(proto: dict) -> dict:
    return {
        "depth": proto["depth"],
        "source": proto.get("source"),
        "source_present": proto.get("source_present", True),
        "linedefined": proto["linedefined"],
        "lastlinedefined": proto["lastlinedefined"],
        "numparams": proto["numparams"],
        "is_vararg": proto["is_vararg"],
        "maxstacksize": proto["maxstacksize"],
        "code": {"count": proto["code"]["count"], "words": proto["code"]["words"]},
        "constants": proto["constants"],
        "upvalues": proto["upvalues"],
        "children": [structural(c) for c in proto["children"]],
        "debug": proto["debug"],
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    report = {"writer": "custom Lua format inverse of bounded parser", "samples": []}
    all_ok = True
    for version in VERSIONS:
        source_path = BASE / version / "LuaScript.luac"
        parsed = parser.parse_sample(source_path)
        rebuilt = write_sample(parsed)
        out_path = OUT / f"{version}.LuaScript.roundtrip.luac"
        out_path.write_bytes(rebuilt)
        reparsed = parser.parse_sample(out_path)
        same_bytes = rebuilt == source_path.read_bytes()
        same_structure = structural(parsed["root"]) == structural(reparsed["root"])
        item = {
            "version": version,
            "source_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
            "roundtrip_sha256": hashlib.sha256(rebuilt).hexdigest(),
            "source_size": source_path.stat().st_size,
            "roundtrip_size": len(rebuilt),
            "byte_identical": same_bytes,
            "structure_identical": same_structure,
            "source_final_offset": parsed["final_offset"],
            "roundtrip_final_offset": reparsed["final_offset"],
            "source_remaining": parsed["remaining"],
            "roundtrip_remaining": reparsed["remaining"],
            "output": str(out_path),
        }
        if not same_bytes or not same_structure or reparsed["remaining"] != 0:
            all_ok = False
            if not same_bytes:
                a = source_path.read_bytes()
                first = next((i for i, (x, y) in enumerate(zip(a, rebuilt)) if x != y), min(len(a), len(rebuilt)))
                item["first_byte_difference"] = first
        report["samples"].append(item)
    (OUT / "roundtrip-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
