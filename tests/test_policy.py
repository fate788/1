from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "local-module"))

from local_maintenance_policy import (  # noqa: E402
    parse_child5_response,
    select_game_state,
    validate_config,
)


def test_missing_key_matches_observed_failure():
    result = parse_child5_response(b"marker\nrecord-data", b"missing-key")
    assert result.status == "key_not_found"
    assert result.records == ()


def test_key_match_extracts_fixed_width_records_without_decoding():
    key = b"TEST-KEY"
    # The first 37 bytes are the matched prefix plus the two-byte offset used
    # by the recovered Lua slice loop; two complete 35-byte rows follow.
    row1 = bytes(range(35))
    row2 = bytes(range(35, 70))
    response = key + b"xx" + row1 + row2 + b"\ntrailing"
    result = parse_child5_response(response, key)
    assert result.status == "records_parsed"
    assert result.records == (row1, row2)


def test_selection_preserves_recovered_codes_and_fails_closed():
    identity = lambda value: value
    code, reason = select_game_state((b"33",), identity, b"unused")
    assert (code, reason) == (306, "direct_first_record")
    code, reason = select_game_state((b"other", b"runtime"), identity, b"runtime")
    assert (code, reason) == (317, "pair_record_match")
    code, reason = select_game_state((b"other",), identity, b"runtime")
    assert (code, reason) == (None, "no_record_match")


def test_config_missing_data_is_valid_but_disabled():
    config = json.loads((Path(__file__).resolve().parents[1] / "local-module" / "maintenance-config.json").read_text(encoding="utf-8"))
    ok, errors = validate_config(config)
    assert ok, errors
    assert config["enabled"] is False


def test_enabled_empty_and_malformed_data_are_rejected():
    base = {
        "schema_version": 1,
        "target_process": "SC2_x64.exe",
        "target_game_build": "5.0.17.98370",
        "selection": {"direct_code": 306, "pair_code": 317},
        "records": [],
        "enabled": True,
    }
    ok, errors = validate_config(base)
    assert not ok and any("empty data" in e for e in errors)
    base["enabled"] = False
    base["records"] = [base64.b64encode(b"short").decode("ascii")]
    ok, errors = validate_config(base)
    assert not ok and any("exactly 35" in e for e in errors)

