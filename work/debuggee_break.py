import ctypes
import time


kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.DebugBreak.restype = None
kernel32.OutputDebugStringA.argtypes = [ctypes.c_char_p]
kernel32.OutputDebugStringA.restype = None
kernel32.OutputDebugStringW.argtypes = [ctypes.c_wchar_p]
kernel32.OutputDebugStringW.restype = None

# Give the debugger time to receive the process-create event before the
# intentional first-chance breakpoint.
time.sleep(0.25)
memory_sentinel = ctypes.create_string_buffer(b"CODEX_MEMORY_SENTINEL")
address_message = f"CODEX_MEM_ADDR=0x{ctypes.addressof(memory_sentinel):x}".encode("ascii")
kernel32.OutputDebugStringA(address_message)
kernel32.OutputDebugStringW("CODEX_DEBUG_SELFTEST_BREAK")
kernel32.DebugBreak()
print("debuggee-after-break", flush=True)
time.sleep(0.25)
