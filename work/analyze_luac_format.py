from pathlib import Path
import struct,hashlib,json,re,math
root=Path(r'C:\Users\13162\Documents\Codex\2026-10-18\di\work\archive-history'); out=root/'finalized'; report={'parser':'standard Lua 5.3 layout probe only; no execution','versions':{}}
for p in sorted((root/'luac').glob('*.luac')):
 b=p.read_bytes(); v=p.stem
 h={
  'luac_sha256':hashlib.sha256(b).hexdigest(),'size':len(b),
  'magic':b[:5].decode('latin1'),'version_byte':b[4] if len(b)>4 else None,
  'format_byte':b[5] if len(b)>5 else None,
  'extension_after_format':b[6:14].hex(),
  'luac_data':b[14:20].hex(),
  'sizes':list(b[20:25]),
  'luac_int':struct.unpack_from('<Q',b,25)[0] if len(b)>=33 else None,
  'luac_num':struct.unpack_from('<d',b,33)[0] if len(b)>=41 else None,
  'body_offset':41
 }
 body=b[41:]; pos=0
 try:
  h['standard_probe']={'upvalue_count_byte':body[0],'source_size_byte':body[1]}
  pos=2; ssize=body[1]
  if ssize==255:
   raise ValueError('long source size not handled in probe')
  pos += max(0,ssize-1)
  h['standard_probe']['source_end']=pos
  h['standard_probe']['linedefined']=struct.unpack_from('<I',body,pos)[0]; pos+=4
  h['standard_probe']['lastlinedefined']=struct.unpack_from('<I',body,pos)[0]; pos+=4
  h['standard_probe']['numparams']=body[pos]; h['standard_probe']['is_vararg']=body[pos+1]; h['standard_probe']['maxstacksize']=body[pos+2]; pos+=3
  h['standard_probe']['code_size']=struct.unpack_from('<I',body,pos)[0]; pos+=4
  h['standard_probe']['code_bytes_available']=len(body)-pos
  h['standard_probe']['valid_code_span']=h['standard_probe']['code_size']*4 <= len(body)-pos
  h['standard_probe']['status']='invalid' if not h['standard_probe']['valid_code_span'] else 'not fully parsed'
 except Exception as e:
  h['standard_probe_error']=str(e)
 strings=[]
 for m in re.finditer(rb'[\x20-\x7e]{4,}',b): strings.append(m.group().decode('latin1'))
 h['printable_strings_ge4']=len(strings)
 h['target_string_hits']=[s for s in strings if any(k in s.lower() for k in ['starcraft','sc2','7897','http','https','closece','os.exit','getprocess','version','client','error'])]
 report['versions'][v]=h
(out/'bytecode-format-analysis.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
