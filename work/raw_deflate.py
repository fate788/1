import pathlib,zlib,hashlib,struct
base=pathlib.Path(r'C:\Users\13162\Documents\Codex\2026-10-18\di\work\archive-history')
for p in sorted(base.glob('*.raw')):
 b=p.read_bytes(); print('\n',p.name)
 for off in range(0,20):
  for w in (-15,15,31):
   try:
    d=zlib.decompressobj(w); out=d.decompress(b[off:]); out+=d.flush()
    if len(out)>0:
      print('off',off,'w',w,'out',len(out),'unused',len(d.unused_data),'head',out[:64].hex(),''.join(chr(x) if 32<=x<127 else '.' for x in out[:64]))
   except Exception as e: pass
