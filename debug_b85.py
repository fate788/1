import pathlib,re,zlib,xml.etree.ElementTree as ET
alpha='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz!#$%()*+,-./:;=?@[]^_{}'; p=pathlib.Path(r'C:\Users\13162\Documents\Codex\2026-10-18\di\work\archive-history\decoded')
def b85(s):
 out=bytearray(); powers=(52200625,614125,7225,85,1)
 for i in range(0,len(s),5):
  c=s[i:i+5]; a=0
  for j,ch in enumerate(c): a+=alpha.index(ch)*powers[j]
  if len(c)==5: out.extend(a.to_bytes(4,'big'))
  else:
   rem=len(s)%5; a+=84+powers[rem-1]; out.extend(a.to_bytes(4,'big')[:rem-1])
 return bytes(out)
for d in sorted(p.glob('ARCHIVE-*')):
 text=ET.fromstring((d/'CET_TRAINER.CETRAINER.xml').read_bytes()).findtext('LuaScript') or ''; s=re.search(r'decodeFunction\("([^"]+)"\)',text).group(1); raw=b85(s)
 print(d.name,len(s),len(raw),raw[:20].hex(),raw[-20:].hex())
 o=zlib.decompressobj();
 try:
  out=o.decompress(raw); print('out',len(out),'eof',o.eof,'unused',len(o.unused_data),'uncons',len(o.unconsumed_tail),'checksum?')
 except Exception as e:
  print('err',e,'out_sofar',len(o.unconsumed_tail),len(o.unused_data))
 # try truncate/pad final bytes
 for n in range(0,5):
  try: x=zlib.decompress(raw[:-n] if n else raw); print('trim',n,'ok',len(x))
  except Exception as e: pass
