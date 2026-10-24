import pathlib, struct, hashlib, json
base=pathlib.Path(r'C:\Users\13162\Documents\Codex\2026-10-18\di\work\archive-history')
for p in sorted(base.glob('*.raw')):
 b=p.read_bytes(); print('\n'+p.name)
 for start in range(4,16):
  try:
   pos=start; fc=struct.unpack_from('<I',b,0)[0]; rec=[]
   for n in range(fc):
    nl=struct.unpack_from('<I',b,pos)[0]; pos+=4
    name=b[pos:pos+nl].decode('latin1'); pos+=nl
    fl=struct.unpack_from('<I',b,pos)[0]; pos+=4
    folder=b[pos:pos+fl].decode('latin1'); pos+=fl
    sz=struct.unpack_from('<I',b,pos)[0]; pos+=4
    dat=b[pos:pos+sz]; pos+=sz
    if len(dat)!=sz: raise ValueError('short')
    rec.append((name,folder,sz,pos,hashlib.sha256(dat).hexdigest(),dat[:16]))
   if pos<=len(b) and len(rec)==fc:
    print('start',start,'end',pos,'remain',len(b)-pos)
    for x in rec: print(x[:5],x[5].hex())
  except Exception: pass
