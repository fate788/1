#!/usr/bin/env python3
"""Create compact structural exports from parse_custom_luac.py output."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


TARGETS = {"closece", "closece", "exit", "os", "onluaerror", "getsc2processpid", "sc2_x64.exe"}


def walk(proto: dict, path: str = "root"):
    yield proto, path
    for i, child in enumerate(proto["children"]):
        yield from walk(child, f"{path}.child{i}")


def string_value(c: dict):
    if c.get("kind") in ("short_string", "long_string") and isinstance(c.get("value"), dict):
        return c["value"].get("text")
    return None


def sample_summary(sample: dict) -> dict:
    functions = []
    strings = []
    numbers = []
    call_sites = []
    for proto, path in walk(sample["root"]):
        constants = proto["constants"]
        for i, c in enumerate(constants):
            v = string_value(c)
            if v is not None:
                strings.append({"function": path, "constant": i, "value": v})
            elif c.get("kind") in ("integer", "float"):
                numbers.append({"function": path, "constant": i, "kind": c["kind"], "value": c.get("value")})
        functions.append({
            "path": path,
            "depth": proto["depth"],
            "source": proto["source"],
            "linedefined": proto["linedefined"],
            "lastlinedefined": proto["lastlinedefined"],
            "numparams": proto["numparams"],
            "is_vararg": proto["is_vararg"],
            "maxstacksize": proto["maxstacksize"],
            "code_count": proto["code"]["count"],
            "constant_count": len(constants),
            "upvalue_count": proto["upvalue_count"],
            "child_count": proto["proto_count"],
            "instructions": proto["code"]["instructions"],
            "constants": constants,
            "upvalues": proto["upvalues"],
            "debug": proto["debug"],
        })
        values = {i: string_value(c) for i, c in enumerate(constants)}
        instructions = proto["code"]["instructions"]
        for pos, ins in enumerate(instructions):
            refs = []
            for fld in ("B", "C"):
                x = ins[fld]
                if x & 0x100:
                    refs.append((fld, x & 0xFF))
            if ins["opcode"] == 1:
                refs.append(("Bx", ins["Bx"]))
            for fld, idx in refs:
                val = values.get(idx)
                if isinstance(val, str) and val.lower() in TARGETS:
                    following = instructions[pos + 1:pos + 4]
                    call = next((x for x in following if x["opcode"] in (36, 37)), None)
                    call_sites.append({"function": path, "pc": ins["pc"],
                                       "opname": ins["opname"], "operand": fld,
                                       "constant": idx, "value": val,
                                       "following_call": call})
    unique_strings = sorted({x["value"] for x in strings})
    unique_numbers = sorted({json.dumps(x["value"], ensure_ascii=False, sort_keys=True)
                             for x in numbers})
    return {
        "version": sample["version"],
        "status": sample["status"],
        "header": sample.get("header"),
        "structure": sample.get("structure"),
        "final_offset": sample.get("final_offset"),
        "remaining": sample.get("remaining"),
        "functions": functions,
        "string_constants": strings,
        "unique_string_count": len(unique_strings),
        "unique_strings": unique_strings,
        "numeric_constants": numbers,
        "unique_numeric_count": len(unique_numbers),
        "unique_numeric_json": unique_numbers,
        "interesting_call_sites": call_sites,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    parsed = json.loads(args.input.read_text(encoding="utf-8"))
    args.out.write_text(json.dumps({"source": str(args.input),
                                    "samples": [sample_summary(s) for s in parsed["samples"]]},
                                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
