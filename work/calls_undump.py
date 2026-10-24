from pathlib import Path
import struct
b=Path(r'C:\Users\13162\Documents\Codex\2026-10-18\di\work\archive-history/finalized/ARCHIVE-260804/lua53-64.dll').read_bytes(); raw=0x400;text=0x6b000
for r in range(0xbc220,0xbc3a0):
 o=raw+(r-text)
 if b[o]==0xe8:
  rel=struct.unpack_from('<i',b,o+1)[0];t=r+5+rel; print(hex(r),'->',hex(t))
