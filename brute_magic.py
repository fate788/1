import pathlib
raw=next(pathlib.Path(r'C:\Users\13162\Documents\Codex\2026-10-18\di\work\archive-history\extracted').glob('ARCHIVE-260804/CET_TRAINER.CETRAINER')).read_bytes()
# preprocess first+second loops variants, then brute key sequence
for order in [0,1]:
 d=bytearray(raw)
 if order==0:
  i=1
  while i<len(d)-1: i+=1; d[i]^=d[i-2]
  i=len(d)-1
  while i>0: i-=1; d[i]^=d[i+1]
 else:
  i=len(d)-1
  while i>0: i-=1; d[i]^=d[i+1]
  i=1
  while i<len(d)-1: i+=1; d[i]^=d[i-2]
 found=[]
 for k0 in range(256):
  for step in range(256):
   x=bytes((d[i]^((k0+step*i)&255)) for i in range(7))
   if x in (b'BRICKES',b'<?xmlve',b'<?xml v',b'CHEAT',b'PK\x03\x04') or x[:4] in (b'BRIC',b'<?xm'):
    found.append((k0,step,x))
 print('order',order,'found',found[:20], 'count',len(found))
 # show likely key stepping 2 variants
