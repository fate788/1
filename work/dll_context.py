from pathlib import Path
p=Path(r'C:\Users\13162\Documents\Codex\2026-10-18\di\work\archive-history\extracted\ARCHIVE-260804\lua53-64.dll'); b=p.read_bytes();
for needle in [b'LUA_DUMP_STRINGSIZE_FORMAT2',b'bad header',b'format mismatch in',b'size mismatch in',b'bytecode']:
 i=b.find(needle); print(needle,i)
 if i>=0: print(b[i-600:i+700].decode('latin1','replace'))
