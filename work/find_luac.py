from pathlib import Path
for p in sorted(Path(r'C:\Users\13162\Documents\Codex\2026-10-18\di\work\archive-history\luac').glob('*.luac')):
 b=p.read_bytes(); print(p.name)
 for needle in [b'StarCraft',b'SC2',b'7897',b'http',b'https',b'version',b'client',b'process',b'error',b'Addresses',b'Memory',b'lua53',b'5.0',b'Base98370',b'openProcess']:
  i=b.lower().find(needle.lower())
  if i>=0: print(needle,i,b[i-80:i+200])
