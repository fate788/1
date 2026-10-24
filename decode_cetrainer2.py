import pathlib,zlib,hashlib,struct,xml.etree.ElementTree as ET
base=pathlib.Path(r'C:\Users\13162\Documents\Codex\2026-10-18\di\work\archive-history\extracted')
out=pathlib.Path(r'C:\Users\13162\Documents\Codex\2026-10-18\di\work\archive-history\decoded'); out.mkdir(exist_ok=True)
for ad in sorted(base.glob('ARCHIVE-*')):
 p=ad/'CET_TRAINER.CETRAINER'; raw=p.read_bytes(); data=bytearray(raw)
 for i in range(2,len(data)): data[i]^=data[i-2]
 for i in range(len(data)-2,-1,-1): data[i]^=data[i+1]
 k=0xce
 for i in range(len(data)): data[i]^=k; k=(k+1)&255
 print('\n',ad.name,'rawsha',hashlib.sha256(raw).hexdigest(),'magic',bytes(data[:16]))
 if bytes(data[:5])!=b'CHEAT': print('MAGIC FAIL'); continue
 dec=None
 for w in (-15,15):
  try:
   d=zlib.decompressobj(w); temp=d.decompress(bytes(data[5:])); temp+=d.flush(); dec=temp; print('decomp w',w,'len',len(dec),'unused',len(d.unused_data)); break
  except Exception as e: print('decomp fail',w,e)
 if dec is None: continue
 declared=struct.unpack_from('<i',dec,0)[0] if len(dec)>=4 else None
 print('declared xml size',declared,'actual rest',len(dec)-4,'xmlhead',dec[4:120])
 xml=dec[4:4+declared] if declared is not None and declared>=0 else dec[4:]
 od=out/ad.name; od.mkdir(exist_ok=True); (od/'CET_TRAINER.CETRAINER.dec').write_bytes(data); (od/'CET_TRAINER.CETRAINER.xml').write_bytes(xml)
 try:
  root=ET.fromstring(xml); print('root',root.tag,'attrs',root.attrib)
  vals=[]
  for el in root.iter():
   txt=''.join(el.itertext()).strip()
   if txt: vals.append((el.tag,el.attrib,txt,len(txt)))
  print('elements',len(vals),'root children',[x.tag for x in root])
  for tag,attrs,txt,l in vals:
   low=txt.lower()
   if any(k in low for k in ['version','starcraft','sc2','7897','process','address','error','lua','http','https','socket','min=','client=','too old']):
    print('MATCH',tag,attrs,'len',l,'text',repr(txt[:1000]))
 except Exception as e: print('xml parse fail',e)
