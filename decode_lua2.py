import pathlib,re,zlib,hashlib,xml.etree.ElementTree as ET
alpha='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz!#$%()*+,-./:;=?@[]^_{}'; base=pathlib.Path(r'C:\Users\13162\Documents\Codex\2026-10-18\di\work\archive-history\decoded'); out=pathlib.Path(r'C:\Users\13162\Documents\Codex\2026-10-18\di\work\archive-history\luac'); out.mkdir(exist_ok=True)
def b85(s):
 result=bytearray(); powers=(52200625,614125,7225,85,1)
 for i in range(0,len(s),5):
  c=s[i:i+5]; a=0
  for j,ch in enumerate(c): a += alpha.index(ch)*powers[j]
  if len(c)==5: result.extend(a.to_bytes(4,'big')); continue
  rem=len(s)%5
  if rem in (2,3,4):
   a += 84 + powers[rem-1]; result.extend(a.to_bytes(4,'big')[:rem-1])
 return bytes(result)
for d in sorted(base.glob('ARCHIVE-*')):
 xml=ET.fromstring((d/'CET_TRAINER.CETRAINER.xml').read_bytes()); text=xml.findtext('LuaScript') or ''; m=re.search(r'decodeFunction\("([^"]+)"\)',text); enc=m.group(1); raw=b85(enc); luac=zlib.decompress(raw); (out/(d.name+'.luac')).write_bytes(luac)
 print('\n'+d.name,'encoded',len(enc),'zlib',len(raw),'luac',len(luac),'sha',hashlib.sha256(luac).hexdigest(),'head',luac[:20].hex())
 ss=[]
 for mm in re.finditer(rb'[\x20-\x7e]{4,}',luac): ss.append((mm.start(),mm.group().decode('latin1')))
 print('printable strings >=4',len(ss))
 keys=['version','starcraft','sc2','7897','http','https','socket','heng','process','address','openprocess','memory','error','client','min','too old','base98370','5.0','trainer','origin','lua','connect','send','receive','read','write']
 for off,s in ss:
  if any(k in s.lower() for k in keys): print(off,repr(s[:1500]))
