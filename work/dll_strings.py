from pathlib import Path
import re,hashlib
p=Path(r'C:\Users\13162\Documents\Codex\2026-10-18\di\work\archive-history\extracted\ARCHIVE-260804\lua53-64.dll'); b=p.read_bytes(); print('sha',hashlib.sha256(b).hexdigest())
for m in re.finditer(rb'[\x20-\x7e]{4,}',b):
 s=m.group().decode('latin1')
 if any(k in s.lower() for k in ['lua','version','opcode','dump','load','chunk']): print(m.start(),repr(s[:300]))
