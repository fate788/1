from pathlib import Path
import struct,bisect
b=Path(r'C:\Users\13162\Documents\Codex\2026-10-18\di\work\archive-history/finalized/ARCHIVE-260804/lua53-64.dll').read_bytes(); start=0xbbce0; end=0xbbeff; raw0=0x400;text_rva=0x6b000
for r in range(start,end-4):
 o=raw0+(r-text_rva)
 if b[o]==0xe8:
  rel=struct.unpack_from('<i',b,o+1)[0]; t=r+5+rel
  print(hex(r),'call',hex(t),'rel',hex(rel))
