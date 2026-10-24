# 260804 本地维护候选

本目录是独立工作区副本。`reference/` 中的 EXE、Lua 字节码和 DLL 只读保留；原始下载文件、游戏目录和历史日志未覆盖。

## 当前交付

- `analysis/r23-dataflow.md`：从已解析字节码生成的 R23 别名、上值和消费者报告。
- `local-module/local_maintenance_policy.py`：不联网、不执行 Lua 的本地策略模型，严格复现 Child Proto 5 的字节切片和 306/317 选择分支；未匹配时返回 `None`，不强制成功。
- `local-module/maintenance-config.json`：目标构建记录和选择常量；当前故意禁用且无记录，因为工作区没有成功的 key 响应或发布格式规范。
- `tests/run_offline_tests.py`：离线回归入口。
- `archive_codec.py` / `cetrainer_codec.py`：有界的 ARCHIVE、CETRAINER 解码/编码器，保留未知尾部和未解释字段。
- `tests/run_codec_tests.py`：统一运行 LuaScript、CETRAINER 和 ARCHIVE 的无修改往返及受控内容变更测试；测试不会启动目标或游戏。
- `build_repair_candidate.py` / `build_repair_candidate.ps1`：固定输入哈希的守护式构建脚本。缺少经过验证的记录或自定义字节码重打包器时只生成 `candidate/repair-manifest.json`，拒绝写出 EXE。

## 离线验证

在工作目录执行：

```powershell
python .\tests\run_offline_tests.py
```

测试覆盖缺 key、固定宽度记录提取、306/317 选择、空配置拒绝和错误记录长度。测试数据为合成字节，不包含真实 key、响应或凭据。

## 为什么当前没有修改 EXE

## 外层封装验证

三份历史样本的 LuaScript 无修改往返逐字节一致。CETRAINER 和 ARCHIVE 的无修改重编码均能再次解包得到完全相同的 XML、条目内容、条目顺序和尾部字节；压缩器输出不同，因此外层文件字节不要求一致。受控 XML、Lua 常量和单条 ARCHIVE 内容变更测试均验证了预期变化只出现在目标语义处。生成的二进制测试产物位于 `test-runs/`，已被 `.gitignore` 排除。

静态证据表明 R23 不是地址/偏移表：它只在 `OnTimer` 中参与第一条记录比较、`pairs(R23)` 比较，并触发全局 `gameIntCode(true)` 及状态 306/317；后续 `GetSC2ProcessPid`、`F_OpenProcess` 和内存初始化由另一段闭包继续执行。可是 `gameIntCode` 的宿主契约、成功响应中的真实 35 字节记录和远程检查的正规本地替代格式都没有在工作区得到验证。

直接改 Child Proto 5 返回 `true` 会绕过这个未解释的启动策略，空表也不能冒充成功。当前虽已有结构化 LuaScript、CETRAINER 和 ARCHIVE 编解码器，但它们尚未接入完整 EXE 重建/加载验证路径；构建脚本仍会在哈希和策略前置条件检查后安全停止，不生成所谓修复版。

要继续生成可执行候选，最小缺失项是：一个经验证的成功记录样本（可只在本地保存）或明确的本地配置规范，以及能保持原自定义字节码格式、闭包和上值布局的写回工具。拿到后仍需先离线验证 306/317 分支和后续初始化，再安排一次受控启动。
