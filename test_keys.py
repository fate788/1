import pathlib
for p in sorted(pathlib.Path(r'C:\Users\13162\Documents\Codex\2026-10-18\di\work\archive-history\extracted').glob('ARCHIVE-*/CET_TRAINER.CETRAINER')):
 raw=p.read_bytes(); print(p.parent.name)
 for key0 in [0xcd,0xce,0xcc,0xcf]:
  data=bytearray(raw); v=1
  while v<len(data)-1: v+=1; data[v]^=data[v-2]
  v=len(data)-1
  while v>0: v-=1; data[v]^=data[v+1]
  key=key0
  for i in range(len(data)): data[i]^=key; key=(key+2)&255
  print(hex(key0),data[:16].hex(),repr(bytes(data[:16])))
