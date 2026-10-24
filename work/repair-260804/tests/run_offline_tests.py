from __future__ import annotations

import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("test_policy", HERE / "test_policy.py")
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)

tests = [name for name in dir(module) if name.startswith("test_")]
failed = []
for name in tests:
    try:
        getattr(module, name)()
        print(f"PASS {name}")
    except Exception as exc:
        failed.append((name, repr(exc)))
        print(f"FAIL {name}: {exc!r}")
if failed:
    raise SystemExit(1)
print(f"ALL_PASS count={len(tests)}")
