# 受控启动诊断包

此包只针对已经准备好的工作区副本运行一次，不接受命令行参数，不下载或上传内容。

## 启动

1. 右键 **Windows PowerShell**，选择“以管理员身份运行”。
2. 在提升后的窗口执行：

```powershell
& 'C:\Users\13162\Documents\Codex\2026-10-18\di\work\diagnostic-package\run_startup_observation.ps1'
```

启动文件会检查当前有效管理员令牌、固定 Python、脚本、工作目录、目标 EXE 和参考 Lua DLL 的哈希；任一检查失败就退出，不启动目标。它只启动固定的 `observe_modifier_startup.py`，不创建常驻通道。

## 输出

- 观测 JSON：`C:\Users\13162\Documents\Codex\2026-10-18\di\work\diagnostic-package\startup-observation-run.json`
- 启动器日志：`C:\Users\13162\Documents\Codex\2026-10-18\di\work\diagnostic-package\launcher-output.log`

观测器仍使用固定 45 秒超时和 20,000 次 VM 入口命中上限；验证加载的 Lua DLL、Proto+0x38、根函数签名、savedpc 对齐和函数范围后，才读取有限判断值。它不附加或操作游戏，不修改比较结果，不写入磁盘 EXE；软件断点只存在于本次被调试进程内存中，并在诊断链结束时清理/终止本次创建的修改器链。

## 固定文件哈希

| 文件 | SHA-256 |
|---|---|
| `observe_modifier_startup.py` | `4D705D6CBDECE9BD6BFFC9B2AC42301744B3CFBC9B3C3EF6409C3960C6EC6754` |
| `run_startup_observation.ps1` | `493C15D6BB753345CBEB08B646AA8D6BE7C712A912A16CAA3DCC5C61C0698975` |
| 目标副本 `SC2_Inv_260804SPt19_1316241517.exe` | `CEA1493191BBD5513F556413D167E2FAD81879E91294DFF7C5CDCA61497CC9EF` |
| 参考 `lua53-64.dll` | `436F6BF9AC414E7E7259BEF4F6E287702A41E1FDDBDD9AF7D43350D47539A3C9` |
