"""Offline, fail-closed model of the recovered Child Proto 5/R23 policy.

This module does not contact the network, execute Lua, inspect the game, or
change the original trainer.  It is deliberately a policy/data-source seam
for a future integration after a verified record set and a bytecode writer are
available.
"""

from __future__ import annotations

from dataclasses import dataclass
import base64
import json
from pathlib import Path
from typing import Callable, Iterable


RECORD_WIDTH = 35
MAX_RECORDS = 4096
MAX_RESPONSE_BYTES = 16 * 1024 * 1024
SUPPORTED_GAME_BUILDS = {"5.0.17.98370"}


@dataclass(frozen=True)
class ParseResult:
    status: str
    records: tuple[bytes, ...]
    match_offset: int | None
    line_end_offset: int | None


def parse_child5_response(response: bytes, key: bytes, *, max_records: int = MAX_RECORDS) -> ParseResult:
    """Mirror the observed Child Proto 5 string operations on bytes.

    Offsets in the result are zero-based Python offsets.  No text decoding,
    normalization, or case folding is performed.  A successful substring
    match does not imply a valid business response; this function reports only
    the recovered structural result.
    """
    if not isinstance(response, (bytes, bytearray)) or not isinstance(key, (bytes, bytearray)):
        return ParseResult("error:type", (), None, None)
    response = bytes(response)
    key = bytes(key)
    if len(response) > MAX_RESPONSE_BYTES or max_records <= 0:
        return ParseResult("error:bounds", (), None, None)

    pos = response.find(key)
    if pos < 0:
        return ParseResult("key_not_found", (), None, None)

    newline = response.find(b"\n", pos)
    line_end = len(response) if newline < 0 else newline
    chunk = response[pos:line_end]

    records: list[bytes] = []
    i = 1  # observed Lua loop starts at integer 1 for the 35-byte stride
    while i <= max_records:
        # Lua string.sub(chunk, 3 + 35*i, 3 + 35*i + 34), converted to
        # zero-based half-open Python offsets.
        start = (3 + RECORD_WIDTH * i) - 1
        end = start + RECORD_WIDTH
        if start >= len(chunk):
            break
        field = chunk[start:end]
        if field == b"":
            break
        records.append(field)
        i += 1
    else:
        return ParseResult("error:record_limit", tuple(records), pos, line_end)

    return ParseResult("records_parsed" if records else "matched_empty", tuple(records), pos, line_end)


def select_game_state(
    records: Iterable[bytes],
    smdx: Callable[[bytes], bytes],
    captured_runtime_value: bytes,
) -> tuple[int | None, str]:
    """Mirror the two observed selection branches without forcing a result."""
    rows = tuple(records)
    if rows and rows[0] == smdx(b"33"):
        return 306, "direct_first_record"
    wanted = smdx(bytes(captured_runtime_value))
    for row in rows:
        if row == wanted:
            return 317, "pair_record_match"
    return None, "no_record_match"


def decode_records(config: dict) -> tuple[bytes, ...]:
    records = config.get("records")
    if not isinstance(records, list):
        raise ValueError("records must be a list")
    decoded: list[bytes] = []
    for index, item in enumerate(records):
        if not isinstance(item, str):
            raise ValueError(f"records[{index}] must be base64 text")
        try:
            row = base64.b64decode(item, validate=True)
        except Exception as exc:
            raise ValueError(f"records[{index}] is not valid base64") from exc
        if len(row) != RECORD_WIDTH:
            raise ValueError(f"records[{index}] must decode to exactly {RECORD_WIDTH} bytes")
        decoded.append(row)
    if len(decoded) > MAX_RECORDS:
        raise ValueError("too many records")
    return tuple(decoded)


def validate_config(config: dict) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if config.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if config.get("target_process") != "SC2_x64.exe":
        errors.append("target_process must be SC2_x64.exe")
    if not isinstance(config.get("target_game_build"), str) or not config["target_game_build"]:
        errors.append("target_game_build is required")
    elif config["target_game_build"] not in SUPPORTED_GAME_BUILDS:
        errors.append("target_game_build is not in the locally verified build set")
    try:
        rows = decode_records(config)
    except ValueError as exc:
        errors.append(str(exc))
        rows = ()
    if config.get("enabled") is True and not rows:
        errors.append("enabled=true requires verified local records; empty data is not success")
    selection = config.get("selection")
    if not isinstance(selection, dict) or selection.get("direct_code") != 306 or selection.get("pair_code") != 317:
        errors.append("selection codes must retain recovered values 306 and 317")
    return not errors, errors


def load_config(path: Path) -> dict:
    config = json.loads(path.read_text(encoding="utf-8"))
    ok, errors = validate_config(config)
    if not ok:
        raise ValueError("; ".join(errors))
    return config

