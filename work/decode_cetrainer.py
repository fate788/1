import pathlib,zlib,hashlib,struct,xml.etree.ElementTree as ET
base=pathlib.Path(r'C:\Users\13162\Documents\Codex\2026-10-18\di\work\archive-history\extracted')
out=pathlib.Path(r'C:\Users\13162\Documents\Codex\2026-10-18\di\work\archive-history\decoded'); out.mkdir(exist_ok=True)
for ad in sorted(base.glob('ARCHIVE-*')):
 p=ad/'CET_TRAINER.CETRAINER'; raw=p.read_bytes(); data=bytearray(raw)
 v=1
 while v < len(data)-1:
  v+=1; data[v] ^= data[v-2]
 v=len(data)-1
 while v>0:
  v-=1; data[v] ^= data[v+1]
 key=0xcd
 for i in range(len(data)): data[i]^=key; key=(key+2)&0xff
 print('\n',ad.name,'magic',data[:16])
 if bytes(data[:7])!=b'BRICKES': print('MAGIC FAIL'); continue
 dec=None
 for w in (-15,15):
  try:
   d=zlib.decompressobj(w); temp=d.decompress(bytes(data[7:])); temp+=d.flush(); dec=temp; print('decomp w',w,'len',len(dec),'unused',len(d.unused_data)); break
  except Exception as e: print('decomp fail',w,e)
 if dec is None: continue
 od=out/ad.name; od.mkdir(exist_ok=True); (od/'CET_TRAINER.CETRAINER.dec').write_bytes(data); (od/'CET_TRAINER.CETRAINER.xml').write_bytes(dec)
 print('xml head',dec[:200])
 try:
  root=ET.fromstring(dec); print('root',root.tag,'attrs',root.attrib)
  vals=[]
  for el in root.iter():
   txt=''.join(el.itertext()).strip()
   if txt: vals.append((el.tag,el.attrib,txt,len(txt)))
  print('elements',len(vals))
  for tag,attrs,txt,l in vals:
   low=txt.lower()
   if any(k in low for k in ['version','starcraft','sc2','7897','process','address','error','lua','http','https','socket','min=','client=']):
    print('MATCH',tag,attrs,'len',l,'text',repr(txt[:800]))
 except Exception as e: print('xml parse fail',e)
