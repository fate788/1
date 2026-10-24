from pathlib import Path
from collections import Counter
ps=sorted(Path(r'C:\Users\13162\Documents\Codex\2026-10-18\di\work\archive-history/luac').glob('*.luac')); bs=[p.read_bytes() for p in ps]
print('lengths',[len(b) for b in bs])
# same bytes positions across all up to min
m=min(map(len,bs)); same=[i for i in range(m) if bs[0][i]==bs[1][i]==bs[2][i]]
runs=[]; s=None; prev=None
for i in same:
 if s is None: s=prev=i
 elif i==prev+1: prev=i
 else: runs.append((s,prev)); s=prev=i
if s is not None:runs.append((s,prev))
print('common runs first 30',runs[:30])
for a,b in runs[:20]: print(a,b,b-a+1,bs[0][a:b+1].hex(' '))
# stable body positions first 300
print('common body count',sum(1 for i in range(41,m) if bs[0][i]==bs[1][i]==bs[2][i]),'of',m-41)
