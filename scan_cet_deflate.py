import pathlib,zlib
for p in sorted(pathlib.Path(r'C:\Users\13162\Documents\Codex\2026-10-18\di\work\archive-history\extracted').glob('ARCHIVE-*/CET_TRAINER.CETRAINER')):
 b=p.read_bytes(); rows=[]
 for i in range(len(b)):
  for w in (-15,15):
   try:
    d=zlib.decompressobj(w); out=d.decompress(b[i:]); out+=d.flush()
    if len(out)>=64 and (len(d.unused_data)>0 or i+len(out)<len(b)):
     score=sum(out.count(x) for x in [b'<?xml',b'CheatTable',b'BRICKES',b'Lua',b'StarCraft',b'SC2'])
     rows.append((score,i,w,len(out),len(d.unused_data),out[:32]))
   except: pass
 print('\n',p.parent.name,'valid',len(rows))
 for row in sorted(rows,reverse=True)[:30]:
  score,i,w,n,u,h=row; print('score',score,'off',i,'w',w,'len',n,'unused',u,'head',h.hex(),''.join(chr(x) if 32<=x<127 else '.' for x in h))
