#!/usr/bin/env python3
"""One-shot, ordinary-user startup observation for the workspace modifier copy.

This debugger changes only the debugged process address space: it installs
three temporary INT3 breakpoints in the verified lua53-64.dll image and uses
single-step to restore/reinstall them.  It never writes the target EXE, game
files, or network responses.
"""
from __future__ import annotations

import ctypes
import hashlib
import json
import os
import struct
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from ctypes import wintypes

KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True)
NTDLL = ctypes.WinDLL("ntdll")

DEBUG_PROCESS = 0x00000001
EXCEPTION_DEBUG_EVENT = 1
CREATE_PROCESS_DEBUG_EVENT = 3
CREATE_THREAD_DEBUG_EVENT = 2
EXIT_PROCESS_DEBUG_EVENT = 5
EXIT_THREAD_DEBUG_EVENT = 4
LOAD_DLL_DEBUG_EVENT = 6
UNLOAD_DLL_DEBUG_EVENT = 7
OUTPUT_DEBUG_STRING_EVENT = 8
RIP_EVENT = 9

DBG_CONTINUE = 0x00010002
DBG_EXCEPTION_NOT_HANDLED = 0x80010001
STATUS_BREAKPOINT = 0x80000003
STATUS_SINGLE_STEP = 0x80000004
ERROR_SEM_TIMEOUT = 121

THREAD_GET_CONTEXT = 0x0008
THREAD_SET_CONTEXT = 0x0010
THREAD_QUERY_INFORMATION = 0x0040
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_VM_OPERATION = 0x0008
MEM_COMMIT = 0x1000
PAGE_NOACCESS = 0x01
PAGE_GUARD = 0x100
IMAGE_FILE_MACHINE_I386 = 0x014C
IMAGE_FILE_MACHINE_AMD64 = 0x8664

CONTEXT_FULL = 0x00010007
CONTEXT_SIZE = 1232
CONTEXT_FLAGS_OFFSET = 48
CONTEXT_EFLAGS_OFFSET = 68
CONTEXT_RBP_OFFSET = 160
CONTEXT_RIP_OFFSET = 248
CONTEXT_RAX_OFFSET = 120
CONTEXT_RCX_OFFSET = 128

TIMEOUT_SECONDS = 45.0
MAX_VM_HITS = 20000
EXPECTED_LUA_SHA256 = "436f6bf9ac414e7e7259bef4f6e287702a41e1fddbdd9af7d43350d47539a3c9"
EXPECTED_ROOT_SIZECODE = 1469
ROOT_SIGNATURE_PC = 129
ROOT_SIGNATURE = (
    0x0006C481, 0x000704C1, 0x00074501, 0x00478546,
    0x00808564, 0x0AC7C587, 0x0A0005C0, 0x010085A4,
)
ROOT_WORDS = {
    154: 0x0B807D1F,
    155: 0x8000401E,
    172: 0x00004622,
    173: 0x8000401E,
}

WORK = Path(__file__).resolve().parent
TARGET = WORK / "target-observation" / "SC2_Inv_260804SPt19_1316241517.exe"
OUTPUT = Path(__file__).resolve().parents[1] / "outputs" / "startup-observation-run.json"
EXPECTED_DLL_FILE = (
    Path(__file__).resolve().parent
    / "archive-history" / "finalized" / "ARCHIVE-260804" / "lua53-64.dll"
)


class STARTUPINFO(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD), ("lpReserved", wintypes.LPWSTR),
        ("lpDesktop", wintypes.LPWSTR), ("lpTitle", wintypes.LPWSTR),
        ("dwX", wintypes.DWORD), ("dwY", wintypes.DWORD),
        ("dwXSize", wintypes.DWORD), ("dwYSize", wintypes.DWORD),
        ("dwXCountChars", wintypes.DWORD), ("dwYCountChars", wintypes.DWORD),
        ("dwFillAttribute", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
        ("wShowWindow", wintypes.WORD), ("cbReserved2", wintypes.WORD),
        ("lpReserved2", ctypes.POINTER(ctypes.c_byte)),
        ("hStdInput", wintypes.HANDLE), ("hStdOutput", wintypes.HANDLE),
        ("hStdError", wintypes.HANDLE),
    ]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("hProcess", wintypes.HANDLE), ("hThread", wintypes.HANDLE),
        ("dwProcessId", wintypes.DWORD), ("dwThreadId", wintypes.DWORD),
    ]


class EXCEPTION_RECORD(ctypes.Structure):
    _fields_ = [
        ("ExceptionCode", wintypes.DWORD), ("ExceptionFlags", wintypes.DWORD),
        ("ExceptionRecord", ctypes.c_void_p), ("ExceptionAddress", ctypes.c_void_p),
        ("NumberParameters", wintypes.DWORD),
        ("ExceptionInformation", ctypes.c_ulonglong * 15),
    ]


class EXCEPTION_DEBUG_INFO(ctypes.Structure):
    _fields_ = [("ExceptionRecord", EXCEPTION_RECORD), ("dwFirstChance", wintypes.DWORD)]


class CREATE_PROCESS_DEBUG_INFO(ctypes.Structure):
    _fields_ = [
        ("hFile", wintypes.HANDLE), ("hProcess", wintypes.HANDLE),
        ("hThread", wintypes.HANDLE), ("lpBaseOfImage", ctypes.c_void_p),
        ("dwDebugInfoFileOffset", wintypes.DWORD), ("nDebugInfoSize", wintypes.DWORD),
        ("lpThreadLocalBase", ctypes.c_void_p), ("lpStartAddress", ctypes.c_void_p),
        ("lpImageName", ctypes.c_void_p), ("fUnicode", wintypes.WORD),
    ]


class LOAD_DLL_DEBUG_INFO(ctypes.Structure):
    _fields_ = [
        ("hFile", wintypes.HANDLE), ("lpBaseOfDll", ctypes.c_void_p),
        ("dwDebugInfoFileOffset", wintypes.DWORD), ("nDebugInfoSize", wintypes.DWORD),
        ("lpImageName", ctypes.c_void_p), ("fUnicode", wintypes.WORD),
    ]


class EXIT_PROCESS_DEBUG_INFO(ctypes.Structure):
    _fields_ = [("dwExitCode", wintypes.DWORD)]


class OUTPUT_DEBUG_STRING_INFO(ctypes.Structure):
    _fields_ = [
        ("lpDebugStringData", ctypes.c_void_p), ("fUnicode", wintypes.WORD),
        ("nDebugStringLength", wintypes.WORD),
    ]


class DEBUG_UNION(ctypes.Union):
    _fields_ = [
        ("Exception", EXCEPTION_DEBUG_INFO),
        ("CreateProcessInfo", CREATE_PROCESS_DEBUG_INFO),
        ("LoadDll", LOAD_DLL_DEBUG_INFO),
        ("ExitProcess", EXIT_PROCESS_DEBUG_INFO),
        ("OutputDebugString", OUTPUT_DEBUG_STRING_INFO),
        ("raw", ctypes.c_byte * 160),
    ]


class DEBUG_EVENT(ctypes.Structure):
    _fields_ = [
        ("dwDebugEventCode", wintypes.DWORD), ("dwProcessId", wintypes.DWORD),
        ("dwThreadId", wintypes.DWORD), ("u", DEBUG_UNION),
    ]


class PROCESS_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("ExitStatus", ctypes.c_long), ("PebBaseAddress", ctypes.c_void_p),
        ("AffinityMask", ctypes.c_void_p), ("BasePriority", ctypes.c_long),
        ("UniqueProcessId", ctypes.c_void_p), ("InheritedFromUniqueProcessId", ctypes.c_void_p),
    ]


class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", wintypes.DWORD), ("_pad", wintypes.DWORD),
        ("RegionSize", ctypes.c_size_t), ("State", wintypes.DWORD),
        ("Protect", wintypes.DWORD), ("Type", wintypes.DWORD),
    ]


def proto(lib, name, args, result):
    fn = getattr(lib, name)
    fn.argtypes = args
    fn.restype = result
    return fn


CreateProcessW = proto(KERNEL32, "CreateProcessW", [
    wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.c_void_p, ctypes.c_void_p,
    wintypes.BOOL, wintypes.DWORD, ctypes.c_void_p, wintypes.LPCWSTR,
    ctypes.POINTER(STARTUPINFO), ctypes.POINTER(PROCESS_INFORMATION)], wintypes.BOOL)
WaitForDebugEvent = proto(KERNEL32, "WaitForDebugEvent", [ctypes.POINTER(DEBUG_EVENT), wintypes.DWORD], wintypes.BOOL)
ContinueDebugEvent = proto(KERNEL32, "ContinueDebugEvent", [wintypes.DWORD, wintypes.DWORD, wintypes.DWORD], wintypes.BOOL)
ReadProcessMemory = proto(KERNEL32, "ReadProcessMemory", [
    wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t)], wintypes.BOOL)
WriteProcessMemory = proto(KERNEL32, "WriteProcessMemory", [
    wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t)], wintypes.BOOL)
VirtualProtectEx = proto(KERNEL32, "VirtualProtectEx", [
    wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD)], wintypes.BOOL)
VirtualQueryEx = proto(KERNEL32, "VirtualQueryEx", [
    wintypes.HANDLE, ctypes.c_void_p, ctypes.POINTER(MEMORY_BASIC_INFORMATION),
    ctypes.c_size_t], ctypes.c_size_t)
FlushInstructionCache = proto(KERNEL32, "FlushInstructionCache", [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t], wintypes.BOOL)
GetThreadContext = proto(KERNEL32, "GetThreadContext", [wintypes.HANDLE, ctypes.c_void_p], wintypes.BOOL)
SetThreadContext = proto(KERNEL32, "SetThreadContext", [wintypes.HANDLE, ctypes.c_void_p], wintypes.BOOL)
OpenThread = proto(KERNEL32, "OpenThread", [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD], wintypes.HANDLE)
CloseHandle = proto(KERNEL32, "CloseHandle", [wintypes.HANDLE], wintypes.BOOL)
TerminateProcess = proto(KERNEL32, "TerminateProcess", [wintypes.HANDLE, wintypes.UINT], wintypes.BOOL)
QueryFullProcessImageNameW = proto(KERNEL32, "QueryFullProcessImageNameW", [
    wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)], wintypes.BOOL)
GetFinalPathNameByHandleW = proto(KERNEL32, "GetFinalPathNameByHandleW", [
    wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD], wintypes.DWORD)
IsWow64Process2 = getattr(KERNEL32, "IsWow64Process2", None)
if IsWow64Process2:
    IsWow64Process2.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.USHORT), ctypes.POINTER(wintypes.USHORT)]
    IsWow64Process2.restype = wintypes.BOOL
NtQueryInformationProcess = proto(NTDLL, "NtQueryInformationProcess", [
    wintypes.HANDLE, wintypes.ULONG, ctypes.c_void_p, wintypes.ULONG,
    ctypes.POINTER(wintypes.ULONG)], ctypes.c_long)


def now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="microseconds")


def hex_addr(v: int | None) -> str | None:
    return None if v is None else f"0x{v:x}"


def read_mem(handle, addr: int, size: int) -> bytes:
    if not addr or size <= 0:
        raise RuntimeError("invalid memory read address/size")
    buf = (ctypes.c_ubyte * size)()
    got = ctypes.c_size_t()
    if not ReadProcessMemory(handle, ctypes.c_void_p(addr), ctypes.byref(buf), size, ctypes.byref(got)):
        raise ctypes.WinError(ctypes.get_last_error())
    if got.value != size:
        raise RuntimeError(f"short ReadProcessMemory: {got.value}/{size}")
    return bytes(buf)


def write_mem(handle, addr: int, data: bytes) -> None:
    buf = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    got = ctypes.c_size_t()
    if not WriteProcessMemory(handle, ctypes.c_void_p(addr), ctypes.byref(buf), len(data), ctypes.byref(got)) or got.value != len(data):
        raise ctypes.WinError(ctypes.get_last_error())
    if not FlushInstructionCache(handle, ctypes.c_void_p(addr), len(data)):
        raise ctypes.WinError(ctypes.get_last_error())


def readable(handle, addr: int, size: int) -> bool:
    end = addr + size
    cur = addr
    while cur < end:
        mbi = MEMORY_BASIC_INFORMATION()
        if not VirtualQueryEx(handle, ctypes.c_void_p(cur), ctypes.byref(mbi), ctypes.sizeof(mbi)):
            return False
        base = int(mbi.BaseAddress or 0)
        region_end = base + int(mbi.RegionSize)
        if mbi.State != MEM_COMMIT or mbi.Protect & (PAGE_NOACCESS | PAGE_GUARD) or region_end <= cur:
            return False
        cur = min(region_end, end)
    return True


def read_u64(handle, addr: int) -> int:
    return struct.unpack("<Q", read_mem(handle, addr, 8))[0]


def read_u32(handle, addr: int) -> int:
    return struct.unpack("<I", read_mem(handle, addr, 4))[0]


def target_bitness(handle) -> int:
    if IsWow64Process2:
        pm = wintypes.USHORT()
        nm = wintypes.USHORT()
        if IsWow64Process2(handle, ctypes.byref(pm), ctypes.byref(nm)):
            if pm.value == IMAGE_FILE_MACHINE_I386:
                return 32
            if nm.value == IMAGE_FILE_MACHINE_AMD64:
                return 64
    return 64


def query_path(handle) -> str | None:
    n = wintypes.DWORD(32768)
    buf = ctypes.create_unicode_buffer(n.value)
    if QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(n)):
        return buf.value
    return None


def query_parent_and_commandline(handle) -> tuple[int | None, str | None]:
    pbi = PROCESS_BASIC_INFORMATION()
    ret_len = wintypes.ULONG()
    status = NtQueryInformationProcess(handle, 0, ctypes.byref(pbi), ctypes.sizeof(pbi), ctypes.byref(ret_len))
    if status < 0 or not pbi.PebBaseAddress:
        return None, None
    parent = int(pbi.InheritedFromUniqueProcessId or 0) or None
    bitness = target_bitness(handle)
    peb_off = 0x10 if bitness == 32 else 0x20
    cmd_off = 0x40 if bitness == 32 else 0x70
    ptr_size = 4 if bitness == 32 else 8
    try:
        params = int.from_bytes(read_mem(handle, int(pbi.PebBaseAddress) + peb_off, ptr_size), "little")
        if not params:
            return parent, None
        us = read_mem(handle, params + cmd_off, 8 if bitness == 32 else 16)
        length = struct.unpack_from("<H", us, 0)[0]
        buf_ptr = int.from_bytes(us[4:8] if bitness == 32 else us[8:16], "little")
        if not buf_ptr or length == 0 or length > 32766:
            return parent, None
        raw = read_mem(handle, buf_ptr, length)
        return parent, raw.decode("utf-16le", "replace")
    except Exception:
        return parent, None


def handle_path(h) -> str | None:
    if not h:
        return None
    buf = ctypes.create_unicode_buffer(32768)
    n = GetFinalPathNameByHandleW(h, buf, len(buf), 0)
    return buf.value if n and n < len(buf) else None


def sha256_file(path: str | Path) -> str | None:
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def pe_machine(path: str | Path) -> int | None:
    try:
        d = Path(path).read_bytes()
        pe = struct.unpack_from("<I", d, 0x3C)[0]
        return struct.unpack_from("<H", d, pe + 4)[0]
    except Exception:
        return None


def rva_to_raw(path: Path, rva: int) -> int:
    d = path.read_bytes()
    pe = struct.unpack_from("<I", d, 0x3C)[0]
    n = struct.unpack_from("<H", d, pe + 6)[0]
    magic = struct.unpack_from("<H", d, pe + 24)[0]
    sec = pe + 24 + (240 if magic == 0x20B else 224)
    for i in range(n):
        o = sec + 40 * i
        va, vs, rs, ptr = struct.unpack_from("<IIII", d, o + 8)
        if va <= rva < va + max(vs, rs):
            return ptr + rva - va
    raise ValueError(f"RVA not in section: 0x{rva:x}")


def file_rva_bytes(path: Path, rva: int, size: int) -> bytes:
    d = path.read_bytes()
    off = rva_to_raw(path, rva)
    return d[off:off + size]


def context_for_thread(tid: int):
    h = OpenThread(THREAD_GET_CONTEXT | THREAD_SET_CONTEXT | THREAD_QUERY_INFORMATION, False, tid)
    if not h:
        raise ctypes.WinError(ctypes.get_last_error())
    buf = (ctypes.c_ubyte * CONTEXT_SIZE)()
    struct.pack_into("<I", buf, CONTEXT_FLAGS_OFFSET, CONTEXT_FULL)
    if not GetThreadContext(h, ctypes.byref(buf)):
        err = ctypes.WinError(ctypes.get_last_error())
        CloseHandle(h)
        raise err
    return h, buf


def set_context(h, buf) -> None:
    if not SetThreadContext(h, ctypes.byref(buf)):
        raise ctypes.WinError(ctypes.get_last_error())


def tvalue(handle, addr: int, max_prefix: int = 35) -> dict:
    raw = read_mem(handle, addr, 16)
    value = struct.unpack_from("<Q", raw, 0)[0]
    tag_full = struct.unpack_from("<I", raw, 8)[0]
    tag = tag_full & 0x0F
    out = {"tag": tag_full, "type": {
        0: "nil", 1: "boolean", 2: "lightuserdata", 3: "number", 4: "string",
        5: "table", 6: "function", 7: "userdata", 8: "thread",
    }.get(tag, f"tag-{tag}")}
    if tag == 0:
        out["truthy"] = False
    elif tag == 1:
        out["boolean"] = bool(value)
        out["truthy"] = bool(value)
    else:
        out["truthy"] = True
    if tag == 4 and value:
        length = read_u64(handle, value + 0x10)
        out["string_length"] = int(length)
        n = min(int(length), max_prefix)
        out["prefix_hex"] = read_mem(handle, value + 0x20, n).hex() if n else ""
    elif tag_full == 0x13:
        out["integer"] = struct.unpack("<q", raw[:8])[0]
    elif tag == 3:
        out["number"] = struct.unpack("<d", raw[:8])[0]
    return out


def decode_root_instruction(word: int) -> tuple[int, int, int, int]:
    return word & 0x3F, (word >> 6) & 0xFF, (word >> 23) & 0x1FF, (word >> 14) & 0x1FF


def main() -> int:
    started = now()
    result = {
        "status": "not_started", "started_at": started, "ended_at": None,
        "target": str(TARGET), "working_directory": str(TARGET.parent),
        "command": f'"{TARGET}"', "timeout_seconds": TIMEOUT_SECONDS,
        "max_vm_hits": MAX_VM_HITS, "root_pid": None, "root_exit_code": None,
        "root_exit_time": None, "processes": [], "lua_module": None,
        "vm_validation": {}, "observations": {}, "exceptions": [],
        "termination": None, "notes": [
            "Runtime INT3 breakpoints and single-step temporarily alter timing and memory in the debugged modifier chain.",
            "The observation does not attach to or operate the game process; startup side effects before the stop cannot be ruled out.",
        ],
    }
    if not TARGET.is_file():
        result["status"] = "preflight_failed"
        result["error"] = "workspace target copy is missing"
        return finish(result, 1)
    if sha256_file(TARGET) != "cea1493191bbd5513f556413d167e2fad81879e91294dff7c5cdca61497cc9ef":
        result["status"] = "preflight_failed"
        result["error"] = "workspace target copy hash mismatch"
        return finish(result, 1)

    command = f'"{TARGET}"'
    cmd_buf = ctypes.create_unicode_buffer(command)
    si = STARTUPINFO()
    si.cb = ctypes.sizeof(si)
    pi = PROCESS_INFORMATION()
    if not CreateProcessW(None, cmd_buf, None, None, False, DEBUG_PROCESS, None,
                          str(TARGET.parent), ctypes.byref(si), ctypes.byref(pi)):
        result["status"] = "create_failed"
        result["error"] = str(ctypes.WinError(ctypes.get_last_error()))
        return finish(result, 1)

    root_pid = int(pi.dwProcessId)
    result["root_pid"] = root_pid
    handles: dict[int, object] = {root_pid: pi.hProcess}
    processes: dict[int, dict] = {}
    active: set[int] = set()
    breakpoints: dict[int, dict] = {}
    pending_steps: dict[int, dict] = {}
    lua_pid: int | None = None
    lua_handle = None
    lua_base: int | None = None
    root_info: dict | None = None
    pending_branch: dict | None = None
    vm_hits = 0
    deadline = time.monotonic() + TIMEOUT_SECONDS
    stop_requested = False
    stop_reason: str | None = None
    natural_root_exit = False

    def record_process(pid: int, event_info=None):
        ph = handles.get(pid)
        path = query_path(ph) if ph else None
        parent, commandline = query_parent_and_commandline(ph) if ph else (None, None)
        if pid == root_pid:
            path = str(TARGET)
            commandline = command
        item = {
            "pid": pid, "parent_pid": parent, "path": path,
            "command_line": commandline, "created_at": now(),
            "exit_time": None, "exit_code": None,
        }
        processes[pid] = item
        active.add(pid)

    def stop_chain(reason: str):
        nonlocal stop_requested, stop_reason
        if stop_requested:
            return
        stop_requested = True
        stop_reason = reason
        result["termination"] = {"kind": "diagnostic_active_stop", "reason": reason, "time": now()}
        for h in list(handles.values()):
            try:
                TerminateProcess(h, 0xC0DE)
            except Exception:
                pass

    def install(addr: int, name: str):
        if lua_handle is None:
            raise RuntimeError("no Lua process handle")
        original = read_mem(lua_handle, addr, 1)[0]
        write_mem(lua_handle, addr, b"\xCC")
        breakpoints[addr] = {"name": name, "original": original}

    def restore(addr: int):
        bp = breakpoints.get(addr)
        if bp and lua_handle is not None:
            write_mem(lua_handle, addr, bytes([bp["original"]]))

    def reinsert(addr: int):
        if lua_handle is not None:
            write_mem(lua_handle, addr, b"\xCC")

    def validate_and_setup(pid: int, handle, base: int, path: str | None):
        nonlocal lua_pid, lua_handle, lua_base
        if lua_pid is not None:
            return
        if not path or Path(path).name.lower() != "lua53-64.dll":
            return
        disk_hash = sha256_file(path)
        machine = pe_machine(path)
        record = {"pid": pid, "path": path, "sha256": disk_hash, "machine": hex(machine or 0),
                  "image_base": hex_addr(base), "expected_sha256": EXPECTED_LUA_SHA256}
        result["lua_module"] = record
        if disk_hash != EXPECTED_LUA_SHA256 or machine != IMAGE_FILE_MACHINE_AMD64:
            raise RuntimeError(f"verified Lua DLL mismatch: hash={disk_hash} machine={hex(machine or 0)}")
        vm_rva = 0xBE876
        vm_expected = file_rva_bytes(EXPECTED_DLL_FILE, vm_rva, 16)
        runtime = read_mem(handle, base + vm_rva, len(vm_expected))
        if runtime != vm_expected:
            raise RuntimeError("VM loop signature mismatch in loaded Lua image")
        for rva, size, label in [(0xC1228, 2, "eq_compare"), (0xC16B7, 2, "test_compare")]:
            expected = file_rva_bytes(EXPECTED_DLL_FILE, rva, size)
            if read_mem(handle, base + rva, size) != expected:
                raise RuntimeError(f"{label} signature mismatch in loaded Lua image")
        lua_pid, lua_handle, lua_base = pid, handle, base
        install(base + vm_rva, "vm_loop")
        install(base + 0xC1228, "eq_compare")
        install(base + 0xC16B7, "test_compare")
        result["vm_validation"]["loaded_image_signatures"] = "confirmed"

    def current_vm_state(handle, thread_buf):
        rbp = struct.unpack_from("<Q", thread_buf, CONTEXT_RBP_OFFSET)[0]
        L = read_u64(handle, rbp + 0x1CB0)
        ci = read_u64(handle, L + 0x20)
        func_tv = read_u64(handle, ci + 0x00)
        func_obj = read_u64(handle, func_tv + 0x00)
        proto = read_u64(handle, func_obj + 0x18)
        code = read_u64(handle, proto + 0x38)
        savedpc = read_u64(handle, ci + 0x28)
        base = read_u64(handle, ci + 0x20)
        if not code or not savedpc or savedpc % 4:
            raise RuntimeError("invalid Proto+0x38 code pointer or savedpc alignment")
        if not readable(handle, code + ROOT_SIGNATURE_PC * 4, len(ROOT_SIGNATURE) * 4):
            raise RuntimeError("Proto+0x38 code signature range is unreadable")
        sig = struct.unpack("<8I", read_mem(handle, code + ROOT_SIGNATURE_PC * 4, 32))
        return {"rbp": rbp, "L": L, "ci": ci, "func_tv": func_tv, "func_obj": func_obj,
                "proto": proto, "code": code, "savedpc": savedpc, "base": base,
                "signature": sig}

    def root_state(handle, thread_buf):
        nonlocal root_info
        s = current_vm_state(handle, thread_buf)
        if tuple(s["signature"]) != ROOT_SIGNATURE:
            return None, s
        code = s["code"]
        if not (code <= s["savedpc"] < code + EXPECTED_ROOT_SIZECODE * 4):
            raise RuntimeError("root savedpc outside validated function range")
        pc = (s["savedpc"] - code) // 4
        if pc < 0 or pc >= EXPECTED_ROOT_SIZECODE:
            raise RuntimeError("root pc outside sizecode")
        word = read_u32(handle, s["savedpc"])
        if pc in ROOT_WORDS and word != ROOT_WORDS[pc]:
            raise RuntimeError(f"root instruction signature mismatch at pc{pc}")
        if root_info is None:
            root_info = {"code": code, "proto": s["proto"], "first_seen": now()}
            result["vm_validation"].update({
                "proto_code_pointer": hex_addr(code), "proto": hex_addr(s["proto"]),
                "savedpc_alignment": True, "root_function_range": [0, EXPECTED_ROOT_SIZECODE],
                "root_signature": True,
            })
        elif code != root_info["code"]:
            raise RuntimeError("root Proto/code pointer changed unexpectedly")
        return pc, s

    def log_value_at(s, reg: int, label: str):
        addr = s["base"] + reg * 0x10
        v = tvalue(lua_handle, addr)
        result["observations"][label] = {"register": reg, "tvalue_address": hex_addr(addr), **v}
        return v

    try:
        while True:
            if time.monotonic() >= deadline:
                stop_chain("fixed timeout reached")
                break
            ev = DEBUG_EVENT()
            if not WaitForDebugEvent(ctypes.byref(ev), 100):
                if ctypes.get_last_error() == ERROR_SEM_TIMEOUT:
                    continue
                raise ctypes.WinError(ctypes.get_last_error())
            code = int(ev.dwDebugEventCode)
            pid = int(ev.dwProcessId)
            tid = int(ev.dwThreadId)
            status = DBG_CONTINUE
            if code == CREATE_PROCESS_DEBUG_EVENT:
                info = ev.u.CreateProcessInfo
                if pid not in handles and info.hProcess:
                    handles[pid] = info.hProcess
                if pid not in processes:
                    record_process(pid, info)
                if info.hFile:
                    CloseHandle(info.hFile)
            elif code == LOAD_DLL_DEBUG_EVENT:
                info = ev.u.LoadDll
                path = handle_path(info.hFile)
                if not path and info.lpImageName and pid in handles:
                    try:
                        path = read_mem(handles[pid], int(info.lpImageName), 1024).split(b"\0", 1)[0].decode("utf-16le" if info.fUnicode else "ascii", "ignore")
                    except Exception:
                        path = None
                if path and Path(path).name.lower() == "lua53-64.dll":
                    try:
                        validate_and_setup(pid, handles[pid], int(info.lpBaseOfDll or 0), path)
                    except Exception as e:
                        result["vm_validation"]["error"] = str(e)
                        stop_chain("Lua DLL/runtime validation failed")
                if info.hFile:
                    CloseHandle(info.hFile)
            elif code == EXIT_PROCESS_DEBUG_EVENT:
                exit_code = int(ev.u.ExitProcess.dwExitCode)
                item = processes.get(pid)
                if item:
                    item["exit_time"] = now()
                    item["exit_code"] = exit_code
                active.discard(pid)
                if pid == root_pid:
                    result["root_exit_time"] = item["exit_time"] if item else now()
                    result["root_exit_code"] = exit_code
                    natural_root_exit = not stop_requested
            elif code == EXCEPTION_DEBUG_EVENT:
                exc = ev.u.Exception.ExceptionRecord
                exc_code = int(exc.ExceptionCode)
                exc_addr = int(exc.ExceptionAddress or 0)
                first = bool(ev.u.Exception.dwFirstChance)
                if exc_code == STATUS_BREAKPOINT and lua_pid == pid and lua_base is not None:
                    haddr = exc_addr
                    # Windows reports RIP one byte after an INT3; inspect it.
                    th, ctx = context_for_thread(tid)
                    rip = struct.unpack_from("<Q", ctx, CONTEXT_RIP_OFFSET)[0]
                    addr = next((a for a in breakpoints if rip in (a, a + 1) or haddr in (a, a + 1)), None)
                    if addr is not None:
                        restore(addr)
                        struct.pack_into("<Q", ctx, CONTEXT_RIP_OFFSET, addr)
                        eflags = struct.unpack_from("<I", ctx, CONTEXT_EFLAGS_OFFSET)[0] | 0x100
                        struct.pack_into("<I", ctx, CONTEXT_EFLAGS_OFFSET, eflags)
                        set_context(th, ctx)
                        pending_steps[tid] = {"addr": addr, "thread": th}
                        bp_name = breakpoints[addr]["name"]
                        if bp_name == "vm_loop":
                            vm_hits += 1
                            if vm_hits > MAX_VM_HITS:
                                stop_chain("VM breakpoint hit cap reached")
                            else:
                                try:
                                    pc, s = root_state(handles[pid], ctx)
                                    if pc is not None:
                                        if pending_branch is not None:
                                            pending_branch["actual_target_pc"] = pc
                                            pending_branch["target_time"] = now()
                                            pending_branch = None
                                        if pc == 137 and "getURL_return" not in result["observations"]:
                                            log_value_at(s, 22, "getURL_return")
                                        if pc == 153 and "smdx_260726" not in result["observations"]:
                                            log_value_at(s, 24, "smdx_260726")
                                        if pc == 154 and "first_eq" not in result["observations"]:
                                            b = log_value_at(s, 23, "first_eq_left")
                                            c = log_value_at(s, 24, "first_eq_right")
                                            result["observations"]["first_eq"] = {
                                                "pc": 154, "operands": ["R23", "R24"],
                                                "left": b, "right": c,
                                                "instruction": decode_root_instruction(ROOT_WORDS[154]),
                                            }
                                            pending_branch = {"kind": "EQ", "pc": 154}
                                        if pc == 172 and "getAccountHandle" not in result["observations"]:
                                            v = log_value_at(s, 24, "getAccountHandle")
                                            result["observations"]["getAccountHandle"]["pc"] = 172
                                            pending_branch = {"kind": "TEST", "pc": 172}
                                        if pc in (156, 174, 179):
                                            stop_chain(f"confirmed root exit/continuation boundary pc{pc}")
                                except Exception as e:
                                    result["vm_validation"]["error"] = str(e)
                                    stop_chain("runtime VM layout validation failed")
                        elif bp_name == "eq_compare" and pending_branch and pending_branch.get("kind") == "EQ":
                            eax = struct.unpack_from("<I", ctx, CONTEXT_RAX_OFFSET)[0]
                            ecx = struct.unpack_from("<I", ctx, CONTEXT_RCX_OFFSET)[0]
                            eflags = struct.unpack_from("<I", ctx, CONTEXT_EFLAGS_OFFSET)[0]
                            result["observations"]["first_eq"].update({
                                "native_eax": eax, "native_a": ecx, "native_equal": eax == ecx,
                                "native_cmp_zf": bool(eflags & 0x40),
                            })
                        elif bp_name == "test_compare" and pending_branch and pending_branch.get("kind") == "TEST":
                            # The handler has just set [rbp+0x1c78] and flags are from CMP.
                            rbp = struct.unpack_from("<Q", ctx, CONTEXT_RBP_OFFSET)[0]
                            internal = read_u32(handles[pid], rbp + 0x1C78)
                            eflags = struct.unpack_from("<I", ctx, CONTEXT_EFLAGS_OFFSET)[0]
                            result["observations"]["getAccountHandle"].update({
                                "native_truth_value": internal, "native_test_zf": bool(eflags & 0x40),
                            })
                    else:
                        status = DBG_CONTINUE
                        CloseHandle(th)
                elif exc_code == STATUS_SINGLE_STEP and tid in pending_steps:
                    step = pending_steps.pop(tid)
                    addr = step["addr"]
                    # Reinstall the breakpoint after executing its original instruction.
                    reinsert(addr)
                    th = step["thread"]
                    ctx = (ctypes.c_ubyte * CONTEXT_SIZE)()
                    struct.pack_into("<I", ctx, CONTEXT_FLAGS_OFFSET, CONTEXT_FULL)
                    if GetThreadContext(th, ctypes.byref(ctx)):
                        eflags = struct.unpack_from("<I", ctx, CONTEXT_EFLAGS_OFFSET)[0] & ~0x100
                        struct.pack_into("<I", ctx, CONTEXT_EFLAGS_OFFSET, eflags)
                        set_context(th, ctx)
                    CloseHandle(th)
                elif exc_code == STATUS_BREAKPOINT and first:
                    # Loader/debugger first-chance breakpoints are not target
                    # faults and must be continued without treating them as
                    # an exception in the modifier.
                    result.setdefault("initial_breakpoints", 0)
                    result["initial_breakpoints"] += 1
                    status = DBG_CONTINUE
                else:
                    rec = {"pid": pid, "tid": tid, "code": hex(exc_code),
                           "first_chance": first, "address": hex_addr(exc_addr), "time": now()}
                    result["exceptions"].append(rec)
                    if not first:
                        stop_chain("unhandled debug exception")
                    else:
                        status = DBG_EXCEPTION_NOT_HANDLED
            elif code == RIP_EVENT:
                result["exceptions"].append({"pid": pid, "tid": tid, "code": "RIP_EVENT", "time": now()})
                stop_chain("RIP debug event")

            if not ContinueDebugEvent(ev.dwProcessId, ev.dwThreadId, status):
                raise ctypes.WinError(ctypes.get_last_error())
            if pid == root_pid and code == EXIT_PROCESS_DEBUG_EVENT and not active:
                break
            if stop_requested and not active:
                break
    except Exception as e:
        result["status"] = "debugger_error"
        result["error"] = str(e)
        stop_chain("debugger error")
    finally:
        for pid, item in processes.items():
            if pid in handles and handles[pid] and pid != root_pid:
                try:
                    CloseHandle(handles[pid])
                except Exception:
                    pass
        try:
            CloseHandle(pi.hThread)
        except Exception:
            pass
        try:
            CloseHandle(pi.hProcess)
        except Exception:
            pass
        result["ended_at"] = now()
        result["vm_hits"] = vm_hits
        result["processes"] = list(processes.values())
        result["status"] = "diagnostic_active_stop" if stop_requested else ("natural_exit" if natural_root_exit else "completed")
        result["stop_reason"] = stop_reason
    return finish(result, 0 if result["status"] in ("diagnostic_active_stop", "natural_exit", "completed") else 1)


def finish(result: dict, code: int) -> int:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
