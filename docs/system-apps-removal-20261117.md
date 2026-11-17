# HyperOS 4 系统应用删除记录（2026-11-17）

设备：Xiaomi 15 `dada` / 24129PN74C，HyperOS OS4.0.4.0.XOCCNXM，Android 17 / SDK 37，BL 锁定。

## 结论先说：怎么删得掉

shell（uid 2000）在这台机器上被 MIUI 拦死了两条常规路：

```
$ adb shell pm uninstall --user 0 com.xiaomi.macro
Failure [only root can delete system app for a particular user]

$ adb shell pm disable-user --user 0 com.xiaomi.macro
java.lang.SecurityException: Cannot disable system packages.
  at com.android.server.pm.PackageManagerServiceImpl.shouldRestrictEnabledSettingsChange(...)
```

`pm hide` 也不行（`requires: android.permission.MANAGE_USERS`）。Shizuku 以 uid 2000 运行，同样受限 ——
**装 Shizuku 并不能让系统应用变成可删的**。

真正可用的是 khleak 那个 uid=0 会话，但它默认上下文是 `u:object_r:unlabeled:s0`，
servicemanager 不认，所以直接跑 `pm` 会得到 `cmd: Can't find service: package`。
SELinux 此时是 `Permissive`，用 `runcon` 换到系统认得的域即可：

```bash
adb shell /data/local/tmp/khleak su -c \
  "runcon u:r:shell:s0 sh -c 'pm uninstall --user 0 <package>'"
# => Success
```

`runcon u:r:shell:s0` 下 uid 仍是 0，MIUI 的 root 判定通过，删除生效。

## 已删除的 10 个包

| 应用名 | 包名 | 结果 |
|---|---|---|
| SystemHelper（system-helper） | `com.mobiletools.systemhelper` | Success |
| 搜狗输入法小米版 | `com.sohu.inputmethod.sogou.xiaomi` | Success |
| 智能助理（负一屏） | `com.miui.personalassistant` | Success |
| 生活黄页 | `com.miui.yellowpage` | Success |
| 快应用服务框架 | `com.miui.hybrid` | Success |
| 分析 | `com.miui.analytics` | Success |
| 智能服务（MSA 广告 SDK） | `com.miui.systemAdSolution` | Success |
| 系统安全组件（AI 反诈） | `com.miui.guardprovider` | Success |
| 自动连招 | `com.xiaomi.macro` | Success |
| 米币支付 | `com.xiaomi.payment` | Success |

包名是靠 `aapt2 dump badging` 逐个小包名核对出来的，不是猜的：
`com.miui.guardprovider` = `System security components`、`com.miui.systemAdSolution` = `智能服务`、
`com.xiaomi.payment` = `Mi Coins`、`com.miui.yellowpage` = `Yellow pages`、
`com.miui.hybrid` = `Quick apps Service Framework`、`com.miui.personalassistant` = `App vault`。

## 删除的语义（重要）

这是 `pm uninstall --user 0`，**不是删掉 /system 或 /product 里的 APK**：

- 对 user 0 而言应用消失：桌面图标没了、不随开机启动、不出现在应用列表、不能更新；
- APK 本体仍在系统分区，OTA 升级后可能被重新装回来；
- 想彻底从分区里抹掉，必须有可写 `boot`/`init_boot` 的 root（Magisk/KernelSU）做 remount —— 仍受 BL 锁定限制。

恢复（脚本已推到手机）：

```bash
adb shell /data/local/tmp/khleak su -c \
  "runcon u:r:shell:s0 sh /data/local/tmp/../../scripts/restore-miui-apps.sh"
# 单条：pm install-existing --user 0 <package>
```

脚本源码：[../../scripts/restore-miui-apps.sh](restore-miui-apps.sh)

## 副作用与实际状态

- 默认输入法是微信输入法（`com.tencent.wetype`），删搜狗不影响打字；
  其余仍可用的输入法：百度输入法小米版、讯飞输入法小米版。
- 桌面（`com.miui.home` RELEASE-8.01.02.8607）正常，`topResumedActivity=com.miui.home/.launcher.Launcher`。
- 负一屏、黄页、快应用、米币支付入口按预期消失。
- 卸载后 `pm list packages` 对这 10 个包的计数全部为 0。

## Shizuku

- 版本 `13.6.0.r1086.2650830c`，已安装，通过 adb 启动：
  `adb shell /data/app/~~wrkCxi4C_qY9FuBbnC8e_Q==/moe.shizuku.privileged.api-zxLlDzC1fR-sri7JcHX-dA==/lib/arm64/libshizuku.so`
- 服务进程 `shizuku_server` 以 shell uid 运行，界面显示「Shizuku 正在运行 / 版本 13.5，adb」。
- **重启后失效**，需要重新执行上面的 adb 启动命令（或在手机上配对无线调试后从界面启动）。
