from pathlib import Path
b=Path(r'C:\Users\13162\Documents\Codex\2026-10-18\di\work\archive-history/finalized/ARCHIVE-260804/lua53-64.dll').read_bytes(); raw=0x400;text=0x6b000
for r in range(0xbbd00,0xbbde5):
 o=raw+(r-text); print(f'{r:08x} {b[o]:02x}')
