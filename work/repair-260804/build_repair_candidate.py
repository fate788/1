from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
REFERENCE = HERE / "reference"
CONFIG = HERE / "local-module" / "maintenance-config.json"
OUT = HERE / "candidate"

EXPECTED = {
    "SC2_Inv_260804SPt19_1316241517.original-copy.exe": "cea1493191bbd5513f556413d167e2fad81879e91294dff7c5cdca61497cc9ef",
    "LuaScript-260804.luac": "f3f8a6fb27551b7534717536bba2f971ef93282ed9b2ab3c51607e7dd9bed28b",
    "lua53-64.dll": "436f6bf9ac414e7e7259bef4f6e287702a41e1fddbdd9af7d43350d47539a3c9",
    "cheatengine-x86_64.exe": "c743cbed593eabb1bf8f938395045df5c6422ffa9edb3a7be6abcbcb86398b01",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    observed = {}
    failures = []
    for name, wanted in EXPECTED.items():
        path = REFERENCE / name
        if not path.is_file():
            failures.append(f"missing reference: {path}")
            continue
        got = sha256(path)
        observed[name] = {"path": str(path), "sha256": got, "expected": wanted, "match": got == wanted}
        if got != wanted:
            failures.append(f"hash mismatch: {name}")

    try:
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
    except Exception as exc:
        failures.append(f"config read error: {exc}")
        config = {}

    # Import the local module without installing anything globally.
    sys.path.insert(0, str(HERE / "local-module"))
    from local_maintenance_policy import validate_config  # type: ignore

    config_ok, config_errors = validate_config(config)
    if not config_ok:
        failures.extend(f"config: {e}" for e in config_errors)

    # This guard is intentional: the policy input and host integration are
    # still unresolved, and the codecs are not wired into a complete EXE
    # rebuild/load path.  A build must refuse to emit an unverified bypass.
    blockers = [
        "no verified successful response records are present",
        "gameIntCode host registration and the 306/317 consumer contract are unresolved",
        "LuaScript/CETRAINER/ARCHIVE codecs are not integrated into a complete EXE rebuild and loader validation path",
        "the local config is disabled and contains no records",
    ]
    layers = {
        "luascript_roundtrip": "passed",
        "cetrainer_roundtrip": "passed_content_only",
        "archive_roundtrip": "passed_content_only",
        "policy_unit": "passed_separately",
        "integration": "not_run",
    }
    manifest = {
        "status": "candidate_not_built",
        "reason": "; ".join(blockers),
        "layers": layers,
        "input_hashes": observed,
        "config": str(CONFIG),
        "config_valid": config_ok,
        "config_errors": config_errors,
        "output_exe": None,
        "original_files_unchanged": True,
        "network_access": False,
        "game_files_modified": False,
        "security_settings_modified": False,
    }
    (OUT / "repair-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    if failures:
        print("INPUT_CHECK_FAILED", file=sys.stderr)
        for failure in failures:
            print(failure, file=sys.stderr)
        return 2
    print("No EXE emitted: guarded candidate build still requires verified policy records, host semantics, and an integrated packaging/load path.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
