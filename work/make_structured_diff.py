from pathlib import Path
import json,hashlib,xml.etree.ElementTree as ET
root=Path(r'C:\Users\13162\Documents\Codex\2026-10-18\di\work\archive-history'); final=root/'finalized'; report=json.loads((final/'bytecode-format-analysis.json').read_text(encoding='utf-8'))
versions={}
for v in ['ARCHIVE-0604','ARCHIVE-260718','ARCHIVE-260804']:
 xml=ET.fromstring((final/v/'CET_TRAINER.CETRAINER.xml').read_bytes()); txt=xml.findtext('LuaScript') or ''; versions[v]={'xml_root':xml.tag,'xml_attrs':xml.attrib,'xml_children':[e.tag for e in xml],'lua_script_outer_length':len(txt),'lua_script_prefix':txt[:20],'luac_length':(final/v/'LuaScript.luac').stat().st_size,'format':report['versions'][v]}
bs=[(final/v/'LuaScript.luac').read_bytes() for v in versions]; m=min(map(len,bs)); common=sum(1 for i in range(m) if bs[0][i]==bs[1][i]==bs[2][i])
out={'versions':versions,'common_byte_count_to_min_length':common,'min_length':m,'notes':['No Lua bytecode was executed.','Printable-string scan found no closeCE/os.exit/network/StarCraft/version hits; because the inner format is modified, this is not proof that those calls are absent.','Standard Lua 5.3 prototype parsing is invalid at the root and no bounded body offset probe 41..199 produced a plausible standard root prototype.']}
(final/'structured-diff.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print('wrote',final/'structured-diff.json')
