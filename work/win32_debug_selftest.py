#!/usr/bin/env python3
"""Minimal child-process debug API self-test.

The child is a workspace-created Python script that calls kernel32!DebugBreak.
This test does not load or start the requested modifier or any game process.
"""
from __future__ import annotations

import ctypes
import json
import re
import struct
import subprocess
import sys
from ctypes import wintypes
from pathlib import Path


kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

DEBUG_ONLY_THIS_PROCESS = 0x00000002
EXCEPTION_DEBUG_EVENT = 1
CREATE_PROCESS_DEBUG_EVENT = 3
EXIT_PROCESS_DEBUG_EVENT = 5
DBG_CONTINUE = 0x00010002
DBG_EXCEPTION_NOT_HANDLED = 0x80010001
STATUS_BREAKPOINT = 0x80000003


class STARTUPINFO(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("lpReserved", wintypes.LPWSTR),
        ("lpDesktop", wintypes.LPWSTR),
        ("lpTitle", wintypes.LPWSTR),
        ("dwX", wintypes.DWORD),
        ("dwY", wintypes.DWORD),
        ("dwXSize", wintypes.DWORD),
        ("dwYSize", wintypes.DWORD),
        ("dwXCountChars", wintypes.DWORD),
        ("dwYCountChars", wintypes.DWORD),
        ("dwFillAttribute", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("wShowWindow", wintypes.WORD),
        ("cbReserved2", wintypes.WORD),
        ("lpReserved2", ctypes.POINTER(ctypes.c_byte)),
        ("hStdInput", wintypes.HANDLE),
        ("hStdOutput", wintypes.HANDLE),
        ("hStdError", wintypes.HANDLE),
    ]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("hProcess", wintypes.HANDLE),
        ("hThread", wintypes.HANDLE),
        ("dwProcessId", wintypes.DWORD),
        ("dwThreadId", wintypes.DWORD),
    ]


class EXCEPTION_RECORD(ctypes.Structure):
    _fields_ = [
        ("ExceptionCode", wintypes.DWORD),
        ("ExceptionFlags", wintypes.DWORD),
        ("ExceptionRecord", ctypes.c_void_p),
        ("ExceptionAddress", ctypes.c_void_p),
        ("NumberParameters", wintypes.DWORD),
        ("ExceptionInformation", ctypes.c_ulonglong * 15),
    ]


class EXCEPTION_DEBUG_INFO(ctypes.Structure):
    _fields_ = [
        ("ExceptionRecord", EXCEPTION_RECORD),
        ("dwFirstChance", wintypes.DWORD),
    ]


class CREATE_PROCESS_DEBUG_INFO(ctypes.Structure):
    _fields_ = [
        ("hFile", wintypes.HANDLE),
        ("hProcess", wintypes.HANDLE),
        ("hThread", wintypes.HANDLE),
        ("lpBaseOfImage", ctypes.c_void_p),
        ("dwDebugInfoFileOffset", wintypes.DWORD),
        ("nDebugInfoSize", wintypes.DWORD),
        ("lpThreadLocalBase", ctypes.c_void_p),
        ("lpStartAddress", ctypes.c_void_p),
        ("lpImageName", ctypes.c_void_p),
        ("fUnicode", wintypes.WORD),
    ]


class EXIT_PROCESS_DEBUG_INFO(ctypes.Structure):
    _fields_ = [("dwExitCode", wintypes.DWORD)]


class OUTPUT_DEBUG_STRING_INFO(ctypes.Structure):
    _fields_ = [
        ("lpDebugStringData", ctypes.c_void_p),
        ("fUnicode", wintypes.WORD),
        ("nDebugStringLength", wintypes.WORD),
    ]


class DEBUG_UNION(ctypes.Union):
    _fields_ = [
        ("Exception", EXCEPTION_DEBUG_INFO),
        ("CreateProcessInfo", CREATE_PROCESS_DEBUG_INFO),
        ("ExitProcess", EXIT_PROCESS_DEBUG_INFO),
        ("OutputDebugString", OUTPUT_DEBUG_STRING_INFO),
        ("raw", ctypes.c_byte * 160),
    ]


class DEBUG_EVENT(ctypes.Structure):
    _fields_ = [
        ("dwDebugEventCode", wintypes.DWORD),
        ("dwProcessId", wintypes.DWORD),
        ("dwThreadId", wintypes.DWORD),
        ("u", DEBUG_UNION),
    ]


kernel32.CreateProcessW.argtypes = [
    wintypes.LPCWSTR,
    wintypes.LPWSTR,
    ctypes.c_void_p,
    ctypes.c_void_p,
    wintypes.BOOL,
    wintypes.DWORD,
    ctypes.c_void_p,
    wintypes.LPCWSTR,
    ctypes.POINTER(STARTUPINFO),
    ctypes.POINTER(PROCESS_INFORMATION),
]
kernel32.CreateProcessW.restype = wintypes.BOOL
kernel32.WaitForDebugEvent.argtypes = [ctypes.POINTER(DEBUG_EVENT), wintypes.DWORD]
kernel32.WaitForDebugEvent.restype = wintypes.BOOL
kernel32.ContinueDebugEvent.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.DWORD]
kernel32.ContinueDebugEvent.restype = wintypes.BOOL
kernel32.GetThreadContext.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
kernel32.GetThreadContext.restype = wintypes.BOOL
kernel32.ReadProcessMemory.argtypes = [
    wintypes.HANDLE,
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t),
]
kernel32.ReadProcessMemory.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL

# x64 CONTEXT layout through Rip. The full buffer is intentionally oversized
# for the Windows x64 CONTEXT structure; offsets are from the documented x64
# layout and are used only for this self-created test process.
CONTEXT_FULL = 0x00010007
CONTEXT_SIZE = 1232
CONTEXT_FLAGS_OFFSET = 48
CONTEXT_RSP_OFFSET = 152
CONTEXT_RIP_OFFSET = 248


def main() -> int:
    root = Path(__file__).resolve().parent
    child = root / "debuggee_break.py"
    py = Path(sys.executable).resolve()
    command = f'"{py}" -B "{child}"'
    command_buffer = ctypes.create_unicode_buffer(command)
    si = STARTUPINFO()
    si.cb = ctypes.sizeof(si)
    pi = PROCESS_INFORMATION()
    started = kernel32.CreateProcessW(
        None,
        command_buffer,
        None,
        None,
        False,
        DEBUG_ONLY_THIS_PROCESS,
        None,
        str(root),
        ctypes.byref(si),
        ctypes.byref(pi),
    )
    if not started:
        raise ctypes.WinError(ctypes.get_last_error())

    events: list[dict] = []
    breakpoint_seen = False
    sentinel_seen = False
    sentinel_breakpoint_seen = False
    context_read = False
    context_rip = None
    context_rsp = None
    memory_read = False
    memory_match = False
    exit_code: int | None = None
    try:
        while True:
            event = DEBUG_EVENT()
            if not kernel32.WaitForDebugEvent(ctypes.byref(event), 5000):
                error = ctypes.get_last_error()
                raise ctypes.WinError(error)
            record = {
                "code": int(event.dwDebugEventCode),
                "pid": int(event.dwProcessId),
                "tid": int(event.dwThreadId),
            }
            continue_status = DBG_CONTINUE
            if event.dwDebugEventCode == CREATE_PROCESS_DEBUG_EVENT:
                record["image_base"] = hex(event.u.CreateProcessInfo.lpBaseOfImage or 0)
                record["start_address"] = hex(event.u.CreateProcessInfo.lpStartAddress or 0)
            elif event.dwDebugEventCode == EXCEPTION_DEBUG_EVENT:
                exc = event.u.Exception.ExceptionRecord
                record["exception_code"] = hex(int(exc.ExceptionCode))
                record["first_chance"] = int(event.u.Exception.dwFirstChance)
                record["exception_address"] = hex(int(exc.ExceptionAddress or 0))
                if exc.ExceptionCode == STATUS_BREAKPOINT and event.u.Exception.dwFirstChance:
                    breakpoint_seen = True
                    if sentinel_seen:
                        sentinel_breakpoint_seen = True
                        buffer = (ctypes.c_ubyte * CONTEXT_SIZE)()
                        struct.pack_into("<I", buffer, CONTEXT_FLAGS_OFFSET, CONTEXT_FULL)
                        if kernel32.GetThreadContext(pi.hThread, ctypes.byref(buffer)):
                            context_read = True
                            context_rsp = hex(struct.unpack_from("<Q", buffer, CONTEXT_RSP_OFFSET)[0])
                            context_rip = hex(struct.unpack_from("<Q", buffer, CONTEXT_RIP_OFFSET)[0])
                            record["context_rip"] = context_rip
                            record["context_rsp"] = context_rsp
                else:
                    continue_status = DBG_EXCEPTION_NOT_HANDLED
            elif event.dwDebugEventCode == 8:
                info = event.u.OutputDebugString
                record["debug_string_length"] = int(info.nDebugStringLength)
                record["debug_string_unicode"] = bool(info.fUnicode)
                # Read only the self-created ASCII address marker.
                n = min(max(int(info.nDebugStringLength), 1), 256)
                raw = (ctypes.c_char * n)()
                got = ctypes.c_size_t()
                if kernel32.ReadProcessMemory(
                    pi.hProcess,
                    info.lpDebugStringData,
                    ctypes.byref(raw),
                    n,
                    ctypes.byref(got),
                ):
                    marker = bytes(raw[: got.value]).split(b"\0", 1)[0].decode("ascii", "ignore")
                    match = re.fullmatch(r"CODEX_MEM_ADDR=0x([0-9a-fA-F]+)", marker)
                    if match:
                        address = int(match.group(1), 16)
                        target = (ctypes.c_char * len(b"CODEX_MEMORY_SENTINEL"))()
                        target_got = ctypes.c_size_t()
                        if kernel32.ReadProcessMemory(
                            pi.hProcess,
                            ctypes.c_void_p(address),
                            ctypes.byref(target),
                            len(target),
                            ctypes.byref(target_got),
                        ):
                            memory_read = True
                            memory_match = bytes(target[: target_got.value]) == b"CODEX_MEMORY_SENTINEL"
                            record["memory_sentinel_read"] = memory_match
                # Do not retain the marker's address or contents in the report.
                sentinel_seen = True
            elif event.dwDebugEventCode == EXIT_PROCESS_DEBUG_EVENT:
                exit_code = int(event.u.ExitProcess.dwExitCode)
            events.append(record)
            if not kernel32.ContinueDebugEvent(event.dwProcessId, event.dwThreadId, continue_status):
                raise ctypes.WinError(ctypes.get_last_error())
            if event.dwDebugEventCode == EXIT_PROCESS_DEBUG_EVENT:
                break
    finally:
        kernel32.CloseHandle(pi.hThread)
        kernel32.CloseHandle(pi.hProcess)

    result = {
        "python": str(py),
        "command": command,
        "child": str(child),
        "debug_only_this_process": True,
        "breakpoint_seen": breakpoint_seen,
        "sentinel_seen": sentinel_seen,
        "sentinel_breakpoint_seen": sentinel_breakpoint_seen,
        "context_read": context_read,
        "context_rip": context_rip,
        "context_rsp": context_rsp,
        "memory_read": memory_read,
        "memory_match": memory_match,
        "exit_code": exit_code,
        "events": events,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if sentinel_breakpoint_seen and context_read and memory_read and memory_match and exit_code == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
