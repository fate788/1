from pathlib import Path
import struct,re,bisect,json
p=Path(r'C:\Users\13162\Documents\Codex\2026-10-18\di\work\archive-history/finalized/ARCHIVE-260804/lua53-64.dll'); b=p.read_bytes(); text_rva=0x6b000;text_raw=0x400;text_size=921088;rdata_rva=0x14c000;rdata_raw=0xe1200
# function ranges from .pdata
pdata_rva=0x17f000;pdata_raw=0x111400;pdata_size=43224
ranges=[]
for o in range(pdata_raw,pdata_raw+pdata_size,12):
 begin,end,uw=struct.unpack_from('<III',b,o)
 if begin<end: ranges.append((begin,end,uw))
ranges.sort(); starts=[x[0] for x in ranges]
def func(rva):
 i=bisect.bisect_right(starts,rva)-1
 return ranges[i] if i>=0 and rva<ranges[i][1] else None
needles=[b'format mismatch in',b'LUA_DUMP_STRINGSIZE_FORMAT2',b'size mismatch in',b'corrupted',b'version mismatch in',b'float format mismatch in',b'endianness mismatch in',b'truncated',b'not a',b'precompiled chunk']
strs=[]
for n in needles:
 pos=0
 while True:
  i=b.find(n,pos)
  if i<0: break
  strs.append((rdata_rva+(i-rdata_raw),n.decode('latin1'),i)); pos=i+1
print('strings',[(hex(r),s) for r,s,_ in strs])
# patterns for RIP relative references
patterns=[0x48,0x4c,0x4c,0xc7,0x8d,0x8b,0x89]
hits=[]
for o in range(text_raw,text_raw+text_size-7):
 op=b[o:o+3]
 if op in (b'\x48\x8d\x0d',b'\x48\x8d\x15',b'\x48\x8d\x05',b'\x4c\x8d\x05',b'\x4c\x8d\x0d',b'\x48\x8b\x0d',b'\x48\x8b\x05',b'\x4c\x8b\x05',b'\x48\x89\x0d',b'\xc7\x05'):
  disp=struct.unpack_from('<i',b,o+3)[0]; ins_rva=text_rva+(o-text_raw); target=ins_rva+7+disp
  for sr,s,_ in strs:
   if sr<=target<sr+len(s)+1: hits.append((ins_rva,target,op.hex(),s,func(ins_rva)))
for h in hits:
 ins,target,op,s,f=h; print('hit',hex(ins),'target',hex(target),op,s,'func',tuple(hex(x) if i<2 else hex(x) for i,x in enumerate(f)) if f else None)
print('hit count',len(hits))
