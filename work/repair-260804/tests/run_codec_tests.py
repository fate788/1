from __future__ import annotations

import copy
import hashlib
import json
import os
import shlex
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import archive_codec  # noqa: E402
import cetrainer_codec  # noqa: E402
import roundtrip_parser as parser  # noqa: E402
import roundtrip_writer as writer  # noqa: E402


VERSIONS = ("ARCHIVE-0604", "ARCHIVE-260718", "ARCHIVE-260804")
ARCHIVE_ROOT = HERE.parent / "archive-history"
FINALIZED = ARCHIVE_ROOT / "finalized"
RUN_ID = datetime.now().strftime("%Y%m%d-%H%M%S")
RUN_ROOT = HERE / "test-runs" / RUN_ID
RUN_ROOT.mkdir(parents=True, exist_ok=False)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def structural(proto: dict) -> dict:
    return writer.structural(proto)


def update_string(value: dict, new_bytes: bytes) -> None:
    value["size_including_nul"] = len(new_bytes) + 1
    value["text_hex"] = new_bytes.hex(" ")
    value["text"] = new_bytes.decode("utf-8", "replace")


def mutate_root_constant(parsed: dict, mode: str) -> tuple[dict, str, bytes]:
    modified = copy.deepcopy(parsed)
    root = modified["root"]
    target_index = next(
        i for i, c in enumerate(root["constants"])
        if c.get("tag") in (4, 20) and isinstance(c.get("value"), dict)
    )
    value = root["constants"][target_index]["value"]
    original = bytes.fromhex(value["text_hex"])
    if mode == "equal":
        new = (original[:-1] + bytes([original[-1] ^ 1])) if original else b"X"
    elif mode == "longer":
        new = original + b"X"
    elif mode == "shorter":
        new = original[:-1] if original else b""
    else:
        raise ValueError(mode)
    update_string(value, new)
    return modified, f"root.constants[{target_index}]", new


def run_luac() -> dict:
    section = {"samples": [], "mutation_tests": [], "writer_module": str(HERE / "roundtrip_writer.py")}
    for version in VERSIONS:
        source = FINALIZED / version / "LuaScript.luac"
        parsed = parser.parse_sample(source)
        rebuilt = writer.write_sample(parsed)
        out = RUN_ROOT / f"{version}.roundtrip.luac"
        out.write_bytes(rebuilt)
        reparsed = parser.parse_sample(out)
        section["samples"].append({
            "version": version,
            "source_sha256": sha256(source),
            "output_sha256": sha256(out),
            "source_size": source.stat().st_size,
            "output_size": out.stat().st_size,
            "byte_identical": rebuilt == source.read_bytes(),
            "structure_identical": structural(parsed["root"]) == structural(reparsed["root"]),
            "source_remaining": parsed["remaining"],
            "output_remaining": reparsed["remaining"],
            "output": str(out),
        })
        for mode in ("equal", "longer", "shorter"):
            modified, field, expected = mutate_root_constant(parsed, mode)
            changed = writer.write_sample(modified)
            mod_out = RUN_ROOT / f"{version}.{mode}.luac"
            mod_out.write_bytes(changed)
            reparsed_mod = parser.parse_sample(mod_out)
            target_index = int(field.split("[")[1].split("]")[0])
            actual = bytes.fromhex(reparsed_mod["root"]["constants"][target_index]["value"]["text_hex"])
            section["mutation_tests"].append({
                "version": version,
                "mode": mode,
                "field": field,
                "expected_bytes_sha256": hashlib.sha256(expected).hexdigest(),
                "actual_bytes_sha256": hashlib.sha256(actual).hexdigest(),
                "semantic_match": actual == expected,
                "structure_valid": reparsed_mod["remaining"] == 0 and reparsed_mod["structure"]["validation_error_count"] == 0,
                "output": str(mod_out),
                "is_candidate": False,
            })
    return section


def run_cetrainer() -> dict:
    section = {"samples": [], "mutation_tests": []}
    for version in VERSIONS:
        source = FINALIZED / version / "CET_TRAINER.CETRAINER"
        decoded = cetrainer_codec.decode_file(source)
        output = cetrainer_codec.encode_cetrainer(decoded["xml"])
        out = RUN_ROOT / f"{version}.CET_TRAINER.roundtrip"
        out.write_bytes(output)
        redecode = cetrainer_codec.decode_cetrainer(output)
        section["samples"].append({
            "version": version,
            "source_sha256": sha256(source),
            "output_sha256": sha256(out),
            "source_size": source.stat().st_size,
            "output_size": out.stat().st_size,
            "byte_identical": output == source.read_bytes(),
            "decoded_xml_identical": redecode["xml"] == decoded["xml"],
            "magic": decoded["magic"].decode("latin1"),
            "xml_sha256": hashlib.sha256(decoded["xml"]).hexdigest(),
            "output": str(out),
        })
        marker = b"\n<!-- repair roundtrip test only -->\n"
        if b"</CheatTable>" not in decoded["xml"]:
            raise AssertionError("CheatTable closing tag not found")
        mutated_xml = decoded["xml"].replace(b"</CheatTable>", marker + b"</CheatTable>", 1)
        mutated = cetrainer_codec.encode_cetrainer(mutated_xml)
        mut_out = RUN_ROOT / f"{version}.CET_TRAINER.mutated"
        mut_out.write_bytes(mutated)
        mut_decoded = cetrainer_codec.decode_cetrainer(mutated)
        section["mutation_tests"].append({
            "version": version,
            "marker_present": marker in mut_decoded["xml"],
            "decoded_sha256": hashlib.sha256(mut_decoded["xml"]).hexdigest(),
            "expected_sha256": hashlib.sha256(mutated_xml).hexdigest(),
            "output": str(mut_out),
            "is_candidate": False,
        })
    return section


def run_archive() -> dict:
    section = {"samples": [], "mutation_tests": []}
    for version in VERSIONS:
        source = ARCHIVE_ROOT / f"{version}.raw"
        decoded = archive_codec.decode_archive(source.read_bytes())
        rebuilt = archive_codec.encode_archive(decoded["entries"], trailing=decoded["trailing"])
        out = RUN_ROOT / f"{version}.archive.roundtrip.raw"
        out.write_bytes(rebuilt)
        redecode = archive_codec.decode_archive(rebuilt)
        source_entries = archive_codec.entry_manifest(decoded)
        output_entries = archive_codec.entry_manifest(redecode)
        section["samples"].append({
            "version": version,
            "source_sha256": sha256(source),
            "output_sha256": sha256(out),
            "source_size": source.stat().st_size,
            "output_size": out.stat().st_size,
            "byte_identical": rebuilt == source.read_bytes(),
            "entries_identical": source_entries == output_entries,
            "trailing_source_hex": decoded["trailing"].hex(),
            "trailing_preserved": redecode["trailing"] == decoded["trailing"],
            "output": str(out),
        })
        entries = [archive_codec.ArchiveEntry(e.name, e.folder, e.data) for e in decoded["entries"]]
        target = next(i for i, e in enumerate(entries) if e.name == b"defines.lua")
        original = entries[target].data
        entries[target].data = original + b"\n-- repair roundtrip test only\n"
        mut_out = RUN_ROOT / f"{version}.archive.mutated.raw"
        mut_out.write_bytes(archive_codec.encode_archive(entries, trailing=decoded["trailing"]))
        mut_decoded = archive_codec.decode_archive(mut_out.read_bytes())
        changed = archive_codec.entry_manifest(mut_decoded)
        unchanged_others = all(
            changed[i]["sha256"] == source_entries[i]["sha256"]
            for i in range(len(changed)) if i != target
        )
        section["mutation_tests"].append({
            "version": version,
            "target_index": target,
            "target_changed": changed[target]["sha256"] != source_entries[target]["sha256"],
            "other_entries_unchanged": unchanged_others,
            "entries_count_same": len(changed) == len(source_entries),
            "output": str(mut_out),
            "is_candidate": False,
        })
    return section


def main() -> int:
    command = "python .\\work\\repair-260804\\tests\\run_codec_tests.py"
    report = {
        "run_id": RUN_ID,
        "command": command,
        "cwd": str(Path.cwd()),
        "python": sys.executable,
        "sections": {
            "luac": run_luac(),
            "cetrainer": run_cetrainer(),
            "archive": run_archive(),
        },
        "candidate": False,
        "target_started": False,
        "game_touched": False,
    }
    report_path = RUN_ROOT / "codec-test-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(report_path), "run_id": RUN_ID}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
