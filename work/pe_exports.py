from pathlib import Path
import struct,json,hashlib
p=Path(r'C:\Users\13162\Documents\Codex\2026-10-18\di\work\archive-history/finalized/ARCHIVE-260804/lua53-64.dll'); b=p.read_bytes()
def u16(o): return struct.unpack_from('<H',b,o)[0]
def u32(o): return struct.unpack_from('<I',b,o)[0]
def rvaoff(rva,secs):
 for va,vs,rawptr,rawsize,name in secs:
  if va<=rva<va+max(vs,rawsize): return rawptr+(rva-va)
 return None
e_lfanew=u32(0x3c); assert b[e_lfanew:e_lfanew+4]==b'PE\0\0'; fh=e_lfanew+4; machine=u16(fh); nsec=u16(fh+2); opt=fh+20; magic=u16(opt); optsize=u16(fh+16); dirbase=opt+(112 if magic==0x20b else 96); secs=[]
for i in range(nsec):
 o=opt+optsize+40*i; name=b[o:o+8].split(b'\0',1)[0].decode('latin1'); vs=u32(o+8); va=u32(o+12); rawsize=u32(o+16); rawptr=u32(o+20); secs.append((va,vs,rawptr,rawsize,name))
print('sha',hashlib.sha256(b).hexdigest(),'machine',hex(machine),'magic',hex(magic),'sections',[(x[4],hex(x[0]),x[1],hex(x[2]),x[3]) for x in secs])
def directory(i): return (u32(dirbase+8*i),u32(dirbase+8*i+4))
exp_rva,exp_sz=directory(0); print('export_dir',hex(exp_rva),exp_sz)
exp=rvaoff(exp_rva,secs); names=[]
if exp:
 flags,time,maj,minv,name_rva,base,func_count,name_count,func_rva,names_rva,ords_rva=struct.unpack_from('<IIHHIIIIIII',b,exp)
 print('export header',{'time':time,'base':base,'func_count':func_count,'name_count':name_count,'name':b[rvaoff(name_rva,secs):].split(b'\0',1)[0].decode('latin1') if rvaoff(name_rva,secs) else None})
 foff=rvaoff(func_rva,secs); noff=rvaoff(names_rva,secs); ooff=rvaoff(ords_rva,secs)
 for i in range(name_count):
  nrva=u32(b,noff+4*i) if False else struct.unpack_from('<I',b,noff+4*i)[0]; no=rvaoff(nrva,secs); nm=b[no:].split(b'\0',1)[0].decode('latin1')
  ordv=struct.unpack_from('<H',b,ooff+2*i)[0]; frva=struct.unpack_from('<I',b,foff+4*ordv)[0]; names.append((nm,base+ordv,frva))
 for row in names:
  if any(k in row[0].lower() for k in ['lua','load','dump','undump','chunk']): print('export',row)
# debug directory
for i in [6]:
 drva,dsz=directory(i); print('dir',i,hex(drva),dsz)
 do=rvaoff(drva,secs)
 if do:
  for j in range(dsz//28):
   q=do+28*j; typ=u32(q+12); size=u32(q+16); addr=u32(q+20); ptr=u32(q+24); print('debug',j,'type',typ,'size',size,'addr',hex(addr),'ptr',hex(ptr),b[ptr:ptr+4])
   if b[ptr:ptr+4]==b'RSDS': print('pdb',b[ptr+24:].split(b'\0',1)[0].decode('latin1'))
