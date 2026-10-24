from pathlib import Path
import struct
for p in sorted(Path(r'C:\Users\13162\Documents\Codex\2026-10-18\di\work\archive-history/luac').glob('*.luac')):
 b=p.read_bytes(); body=b[41:]; key0=bytes([0xce,0xce,0xce]); k=body[3:7]
 keys=key0+bytes(k*((len(body)-3+3)//4))[:len(body)-3]
 x=bytes(v^keys[i] for i,v in enumerate(body))
 print(p.name,'key',k.hex(),'head',x[:40].hex(' '),'fields',x[:13].hex(), 'code',struct.unpack_from('<I',x,13)[0])
