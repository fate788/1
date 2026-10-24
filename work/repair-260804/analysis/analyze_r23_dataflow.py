from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PARSE = ROOT / "work" / "archive-history" / "finalized" / "custom-luac-parse.json"
OUT = Path(__file__).resolve().parent


def load_latest():
    data = json.loads(PARSE.read_text(encoding="utf-8"))
    return next(s for s in data["samples"] if "ARCHIVE-260804" in s["path"])


def all_nodes(node, path="root"):
    yield node, path
    for i, child in enumerate(node.get("children", [])):
        yield from all_nodes(child, f"{path}.child[{i}]")


def build_parents(root):
    parents = {id(root): None}
    paths = {id(root): "root"}

    def walk(node, path):
        for i, child in enumerate(node.get("children", [])):
            parents[id(child)] = node
            paths[id(child)] = f"{path}.child[{i}]"
            walk(child, paths[id(child)])

    walk(root, "root")
    return parents, paths


def resolve_upvalue(node, slot, parents, paths):
    up = node["upvalues"][slot]
    parent = parents[id(node)]
    if up["instack"]:
        if parent is None:
            return ("root.local", up["idx"])
        if parent is not None and paths[id(parent)] == "root":
            return ("root.local", up["idx"])
        return (paths[id(parent)] + ".local", up["idx"])
    return resolve_upvalue(parent, up["idx"], parents, paths)


def value(node, index):
    c = node["constants"][index]
    v = c.get("value")
    if isinstance(v, dict):
        return v.get("text", v)
    return v


def rk(node, x):
    return f"K{x - 256}={value(node, x)!r}" if x >= 256 else f"R{x}"


def main():
    sample = load_latest()
    root = sample["root"]
    parents, paths = build_parents(root)
    n5 = root["children"][5]
    n73 = root["children"][73]
    n_on_timer = n73["children"][0]

    resolved = []
    for node, path in all_nodes(root):
        for slot in range(len(node.get("upvalues", []))):
            try:
                target = resolve_upvalue(node, slot, parents, paths)
            except Exception:
                continue
            if target == ("root.local", 23):
                uses = [
                    i for i in node["code"]["instructions"]
                    if i["opname"] in ("GETUPVAL", "SETUPVAL") and i["B"] == slot
                ]
                descendants = []
                for ci, child in enumerate(node.get("children", [])):
                    for child_slot, up in enumerate(child.get("upvalues", [])):
                        if not up["instack"] and up["idx"] == slot:
                            descendants.append({"child": ci, "slot": child_slot})
                resolved.append({
                    "path": path,
                    "slot": slot,
                    "upvalue": node["upvalues"][slot],
                    "target": target,
                    "uses": uses,
                    "descendants": descendants,
                })

    out = {
        "sample": sample["path"],
        "lua_sha256": sample["sha256"],
        "root_r23_creation": {"pc": 161, "op": "NEWTABLE", "A": 23},
        "root_registration": [
            {"pc": 162, "op": "CLOSURE", "A": 24, "child": 5},
            {"pc": 163, "op": "SETTABUP", "key": "GetAccountHandle", "value": "R24"},
        ],
        "r23_resolved_paths": resolved,
        "child5": {
            "upvalues": n5["upvalues"],
            "instructions": [
                {"pc": i["pc"], "op": i["opname"], "A": i["A"], "B": i["B"], "C": i["C"]}
                for i in n5["code"]["instructions"] if i["pc"] in [46, 48, 53, 54, 55, 56, 57, 58, 60, 61]
            ],
        },
        "on_timer_r23_and_consumers": [
            {
                "pc": 189,
                "op": "GETTABUP",
                "upvalue_slot": 35,
                "key": 1,
                "meaning": "R23[1]",
            },
            {
                "pc": 190,
                "op": "GETTABUP",
                "key": "smdx",
                "arg": "33",
            },
            {
                "pc": 193,
                "op": "EQ",
                "meaning": "compare R23[1] with smdx('33')",
            },
            {
                "pc": 197,
                "op": "GETTABUP",
                "key": "gameIntCode",
                "meaning": "external/global call target",
            },
            {
                "pc": 200,
                "op": "LOADK",
                "value": 306,
                "meaning": "stored in upvalue 11 after first-record match path",
            },
            {
                "pc": 203,
                "op": "GETTABUP",
                "key": "pairs",
                "meaning": "pairs(R23)",
            },
            {
                "pc": 204,
                "op": "GETUPVAL",
                "upvalue_slot": 35,
                "meaning": "passes captured R23 to pairs",
            },
            {
                "pc": 205,
                "op": "CALL",
                "meaning": "pairs(R23)",
            },
            {
                "pc": 207,
                "op": "GETTABUP",
                "key": "smdx",
                "meaning": "hash/transform of a captured runtime value",
            },
            {
                "pc": 210,
                "op": "EQ",
                "meaning": "compares an iterator result with smdx(captured value)",
            },
            {
                "pc": 212,
                "op": "LOADK",
                "value": 317,
                "meaning": "stored in upvalue 11 after loop-match path",
            },
            {
                "pc": 216,
                "op": "GETTABUP",
                "key": "gameIntCode",
                "meaning": "external/global call target",
            },
            {
                "pc": 266,
                "op": "GETUPVAL",
                "upvalue_slot": 16,
                "meaning": "continues into process/memory setup after selection",
            },
        ],
        "r23_direct_consumer_scope": {
            "direct_consumer": "root.child[73].child[0]",
            "nested_child0_captures_root_r23": False,
            "direct_memory_feature_code": "root.child[73].child[0].child[0]",
            "external_side_effect_boundary": "gameIntCode and later OnTimer code are external/host-dependent",
        },
    }
    (OUT / "r23-dataflow.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    md = f"""# R23 数据流与维护边界（260804）

## 结论

已确认：R23 是根函数 pc161 创建的空表。Child Proto 5（根 child[5]，注册名 `GetAccountHandle`）把解析出的固定宽度片段写入该表；后续唯一确认的直接消费者是 `root.child[73].child[0]`（由 `runcode` 注册的 `OnTimer` 闭包）。

已确认：R23 的直接读取只有两类：

- pc189：读取 `R23[1]`，与 `smdx("33")` 的结果比较；
- pc203–205：调用 `pairs(R23)`，遍历表并把迭代结果与 `smdx` 对某个捕获值的结果比较。

两条命中路径分别写入数值常量 306（pc200）或 317（pc212），并在 pc197/216 调用全局 `gameIntCode(true)`。这说明远程记录参与启动后的选择状态/游戏代码分支；没有指令证据表明 R23 本身包含地址、偏移或 UI 文本。

## 别名与上值

| 位置 | 证据 | 解释 |
|---|---|---|
| 根 pc161 | `NEWTABLE A=23` | 创建捕获表 R23 |
| 根 pc162–163 | `CLOSURE child[5]`; `SETTABUP _ENV[GetAccountHandle] = R24` | Child Proto 5 捕获根 R23 |
| Child 5 pc46/48 | `GETUPVAL slot1`; `table.insert` | 将片段插入 R23 |
| Child 5 pc53–61 | `GETUPVAL slot1`; `LEN`; `0 < #R23` | 返回表是否非空 |
| 根 child[73] upvalue 26 | `instack=1, idx=23` | 捕获根 R23 |
| child[73].child[0] upvalue 35 | 解析为 parent upvalue 26 | OnTimer 的 R23 别名 |
| OnTimer pc189/203–205 | `R23[1]`、`pairs(R23)` | 唯一已确认的直接消费者 |

解析器对全部原型的上值链做了递归解析。当前样本中没有发现 `root.child[73].child[0].child[0]`（内存写入/代码执行闭包）直接捕获根 R23；它通过其他状态继续执行。因此不能把 R23 直接称为地址表或功能开关表。

## 伪代码（仅按已还原指令）

```text
-- Child 5
records = captured root R23
pos = string.find(response, key, 1, true)
if not pos then return false end
line_end = string.find(response, "\\n", pos) or (#response + 1)
chunk = string.sub(response, pos, line_end - 1)
for i = 1, ... do
    field = string.sub(chunk, 3 + 35*i, 3 + 35*i + 34)
    if field ~= nil and field ~= "" then
        table.insert(records, field)
    end
end
return (#records > 0)

-- OnTimer / runcode child[73].child[0]
if records[1] == smdx("33") then
    gameIntCode(true)       -- pc197–199
    selected_state = 306    -- pc200–201
else
    for _, value in pairs(records) do
        if value == smdx(captured_runtime_value) then
            selected_state = 317  -- pc212–213
            gameIntCode(true)     -- pc216–218
            break/continue according to the decoded jumps
        end
    end
end
-- Later pc230 onward continues process/memory/UI work.
```

The ellipsis in the parser loop is intentional: the loop terminates on an empty `string.sub` result, and its exact successful record count was not observed because the current response had no key match. The iterator variable names are descriptive only; the bytecode confirms the operations, not business names.

## What this means for a maintenance patch

The smallest defensible maintenance seam is the **record producer / local policy source**, not a blind `return true` change. The table is consumed by a version/strategy selection branch before later process and memory initialization. The global `gameIntCode` implementation and the two state constants' business meaning are outside this Lua prototype, so a local source must provide verified records and the expected selection semantics.

The available evidence does not include a successful response containing a key, a valid 35-byte record set, or a specification for the `gameIntCode` contract. Consequently a local source with an empty table would be an invalid success test, and selecting 306/317 from the current game build would be an unverified guess.

## Evidence status

- **已确认：** R23 creation, captures, insertions, direct consumers, selection constants, and the point where later process/memory code follows.
- **推导：** R23 is startup/version strategy input rather than a direct address table, because its only direct uses are the comparisons and `gameIntCode` calls.
- **未知：** exact record schema, captured runtime value at the loop, `gameIntCode` side effects, and whether the remote gate is an access-control contract.

The machine-readable counterpart is `r23-dataflow.json`. It was generated from the existing parsed sample and does not execute the target.
"""
    (OUT / "r23-dataflow.md").write_text(md, encoding="utf-8")


if __name__ == "__main__":
    main()
