from pathlib import Path
for p in sorted(Path(r'C:\Users\13162\Documents\Codex\2026-10-18\di\work\archive-history/luac').glob('*.luac')):
 b=p.read_bytes(); print('\n'+p.name)
 for off in [0,5,6,14,41,42,43,49,50,51,57]: print(off,b[off:off+64].hex(' '))
