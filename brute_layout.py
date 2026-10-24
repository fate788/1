from pathlib import Path
import struct
for p in sorted(Path(r'C:\Users\13162\Documents\Codex\2026-10-18\di\work\archive-history/luac').glob('*.luac')):
 b=p.read_bytes(); best=[]
 for start in range(41,200):
  body=b[start:]
  try:
   nups=body[0]; ssize=body[1]
   if ssize==255 or ssize>100: continue
   pos=2+max(0,ssize-1)+8+3
   if pos+4>len(body): continue
   code=struct.unpack_from('<I',body,pos)[0]
   score=0
   if nups<=32: score+=1
   if ssize<=32: score+=1
   if code<=100000 and code*4<=len(body)-pos: score+=3
   if body[pos+4:pos+8] and all(x<4 for x in body[pos+4:pos+8]): score+=1
   if score>=3: best.append((score,start,nups,ssize,code,len(body)-pos))
  except: pass
 print(p.name,'plausible_offsets',best[:20])
