# 260804 维护候选报告

## 数据流结论

`R23` 在根函数 pc161 创建。Child Proto 5 通过根 R23 的捕获上值，将响应中按 35 字节步长切出的片段写入该表。递归解析全部原型的上值链后，当前版本的直接消费者只有 `root.child[73].child[0]`：

1. pc189 读取 `R23[1]`，与 `smdx("33")` 比较；匹配时调用全局 `gameIntCode(true)`，并把 306 写入状态上值。
2. pc203–205 对 R23 调用 `pairs`；pc207/210 对迭代值和 `smdx` 处理后的捕获值比较；命中时把 317 写入状态上值，并再次调用 `gameIntCode(true)`。
3. pc266 以后才进入 `p_info`、`readInteger`、`modifyBuff`、`GetBehTable`、`GetUnitTable` 等后续过程/功能初始化路径。

因此已确认 R23 是启动策略/版本选择输入；没有证据表明其条目自身就是地址或偏移表，也没有证据证明它只用于 UI。`gameIntCode` 的宿主实现未在 LuaScript、lua53-64.dll 或 CE 字符串中找到，故其副作用和 306/317 的业务含义仍未知。

## 实施的最小候选

`local-module/local_maintenance_policy.py` 是一个离线、失败关闭的可审计策略模块，复现：

- Child Proto 5 的字节级查找、换行截断、35 字节切片和边界限制；
- 第一条记录匹配返回 306；遍历记录匹配返回 317；无匹配返回 `None`；
- 不进行文本解码、大小写转换、联网或目标进程访问。

`maintenance-config.json` 只记录已核验的目标构建 `5.0.17.98370` 和已还原的选择常量，当前 `enabled=false`、`records=[]`。空表不会被视为成功。

## 离线验收

`tests/run_offline_tests.py` 已通过 8 项：缺 key、固定宽度记录、两条选择路径、禁用空配置、合成正常路径、错误记录长度、不支持构建和截断记录边界。测试数据为合成字节，不包含真实 key、响应正文或凭据。

## 为什么未生成 EXE

`build_repair_candidate.py` 已对工作区副本校验：

- EXE SHA-256：`CEA1493191BBD5513F556413D167E2FAD81879E91294DFF7C5CDCA61497CC9EF`；
- LuaScript SHA-256：`F3F8A6FB27551B7534717536BBA2F971EF93282ED9B2AB3C51607E7DD9BED28B`；
- lua53-64.dll SHA-256：`436F6BF9AC414E7E7259BEF4F6E287702A41E1FDDBDD9AF7D43350D47539A3C9`；
- CE 宿主副本 SHA-256：`C743CBED593EABB1BF8F938395045DF5C6422FFA9EDB3A7BE6ABCBCB86398B01`。

构建结果为 `candidate_not_built`。当前已经有能保持已解析结构的 LuaScript 写回器，以及 CETRAINER、ARCHIVE 的内容级解码/编码器；三份历史样本的无修改和受控变更测试已通过。外层重编码因 deflate 输出不确定而不保持原始字节，但重新解包后的内容、条目顺序和尾部数据一致。缺失的仍是成功的 key 响应/记录样本或本地发布规范、`gameIntCode` 的宿主契约，以及把这些编解码器接入完整 EXE 重建/加载验证的路径。直接把 Child Proto 5 改成 `true` 会跳过一个未解释的启动策略，不能作为兼容修复；当前也没有依据选择 306 或 317 来替代服务数据。

`candidate/repair-manifest.json` 记录了该停止原因；没有生成候选 EXE，原件、游戏文件和安全设置均未修改。

## 下一步

有了经验证的本地记录或明确的记录规范后，可以先在此模块中验证记录到 306/317 的选择，再实现自定义字节码写回并做结构/加载测试。随后才安排一次受控启动，分别验收“越过旧启动检查”和“Base98370 功能适配”；目前后者未验证。
