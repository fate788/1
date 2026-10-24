from pathlib import Path
b=Path(r'C:\Users\13162\Documents\Codex\2026-10-18\di\work\archive-history/finalized/ARCHIVE-260804/lua53-64.dll').read_bytes(); raw0=0x400;text=0x6b000
for r in [0xbb6c0,0xbb750,0xbbf90,0xbc090,0xbc140,0xbad10,0x6bad2]:
 o=raw0+(r-text); print('\n',hex(r),b[o:o+160].hex(' '))
