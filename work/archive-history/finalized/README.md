# 固化产物

本目录只包含既有工作区副本的只读固化件。原始 EXE、游戏目录和临时目录未修改。

## 转换链

1. ARCHIVE：读取已保存 `ARCHIVE-*.raw`，解析小端 uint32 文件数，使用 raw DEFLATE（从偏移 4）解压，再按文件名长度、目录长度和文件大小读取记录。
2. CETRAINER：对副本执行 Cheat Engine `OpenSave.pas` 公开保护算法的逆向字节变换；验证 `CHEAT` 头后以 raw DEFLATE 解压，保存 XML 副本。
3. LuaScript：从 XML 读取 `decodeFunction` 的第一个字符串参数，按公开 CustomBase85 字符表还原，再用 zlib 解压；仅保存字节码，不执行。
4. 所有结果均计算 SHA-256。

## 字节码验证
bytecode-format-analysis.json records the fixed header, the standard Lua 5.3 probe failure, and printable-string scan. A bounded probe over body offsets 41..199 found no plausible standard Lua 5.3 root prototype in any version. This is a parser result, not execution.

## 本轮格式核查的修正与边界

此前“多个样本共同位置只有少量字节相同”的描述只能说明二进制差异较大，不能推出原始脚本整体重写、保护机制或具体失效原因。

本轮通过 `lua53-64.dll` 的只读 PE/指令引用扫描确认：字符串 `LUA_DUMP_STRINGSIZE_FORMAT2` 位于实际的 Lua chunk 头检查函数（函数 RVA `0xbbce0`--`0xbbefd`）中，并与 `int`、`size_t`、`Instruction`、`lua_Integer` 和 `lua_Number` 等尺寸标签相邻。头检查函数在一个已读入的单字节分支值非零时把该字符串传给共同尺寸检查辅助函数 RVA `0xbc140`；另一分支使用 `size_t` 标签。这个上下文证明它是运行时头检查中的诊断标签，不能单独证明某种编码算法，也尚未把该分支值与字节码偏移 6--13 的额外 8 字节一一对应。

头检查函数的直接调用者位于 RVA `0xbc2e0` 附近；随后在 RVA `0xbc2e9` 调用内部单字节读取辅助函数 RVA `0xbad10`。三个样本在偏移 41 的第一个后续字节均为 `cf`。该字节确实被读取，但其自定义格式字段语义仍未知，不能套用标准 Lua 5.3 的 upvalue-count 解释。

官方 Cheat Engine 源码的公开实现（提交 `acc6cefd0f18d9dd97040e6cc0a5339e9f056e2e`，`Cheat Engine/lua53/lua53/src/lundump.c` 与 `ldump.c`）只显示标准 `LUAC_FORMAT=0` 和标准头字段顺序；在已核对的官方路径历史中没有发现 `Format=1` 或额外 8 字节字段的实现。因此当前结论是“已确认存在自定义头检查分支，字段语义部分未知”，不是“已恢复完整格式”。

## Capstone 读取器核验

`analyze_custom_reader.py` 使用工作区虚拟环境中的 Capstone 5.0.9，只读反汇编 `lua53-64.dll`。它确认 format=1 分支通过 `0xbbdb6 -> 0xbb6c0 -> 0xbab90` 读取偏移 6..13 的 8 字节，将低 32 位写入状态 `+0x20`；头检查成功在 `0xbbeec` 设置 `+0x24=1`。之后 `0xbab90` 在 `+0x24` 和 `+0x20` 非零时对读取缓冲区执行按索引变换：`i mod 8 == 0` 使用 `0xce`，否则使用状态低 32 位算术右移 `i mod 14` 后的低字节，再 XOR 写回。调用者在 `0xbc2e9` 读取头后第一个字节，三个样本偏移 41 的 `cf` 均变为 `01`。这确认了首主体字段的读取规则，但没有声称恢复完整 Lua 原型。
