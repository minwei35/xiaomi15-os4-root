# QuietMap 真机安装试验（2026-11-17）

## 环境

- Xiaomi 15 dada，Android 17 / SDK 37。
- 高德地图原版 17.03.0.2008，versionCode 170300。
- QuietMap 0.9.3，versionCode 22，libxposed API 102。
- NPatch 1.1.0 (857)，本地模式 `--manager`。
- 用户明确确认卸载原版、接受本地数据清除后进行测试。

## 校验

QuietMap APK SHA-256：`9bf3097d91db7e541c988007b45a7d5bce850f1eb1581109c1aaa8ff1792744c`，与官方 GitHub release 一致。
原包和补丁包哈希见 probe-20261117-quietmap-install.txt。

## 实测

1. 安装官方 QuietMap 成功，原版高德 APK 已拉到 PC 备份。
2. NPatch 制作本地模式高德测试包，默认 Basic (1)。
3. 用户确认后卸载原版并安装测试包。
4. 管理器：管理 → 应用 → 高德地图 → 模块作用域，勾选 QuietMap 并添加。作用域显示 1 个模块。
5. 启动高德，QuietMap 日志确认 AD/UI 多个钩子 registered；PV 默认关闭，AD-03/05 为作者已知 blocked 项。
6. QuietMap 设置页明确显示：
   - 已激活
   - 框架 API 102 · 已注入高德地图 · 目标 17.03.0.2008 · v0.9.3
   - remote prefs：可用，开关改动目标进程可读
7. 但高德显示「我们检测到当前版本出现错误，请重新下载、安装」，点击忽略后退出。
8. 仅改变 NPatch 签名处理等级为 High (2)，同签名覆盖安装；再次启动仍显示相同错误。
9. 日志存在 `libserverkey-debug.so` 缺失及 remote provider 警告，目前尚未定位弹窗的具体检测方法，不能断定只有签名校验一个原因。

## 回滚与当前状态

- 卸载补丁版，重新安装备份的原始高德 APK，安装 Success。
- 原版冷启动正常进入「欢迎使用高德地图」及隐私条款页，进程 PID 12968；未替用户接受隐私条款。
- QuietMap 和 NPatch 管理器保留；当前原版高德没有加载器，因此当前不生效。
- 用户原先高德本地数据已按确认清除，原始 APK 备份不含应用数据。

## 结论

已证实 API 102 模块加载和远程设置通路可用；未证实补丁版高德实际可用，更不能声称去广告已完成。Basic/High 两个配置均被高德错误版本提示阻断。需要进一步定位该检测入口再决定后续兼容方案。

## 证据

- probe-20261117-quietmap-install.txt
- probe-20261117-quietmap-runtime.txt
- PC 本地 evidence：xiaomi15-root-audit/lsposed/quietmap/，含原包、两种测试包和 UI XML。
