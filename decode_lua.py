import pathlib,re,base64,zlib,hashlib,xml.etree.ElementTree as ET
alphabet='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz!#$%()*+,-./:;=?@[]^_{}'
p=pathlib.Path(r'C:\Users\13162\Documents\Codex\2026-10-18\di\work\archive-history\decoded')
out=pathlib.Path(r'C:\Users\13162\Documents\Codex\2026-10-18\di\work\archive-history\luac'); out.mkdir(exist_ok=True)
def b85(s):
 r=bytearray(); powers=[85**4,85**3,85**2,85,1]
 for i in range(0,len(s),5):
  c=s[i:i+5]; a=0
  for j,ch in enumerate(c): a+=alphabet.index(ch)*powers[j]
  if len(c)==5: r.extend(a.to_bytes(4,'big'))
  else:
   rem=len(s)%5
   if rem in (2,3,4):
    a+=84+85**(rem-1); r.extend(a.to_bytes(4,'big')[:rem-1])
 return bytes(r)
for d in sorted(p.glob('ARCHIVE-*')):
 xml=ET.fromstring((d/'CET_TRAINER.CETRAINER.xml').read_bytes()); text=xml.findtext('LuaScript') or ''
 m=re.search(r'decodeFunction\("([^"]+)"\)',text)
 print('\n',d.name,'encoded_len',len(m.group(1)) if m else None)
 if not m: continue
 enc=m.group(1); raw=b85(enc); print('b85 bytes',len(raw),'head',raw[:16].hex())
 try: luac=zlib.decompress(raw); print('luac len',len(luac),'head',luac[:20].hex(), 'sha',hashlib.sha256(luac).hexdigest())
 except Exception as e: print('zlib fail',e); continue
 (out/(d.name+'.luac')).write_bytes(luac)
 # printable strings >=4
 ss=[]
 for mm in re.finditer(rb'[\x20-\x7e]{4,}',luac):
  s=mm.group().decode('latin1'); ss.append((mm.start(),s))
 print('strings',len(ss))
 keys=['version','starcraft','sc2','7897','http','https','socket','heng','process','address','openprocess','read','write','memory','error','client','min','too old','base98370','5.0','lua','origin','trainer']
 for off,s in ss:
  if any(k in s.lower() for k in keys): print(off,repr(s[:1000]))
