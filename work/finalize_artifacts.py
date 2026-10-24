from pathlib import Path
import shutil,hashlib,json,xml.etree.ElementTree as ET,datetime
root=Path(r'C:\Users\13162\Documents\Codex\2026-10-18\di\work\archive-history')
out=root/'finalized'; out.mkdir(exist_ok=True)
versions=['ARCHIVE-0604','ARCHIVE-260718','ARCHIVE-260804']
manifest={'method':[
 'Read-only copy of existing extracted archive manifests and files; no original EXE modified.',
 'ARCHIVE container was parsed as little-endian uint32 file count followed by raw DEFLATE stream at offset 4 and per-file name/folder/size records.',
 'CETRAINER was decoded in memory using the public Cheat Engine OpenSave protection order: byte-wise reverse/XOR passes, CE trainer header, raw DEFLATE; decoded XML was written as a copy.',
 'LuaScript first decodeFunction argument was decoded with the published CustomBase85 alphabet and zlib wrapper; the resulting bytes were saved without execution.'
], 'versions':{}}
for v in versions:
 vd=out/v; vd.mkdir(exist_ok=True)
 src=root/'extracted'/v; dec=root/'decoded'/v; luac=root/'luac'/(v+'.luac')
 # copies
 for n in ['manifest.json','CET_TRAINER.CETRAINER','defines.lua','cheatengine-x86_64.exe','lua53-64.dll']:
  s=src/n; t=vd/n; shutil.copyfile(s,t)
 xml=dec/'CET_TRAINER.CETRAINER.xml'; shutil.copyfile(xml,vd/'CET_TRAINER.CETRAINER.xml')
 rootxml=ET.fromstring(xml.read_bytes()); lua_text=rootxml.findtext('LuaScript') or ''
 (vd/'LuaScript.txt').write_text(lua_text,encoding='utf-8',newline='')
 shutil.copyfile(luac,vd/'LuaScript.luac')
 def info(p):
  b=p.read_bytes(); return {'path':str(p.relative_to(out)).replace('\\','/'),'size':len(b),'sha256':hashlib.sha256(b).hexdigest()}
 manifest['versions'][v]={'files':{n:info(vd/n) for n in ['manifest.json','CET_TRAINER.CETRAINER','defines.lua','cheatengine-x86_64.exe','lua53-64.dll','CET_TRAINER.CETRAINER.xml','LuaScript.txt','LuaScript.luac']},'xml_root':rootxml.tag,'xml_attrs':rootxml.attrib,'lua_script_length':len(lua_text)}
(out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
readme='''# 固化产物\n\n本目录只包含既有工作区副本的只读固化件。原始 EXE、游戏目录和临时目录未修改。\n\n## 转换链\n\n1. ARCHIVE：读取已保存 `ARCHIVE-*.raw`，解析小端 uint32 文件数，使用 raw DEFLATE（从偏移 4）解压，再按文件名长度、目录长度和文件大小读取记录。\n2. CETRAINER：对副本执行 Cheat Engine `OpenSave.pas` 公开保护算法的逆向字节变换；验证 `CHEAT` 头后以 raw DEFLATE 解压，保存 XML 副本。\n3. LuaScript：从 XML 读取 `decodeFunction` 的第一个字符串参数，按公开 CustomBase85 字符表还原，再用 zlib 解压；仅保存字节码，不执行。\n4. 所有结果均计算 SHA-256。\n'''
(out/'README.md').write_text(readme,encoding='utf-8')
print('WROTE',out)
