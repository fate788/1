#!/usr/bin/env python3
"""Verify that DEBUG_PROCESS observes a harmless descendant process."""
from __future__ import annotations

import ctypes
import json
import sys
from ctypes import wintypes
from pathlib import Path

from win32_debug_selftest import (
    CREATE_PROCESS_DEBUG_EVENT,
    DEBUG_EVENT,
    EXCEPTION_DEBUG_EVENT,
    EXIT_PROCESS_DEBUG_EVENT,
    OUTPUT_DEBUG_STRING_INFO,
    PROCESS_INFORMATION,
    STARTUPINFO,
    STATUS_BREAKPOINT,
    DBG_CONTINUE,
    DBG_EXCEPTION_NOT_HANDLED,
    kernel32,
)


DEBUG_PROCESS = 0x00000001
root = Path(__file__).resolve().parent
py = Path(sys.executable).resolve()
parent = root / "debuggee_parent.py"
command = f'"{py}" -B "{parent}"'
buffer = ctypes.create_unicode_buffer(command)
si = STARTUPINFO()
si.cb = ctypes.sizeof(si)
pi = PROCESS_INFORMATION()
if not kernel32.CreateProcessW(
    None,
    buffer,
    None,
    None,
    False,
    DEBUG_PROCESS,
    None,
    str(root),
    ctypes.byref(si),
    ctypes.byref(pi),
):
    raise ctypes.WinError(ctypes.get_last_error())

events: list[dict] = []
pids: set[int] = set()
sentinel = False
child_break = False
exit_codes: dict[int, int] = {}
try:
    while True:
        event = DEBUG_EVENT()
        if not kernel32.WaitForDebugEvent(ctypes.byref(event), 5000):
            raise ctypes.WinError(ctypes.get_last_error())
        pid = int(event.dwProcessId)
        record = {"code": int(event.dwDebugEventCode), "pid": pid, "tid": int(event.dwThreadId)}
        if event.dwDebugEventCode == CREATE_PROCESS_DEBUG_EVENT:
            pids.add(pid)
        elif event.dwDebugEventCode == 8:
            info = event.u.OutputDebugString
            record["debug_string_length"] = int(info.nDebugStringLength)
            sentinel = True
        elif event.dwDebugEventCode == EXCEPTION_DEBUG_EVENT:
            exc = event.u.Exception.ExceptionRecord
            record["exception_code"] = hex(int(exc.ExceptionCode))
            record["first_chance"] = int(event.u.Exception.dwFirstChance)
            if exc.ExceptionCode == STATUS_BREAKPOINT and event.u.Exception.dwFirstChance and sentinel:
                child_break = True
            else:
                # Keep ordinary loader exceptions flowing to the process.
                pass
        elif event.dwDebugEventCode == EXIT_PROCESS_DEBUG_EVENT:
            exit_codes[pid] = int(event.u.ExitProcess.dwExitCode)
        events.append(record)
        status = DBG_CONTINUE
        if event.dwDebugEventCode == EXCEPTION_DEBUG_EVENT:
            exc = event.u.Exception.ExceptionRecord
            if not (exc.ExceptionCode == STATUS_BREAKPOINT and event.u.Exception.dwFirstChance):
                status = DBG_EXCEPTION_NOT_HANDLED
        if not kernel32.ContinueDebugEvent(event.dwProcessId, event.dwThreadId, status):
            raise ctypes.WinError(ctypes.get_last_error())
        if event.dwDebugEventCode == EXIT_PROCESS_DEBUG_EVENT and pid == pi.dwProcessId:
            break
finally:
    kernel32.CloseHandle(pi.hThread)
    kernel32.CloseHandle(pi.hProcess)

result = {
    "python": str(py),
    "command": command,
    "debug_process": True,
    "observed_process_ids": sorted(pids),
    "process_count": len(pids),
    "sentinel_seen": sentinel,
    "descendant_breakpoint_seen": child_break,
    "exit_codes": exit_codes,
    "events": events,
}
print(json.dumps(result, ensure_ascii=False, indent=2))
raise SystemExit(0 if len(pids) >= 2 and child_break else 1)
