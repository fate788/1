from pathlib import Path
import xml.etree.ElementTree as ET, hashlib, re, difflib
base=Path(r'C:\Users\13162\Documents\Codex\2026-10-18\di\work\archive-history\decoded')
texts={}
for d in sorted(base.glob('ARCHIVE-*')):
 xml=(d/'CET_TRAINER.CETRAINER.xml').read_bytes(); root=ET.fromstring(xml)
 print('\n'+d.name,'xmlsize',len(xml),'sha',hashlib.sha256(xml).hexdigest(),'root',root.attrib)
 for el in root.iter():
  txt=''.join(el.itertext())
  if txt.strip():
   print('tag',el.tag,'attrs',el.attrib,'textlen',len(txt),'head',repr(txt[:160]))
   texts[d.name]=txt
   lines=txt.splitlines()
   keys=['version','starcraft','sc2','7897','http','https','socket','heng','process','openprocess','aob','address','write','read','min','client','too old','error','base98370','5.0']
   matches=[]
   for i,line in enumerate(lines,1):
    if any(k in line.lower() for k in keys): matches.append((i,line[:500]))
   print('matches',len(matches))
   for i,line in matches[:250]: print(f' {i}: {line}')
# normalized diff summary
names=sorted(texts)
for i in range(1,len(names)):
 a,b=names[i-1],names[i]
 la=texts[a].splitlines(); lb=texts[b].splitlines(); sm=difflib.SequenceMatcher(None,la,lb)
 print('\nDIFF',a,'->',b,'lines',len(la),len(lb),'ratio',sm.ratio(),'opcodes',sum(1 for x in sm.get_opcodes() if x[0]!='equal'))
 for tag,i1,i2,j1,j2 in sm.get_opcodes():
  if tag!='equal':
   print(tag,'A',i1+1,i2,'B',j1+1,j2)
   for x in la[i1:i2][:8]: print(' A',x[:300])
   for x in lb[j1:j2][:8]: print(' B',x[:300])
