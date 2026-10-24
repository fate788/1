from pathlib import Path
b=Path(r'C:\Users\13162\Documents\Codex\2026-10-18\di\work\archive-history/finalized/ARCHIVE-260804/lua53-64.dll').read_bytes(); raw=0x400;text=0x6b000
for r in [0xbc2e0,0xbc220,0xbc300,0xbc400,0xbc500]:
 o=raw+(r-text); print('\n',hex(r),b[o:o+220].hex(' '))
