from pathlib import Path
import hashlib, json
base=Path(r'C:\Users\13162\Documents\Codex\2026-10-18\di\work\archive-history')
for d in sorted((base/'extracted').glob('ARCHIVE-*')):
 print(d.name)
 for n in ['CET_TRAINER.CETRAINER','defines.lua','cheatengine-x86_64.exe','lua53-64.dll']:
  b=(d/n).read_bytes(); print(n,len(b),hashlib.sha256(b).hexdigest())
 for n in ['CET_TRAINER.CETRAINER.xml']:
  q=base/'decoded'/d.name/n; b=q.read_bytes(); print('decoded/'+n,len(b),hashlib.sha256(b).hexdigest())
 q=base/'luac'/(d.name+'.luac'); b=q.read_bytes(); print('luac',len(b),hashlib.sha256(b).hexdigest())
