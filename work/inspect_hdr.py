import pathlib, struct
for p in sorted(pathlib.Path(r'C:\Users\13162\Documents\Codex\2026-10-18\di\work\archive-history').glob('*.raw')):
 b=p.read_bytes()
 print(p.name)
 print(' '.join(f'{x:02x}' for x in b[:128]))
 print('ascii',''.join(chr(x) if 32<=x<127 else '.' for x in b[:128]))
 for s in [b'CET_TRAINER.CETRAINER',b'defines.lua',b'lua53-64.dll']:
  i=b.find(s)
  print(s,i, 'before',b[i-32:i].hex() if i>=32 else '')
