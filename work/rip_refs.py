from pathlib import Path
import struct
b=Path(r'C:\Users\13162\Documents\Codex\2026-10-18\di\work\archive-history/finalized/ARCHIVE-260804/lua53-64.dll').read_bytes(); raw0=0x400;text=0x6b000
# rdata strings from known offsets
for r in range(0xbbce0,0xbbef0):
 o=raw0+(r-text)
 op=b[o:o+3]
 if op in (b'\x48\x8d\x05',b'\x48\x8d\x15',b'\x4c\x8d\x05',b'\x4c\x8d\x0d',b'\x48\x8d\x0d'):
  disp=struct.unpack_from('<i',b,o+3)[0]; t=r+7+disp
  if 0x14c000<=t<0x15c000:
   to=raw0+(t-rdata_rva) if False else None
   # map target to printable null string via file RVA to raw (rdata raw 0xe1200)
   off=0xe1200+(t-0x14c000); s=b[off:off+200].split(b'\0',1)[0]
   print(hex(r),op.hex(),hex(t),repr(s.decode('latin1')))
