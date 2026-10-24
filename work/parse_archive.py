import pathlib, zlib, struct, hashlib, json, os
base=pathlib.Path(r'C:\Users\13162\Documents\Codex\2026-10-18\di\work\archive-history')
outbase=base/'extracted'
outbase.mkdir(exist_ok=True)
for p in sorted(base.glob('ARCHIVE-*.raw')):
    b=p.read_bytes(); d=zlib.decompressobj(-15); plain=d.decompress(b[4:]); plain+=d.flush()
    print('\n'+p.name+' raw='+str(len(b))+' decompressed='+str(len(plain))+' unused='+str(len(d.unused_data)))
    pos=0; rec=[]; ok=True
    try:
      while pos < len(plain):
        start=pos
        if pos+4>len(plain): raise ValueError('trailing <4')
        nl=struct.unpack_from('<I',plain,pos)[0]; pos+=4
        if nl>100000 or pos+nl>len(plain): raise ValueError(f'bad name length {nl} at {start}')
        name=plain[pos:pos+nl].decode('latin1'); pos+=nl
        if pos+4>len(plain): raise ValueError('folder len missing')
        fl=struct.unpack_from('<I',plain,pos)[0]; pos+=4
        if fl>100000 or pos+fl>len(plain): raise ValueError(f'bad folder length {fl} at {pos-4}')
        folder=plain[pos:pos+fl].decode('latin1'); pos+=fl
        if pos+4>len(plain): raise ValueError('size missing')
        sz=struct.unpack_from('<I',plain,pos)[0]; pos+=4
        if pos+sz>len(plain): raise ValueError(f'bad size {sz} at {pos-4}, remain {len(plain)-pos}')
        data=plain[pos:pos+sz]; pos+=sz
        rec.append({'name':name,'folder':folder,'size':sz,'sha256':hashlib.sha256(data).hexdigest(),'head':data[:32].hex(),'start':start,'data_offset':pos-sz})
      if pos!=len(plain): raise ValueError('not at end')
    except Exception as e:
      ok=False; print('PARSE ERROR',e,'pos',pos,'remain',len(plain)-pos)
    print('records',len(rec),'parse_ok',ok)
    target=outbase/p.stem
    if target.exists():
      import shutil; shutil.rmtree(target)
    target.mkdir(parents=True)
    for i,r in enumerate(rec):
      rel=(r['folder'].replace('\\','/')+'/' if r['folder'] else '')+r['name']
      rel=rel.lstrip('/')
      if '..' in pathlib.PurePosixPath(rel).parts: print('SKIP unsafe',rel); continue
      data=plain[r['data_offset']:r['data_offset']+r['size']]
      fp=target.joinpath(*rel.split('/')); fp.parent.mkdir(parents=True,exist_ok=True); fp.write_bytes(data)
      print(f"{i}: folder={r['folder']!r} name={r['name']!r} size={r['size']} sha256={r['sha256']} head={r['head']}")
    (target/'manifest.json').write_text(json.dumps({'archive':p.name,'raw_size':len(b),'raw_sha256':hashlib.sha256(b).hexdigest(),'decompressed_size':len(plain),'records':rec},ensure_ascii=False,indent=2),encoding='utf-8')
