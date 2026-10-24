from pathlib import Path
import struct
for p in sorted(Path(r'C:\Users\13162\Documents\Codex\2026-10-18\di\work\archive-history/luac').glob('*.luac')):
 b=p.read_bytes(); body=b[41:]; pos=0
 nups=body[pos]; pos+=1
 ssize=body[pos]; pos+=1
 src=body[pos:pos+max(0,ssize-1)]; pos+=max(0,ssize-1)
 vals=[]
 for label in ['linedefined','lastlinedefined']:
  if pos+4<=len(body): vals.append((label,struct.unpack_from('<I',body,pos)[0])); pos+=4
 if pos+3<=len(body): vals += [('numparams',body[pos]),('isvararg',body[pos+1]),('maxstack',body[pos+2])]; pos+=3
 code=struct.unpack_from('<I',body,pos)[0] if pos+4<=len(body) else None
 print(p.name,'bodylen',len(body),'nups',nups,'srcsize',ssize,'src_head',src[:20].hex(),'fields',vals,'code_size',code,'pos_after_header',pos+4,'remaining',len(body)-(pos+4))
