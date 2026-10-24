from pathlib import Path
import zlib
for p in sorted(Path(r'C:\Users\13162\Documents\Codex\2026-10-18\di\work\archive-history/luac').glob('*.luac')):
 b=p.read_bytes(); hits=[]
 for off in range(41,len(b)):
  for w in (15,-15):
   try:
    d=zlib.decompressobj(w); o=d.decompress(b[off:]); o+=d.flush()
    if len(o)>1000: hits.append((off,w,len(o),len(d.unused_data),o[:8].hex()))
   except: pass
 print(p.name,'streams',hits[:20])
