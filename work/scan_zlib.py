import zlib, pathlib, hashlib
base=pathlib.Path(r'C:\Users\13162\Documents\Codex\2026-10-18\di\work\archive-history')
for p in sorted(base.glob('*.raw')):
    b=p.read_bytes()
    print('\n',p.name,len(b),hashlib.sha256(b).hexdigest(), flush=True)
    c=[]
    for i in range(len(b)-1):
        cmf,flg=b[i],b[i+1]
        if cmf==0x78 and ((cmf<<8|flg)%31)==0:
            c.append(i)
    print('zlib candidates',len(c),c[:30], flush=True)
    rows=[]
    for i in c:
        for w in (15, -15):
            try:
                d=zlib.decompressobj(w)
                out=d.decompress(b[i:])
                out += d.flush()
                if len(out)>=8:
                    rows.append((i,w,len(out),len(d.unused_data),len(d.unconsumed_tail),out[:32]))
            except Exception:
                pass
    print('valid streams',len(rows), flush=True)
    for row in rows[:40]:
        i,w,n,u,uc,head=row
        printable=''.join(chr(x) if 32<=x<127 else '.' for x in head)
        print(f'  off={i} w={w} out={n} unused={u} uncons={uc} head={head.hex()} {printable}', flush=True)
