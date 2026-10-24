# R23 数据流与维护边界（260804）

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
line_end = string.find(response, "\n", pos) or (#response + 1)
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
