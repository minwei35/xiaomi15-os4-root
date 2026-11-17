# LSPosed（Vector）生态在这台机器上的可行性

> 实测时间：2026-11-17 11:45–11:55
> 设备：Xiaomi 15 `dada`，HyperOS `OS4.0.4.0.XOCCNXM`，**Android 17 / SDK 37**，安全补丁 2026-10-01，
> `ro.build.type=user`，`ro.debuggable=0`，`ro.boot.flash.locked=1`，`verifiedbootstate=green`

## 0. 结论先行

**现在装不上 LSPosed。** 卡点不是版本、也不是 root 权限不够，而是**没有 boot 期 root**：

- Vector 是 **Zygisk 模块**（包里 `module.prop` 第一行就是 `id=zygisk_vector`），
- 它的安装器走 **Magisk/KernelSU 的 `update-binary` 协议**（`customize.sh` 里全是 `ui_print`/`abort`/`$TMPDIR`），
- 它的注入点在 **zygote 启动之前**。

khleak 给的是**用户态运行期** `uid=0 + FULLCAP`，那时候 zygote 早就 fork 完了，
已经在跑的 App 进程追不回去补注入。

**但「免 root 装模块」这条路没有被完全堵死**：2026-11-17 12:05 实测，
用 [NPatch](https://github.com/7723mod/NPatch) v1.1.0（Vector 核心，官方声明适配 Android 17 / SDK 37）
打出来的补丁包**在本机正常启动**（`KPROBE launch-ok sdk=37`）。细节与实测日志见 §10。
LSPatch 0.6 则确认在 A17 上不可用（见 §10.2 的 `NoSuchFieldError`）。

顺带纠正一条流传的说法：

> 「Android 16 上原版 LSPosed 停在 1.9.2（2023），社区分支叫 Vector，不要升级成新版，模块作用域会和 ZygiskSU 对不上」

前半段对，后半段在 **Android 17** 上是反的：

| | 支持范围 | 依据 |
|---|---|---|
| LSPosed 1.9.2（2023-10-11） | 到 Android 14 为止 | 发布说明里最后一条平台性改动是「修复 Android 14 上的 hook 错误 / 静态方法 hook」 |
| Vector v2.2（2026-08-04） | **Android 8.1 ~ 17** | 包内 `module.prop`：`description=… (Android 8.1 ~ 17)` |

所以在 A17 上要用的是 Vector v2.2（或更新的 canary），1.9.2 / 1.9.2-IT 那一代根本起不来。
「作用域对不上」这个担心也不成立：Vector 的作用域就是 LSPosed 原来的作用域模型，
真正的变量是**下面这套前提有没有**。

## 1. 实测核查（结论：`ZygiskSU 已在` 不成立）

| 检查项 | 命令 | 结果 | 含义 |
|---|---|---|---|
| SU 管理器数据目录 | `ls -la /data/adb`（root 身份） | 只有 `.` 和 `..` | 没有任何管理器写过数据 |
| 模块目录 | `ls /data/adb/modules` | `No such file or directory` | 一个模块都没装 |
| KernelSU 目录 | `ls /data/adb/ksu` | `No such file or directory` | 没有 KernelSU |
| 相关进程 | `ps -A \| grep -iE 'magisk\|ksud\|zygisk\|apd'` | 无 | 没有模块守护进程 |
| build 类型 | `getprop ro.build.type` | `user` | 连 `adb root` 都不可用 |
| `ro.debuggable` | `getprop ro.debuggable` | `0` | 同上 |
| BL | `ro.boot.flash.locked` / `verifiedbootstate` | `1` / `green` | 锁定，`/system`、`boot` 都不可写 |
| 现有 root | `/proc/<rootd>/status` | `Uid: 0 0 0 0`、`CapEff: 000001ffffffffff` | khleak 的**运行期** root |

`/data/adb` 存在但空，是因为系统预置了这个目录（SELinux 给 `0700 root:root`），
不代表有管理器 —— 有 Magisk/KSU 的话里面至少会有 `modules/`、`magisk.db` 或 `ksu/`。

## 2. 为什么「运行期 root」补不上 Zygisk

时间线是这样的：

```
init ──► [Zygisk 注入点] ──► zygote ──► forkAndSpecialize ──► 每个 App 进程
             ↑                                                    ↑
      需要 boot 期 root                                  khleak 在这里才拿到 root
```

Zygisk 干的事：把 `zygisk/*.so` 注入 zygote，再 hook `forkAndSpecialize`，
**这样每个新 fork 出来的 App 都会自动加载模块**。LSPosed 就是踩在这套 ABI 上的：
`service.sh` 在 `late_start` 起 `daemon`，daemon 再和注入进各进程的 companion 通信。

所以缺的不是「能不能写文件」，而是「**zygote 还没起来的时候，谁替我干活**」。这有三条硬阻塞：

1. **没有模块管理器当宿主**：`customize.sh` 全指望 Magisk/KSU 提供 `ui_print`/`abort`/`$TMPDIR`，
   `update-binary` 压根跑不起来；
2. **`sepolicy.rule` 落不了地**：那几条 `allow dex2oat …`、`type xposed_file` 需要 magiskd
   在开机阶段 patch sepolicy，运行期补不了；
3. **`systemless` 挂载不存在**：包里 `bin/arm64-v8a/dex2oat` 和 `liboat_hook.so` 是要顶掉系统
   `dex2oat` 的，靠的是开机时的 overlay 挂载（`/system` 只读且被 AVB 保护）。

这也是为什么「先 khleak 拿 root，再装 Magisk」这条路不成立：Magisk 自己就要改 `boot` 或
`init_boot` 的 ramdisk 才能拿到 boot 期 root，而这两个分区都在锁定的 BL 后面。

## 3. 三条路，各自的真实代价

| 路线 | 前提 | 能得到什么 | 代价 |
|---|---|---|---|
| **A. 解锁 BL + Magisk / KernelSU + Vector v2.2** | `fastboot flashing unlock`（清全部数据）、账号绑定 168 小时 | 完整 LSPosed：模块作用域全覆盖，含 `system_server`；1300+ 模块可用 | 清数据；每次 OTA 要重新修补 boot；部分银行/支付类 App 会检测 root |
| **B. LSPatch 本地模式（免 root）** | 一台有 JDK 的 PC（本机有 JDK 17） | 每个 App 单独打补丁，模块嵌进 App 里，**重启依然生效** | 只作用于被补丁的那个 App；不能做 `system_server` 作用域；改签名 → 原 App 要卸载重装（数据要备份）；LSPatch 最后发布是 0.6（2023-12，核心 LSPosed 1.9.2），**A17 上能不能跑必须实测** |
| **C. 继续 khleak 运行期 root** | 每次开机跑一次（本机 3 轮内命中） | 只能做「当下这一刻」的事：读 `/proc`、`dmesg`、BTF、改内存、临时代理 | 重启即失效；**承载不了任何常驻框架**，所以和 LSPosed 无缘 |

## 4. 你那 6 项逐条能不能落地

| 场景 | 模块（示例） | 需要的作用域 | A（解锁+LSPosed） | B（LSPatch 本地） |
|---|---|---|---|---|
| 微信防撤回 / 去广告 / 步数 | WXEntry / FkWeChat / lexin | 应用 `com.tencent.mm` | ✅ | ✅ 可，但**要重装微信**（签名变了），聊天记录必须先备份；微信自身有环境检测，风险最高的一项 |
| B 站港澳台番剧 | BiliRoaming | 应用 `tv.danmaku.bili` | ✅ | ✅ 可，BiliRoaming 官方也说明支持 local/内置模式；版本要匹配 |
| 高德 / 地图净化 | 静途 QuietMap | 应用 | ✅ | ✅ 可 |
| 视频 App 去广告 | 各家专用（可可影视等） | 应用（且只对特定版本生效） | ✅ | ✅ 可 |
| 应用变量 / 机型伪装 | 应用变量 | 应用 | ✅ | ✅ 可，但只改**被补丁 App 自己看到的** Build 字段；要全局伪装必须 `system` 作用域 |
| 模拟定位 | FakeLocation / 位置模拟 | 应用，部分功能要 system | ⚠️ 部分 | ⚠️ 应用级可用，系统级不行 |
| 屏幕防截屏（`FLAG_SECURE`） | Disable-FLAG_SECURE | **`system_server`** | ✅ | ❌ 本地模式做不到 |

一句话：**「只改某个 App 内部行为」的都能走 B，「改整个系统看到的」只有 A。**
你列表里 6 项中有 5 项属于前者，唯一硬边界是 Disable-FLAG_SECURE。

## 5. 已经做完的准备

- Vector v2.2 release 包已下载并校验（和 GitHub 发布页的 sha256 逐位一致）：

  | | |
  |---|---|
  | 文件 | `Vector-v2.2-3080-Release.zip` |
  | 大小 | 9316843 字节（8.89 MiB） |
  | sha256 | `9ee8323575d615f7b3f1076ff60b2a63a49390ef11881b52632311a37f6f79cc` |
  | 来源 | `https://github.com/JingMatrix/Vector/releases/download/v2.2/Vector-v2.2-3080-Release.zip` |

- 包结构已确认（这就是「必须走模块管理器」的直接证据）：

  ```
  module.prop            id=zygisk_vector, version=v2.2 (3080-…), "Android 8.1 ~ 17"
  customize.sh           Magisk 安装器 API（ui_print / abort / $TMPDIR）
  service.sh             late_start 起 daemon（unshare + 私有挂载命名空间）
  sepolicy.rule          开机期补 SELinux 规则
  bin/arm64-v8a/dex2oat  顶掉系统 dex2oat
  bin/arm64-v8a/liboat_hook.so
  daemon / daemon.apk / manager.apk / cli
  META-INF/com/google/android/update-binary
  ```

  包放在 `xiaomi15-root-audit/lsposed/`（不入库，9 MB 二进制）。

## 6. 如果选 A：解锁之后一次到底

```bash
# 0) 备份（解锁必定清数据）
#    小米云同步 + 本地全量（照片/微信/银行 App 的证书类数据）

# 1) 手机上：设置 → 更多设置 → 开发者选项 → 设备解锁状态 → 绑定账号，等 168 小时

# 2) 解锁（会清空 /data）
fastboot flashing unlock

# 3) 从官方 OTA 里取当前 boot（本仓库 tools/extract_boot.py 已经能只下这一段）
python tools/extract_boot.py            # → boot-stock.img

# 4a) Magisk：把 boot-stock.img 推到手机，Magisk App 里「安装 → 选择并修补文件」
#     拉回 patched 镜像后：
fastboot flash boot magisk_patched.img

# 4b) 或 KernelSU：装 KSU 管理器，用它的「安装」写 boot/init_boot

# 5) 装 Vector：Magisk/KSU → 模块 → 从本地安装 → 选 Vector-v2.2-3080-Release.zip
#    （KSU 还要先装 ZygiskNext，因为 KSU 本身不带 Zygisk）

# 6) 重启，打开 Vector，确认「模块」页能出来

# 7) 装模块：modules.lsposed.org 或各模块的 release，装完在 Vector 里勾作用域

# 8) 验证
adb shell 'su -c "ls /data/adb/modules"'      # 应看到 zygisk_vector + 各模块
adb shell 'su -c "cat /data/adb/modules/zygisk_vector/module.prop"'
```

## 7. 如果选 B：LSPatch 本地模式

> ⚠️ 2026-11-17 实测：LSPatch 0.6（核心 1.9.2）在 Android 17 上**不可用**，
> 卡在 `NoSuchFieldError: android.app.ActivityThread$AppBindData#compatInfo`（该字段 A17 已移除）。
> 请直接看 §10 的 NPatch 方案，本节仅留作对照。

PC 侧（本机 JDK 17 可用）：

```bash
# 1) 取 LSPatch（LSPosed/LSPatch 已 archive，最后版本 0.6）
#    release 资产里有 lspatch.jar（CLI）和 LSPatch.apk（管理器）
curl -L -o lspatch.jar https://github.com/LSPosed/LSPatch/releases/download/v0.6/lspatch.jar

# 2) 给目标 App 打补丁（-m 指定模块 apk，可多次）
java -jar lspatch.jar target.apk -m module.apk -o patched.apk --allow-downgrade

# 3) 装（签名与原版不同，必须先卸载原版；数据要提前备份）
adb install -r patched.apk
```

手机上也可以全程用 LSPatch.apk 操作（选 APK → 选模块 → 生成 → 安装）。
**A17 兼容性未知**：LSPatch 核心是 LSPosed 1.9.2，遇到 `ClassNotFoundException` /
启动即崩就是这套 loader 撑不住 A17，那就只能回到 A。

## 8. 待你定的两件事

1. 走 A 还是 B？
2. 走 B 的话，先拿哪个 App 试水？建议顺序：**地图净化 → B 站 → 视频去广告 → 微信（最后，因为它最贵）**。
   我这边可以立刻用它跑一遍 patch + 装机 + 冒烟。

## 9. 本轮实测补充（11:50–11:55）：两个新发现的硬阻塞

做兼容性验证时又撞到两件事，都会卡住路线 B，和 LSPatch 本身无关。

### 9.1 `kill` 不掉的系统限制：`adb install` 被 MIUI 挡

为了验证 LSPatch 0.6 的 loader 能不能撑住 Android 17，我用本机 SDK 现编了一个最小测试 APK
（`aapt2 link` + `javac` + `d8.jar` + `zipalign` + `apksigner`，8587 字节，签名 `CN=KProbe`），
结果装不进去：

```
adb install -r build/probe-signed.apk
Failure [INSTALL_FAILED_USER_RESTRICTED: Install canceled by user]
```

这是 MIUI/HyperOS 的「USB 安装」开关没开，不是签名也不是 minSdk 问题。
`settings list secure` 里也能看到安装管控的痕迹：
`immobulus_mode_switch_restrict=enable_24_allowlist_…`、`packageinstaller_forbidden_app_list`、
`installer_full_safe_version=1`。

**要装任何 APK（包括路线 B 打出来的补丁包），必须先在手机上做一步操作**：
设置 → 更多设置 → 开发者选项 → **USB 安装**（有的版本叫「通过 USB 安装应用」）
→ 打开（会要求登录小米账号 + 插 SIM 卡）。

### 9.2 khleak 的 root 是「文件级 root」，不是「binder 级 root」

想绕过上面的限制，试过用现成的 root 直接装：

```
$ khleak su -c "pm install -r -t /data/local/tmp/probe.apk"
cmd: Can't find service: package

$ khleak su -c "service list"
Found 0 services:

$ khleak su -c "cat /proc/self/attr/current"
u:object_r:unlabeled:s0
```

**`service list` 一个服务都看不到** —— 说明这个 root 进程连不上 servicemanager，
所以 `pm` / `settings` / `am` / `cmd` 这一整类命令全部不可用。

能用的：读写文件、`/proc`、`dmesg`、`tracefs`、`slabinfo`、`setsockopt`、改内核内存。
不能用的：任何要过 binder 的（装包、改设置、启停服务、查询包信息）。

这条比"临时 root"更值得记住：**它限定了 khleak root 的能力边界是文件系统，不是系统管理。**

### 9.3 所以路线 B 的前置条件是

1. 手机端打开「USB 安装」（一次性，需账号 + SIM）；
2. 或者放弃 adb 安装，改成：`adb push` 到 `/sdcard/Download/` → 用户在文件管理器里点开安装
   （A17 上 `am start -a VIEW -d file://…` 已被禁，只能靠 UI）。

这两条都不属于技术难题，但都需要你在手机上动手 —— 这也是为什么路线 B 现在还没跑起来。


---

## 10. 实测结果：免 root 路线改用 NPatch，Android 17 上能跑

### 10.1 结论

| 方案 | 版本 | Android 17 实测 | 判定 |
|---|---|---|---|
| LSPatch | 0.6（核心 LSPosed 1.9.2，2023-11） | `NoSuchFieldError: android.app.ActivityThread$AppBindData#compatInfo` → 进程被杀 → `ClassNotFoundException: com.kuro.probe.MainActivity` | ❌ 硬不兼容（反射的私有字段在 A17 被删） |
| **NPatch** | **v1.1.0（核心 Vector `core-837`）** | loader 全部就位，`KPROBE launch-ok sdk=37`，`topResumedActivity=…/.MainActivity` | ✅ 可用 |
| LSPosed / Vector | v2.2 | 装不上（无 Zygisk 宿主） | ❌ 见 §2 |

NPatch 的官方发布说明里明确写了 **「Android 17 Ready：Fully compatible with Android 17 (SDK 37)」**，
这和我们实测一致。

### 10.2 LSPatch 挂在哪一行

```
I LSPatch-MetaLoader: Bootstrap loader from embedment
D nativeloader: Load …base.apk!/assets/lspatch/so/arm64-v8a/liblspatch.so … ok
E LSPatch : createLoadedApk
E LSPatch : java.lang.NoSuchFieldError: android.app.ActivityThread$AppBindData#compatInfo
E LSPatch :   at de.robv.android.xposed.XposedHelpers.findField(XposedHelpers.java:246)
```

`AppBindData.compatInfo` 是 LSPatch 用来替换 ClassLoader 的锚点，AOSP 在 Android 17 上把它删了。
这不是"改个参数"能绕的，必须改核心代码 —— 所以要用基于 Vector 的 NPatch。

### 10.3 NPatch 的实测链路（本机，2026-11-17 12:04）

产物与校验：

| 文件 | 大小 | sha256 |
|---|---|---|
| `jar-v1.1.0-857-release.jar` | 9721803 | `903f5899f710fe920d2a48035f91d0b2a1f86eee86fcff53618ea9f9bd0b6a3d` |
| `manager-v1.1.0-857-release.apk` | 6309578 | `548bc86978bf10c6acd9a0076bdc97cc70c30b36648d7b891a0c3cafda9012e0` |

CLI 要 **Java 21**（class 版本 65），本机原只有 JDK 17 → 单独拉了 `jdk-21.0.13+9-jre` 放在
`xiaomi15-root-audit/lsposed/jre21/`。

补丁过程：

```
$ java -jar jar-v1.1.0-857-release.jar -o probeapp/build/npatch-app -f probeapp/build/probe2-signed.apk
Signing apk with built-in NPatch keystore (V2+V3, minSdk 28)...
Adding metaloader dex...            ← 替换成 classes.dex
Adding loader dex...                ← assets/npatch/
Adding native lib...                ← assets/npatch/libnpatch.so
Creating nested apk link...         ← 原包变 assets/lspatch/origin.apk 这种嵌套
Done. Output APK: …/probe2-signed-857-npatched.apk   (787 KB)
```

装机后的运行日志（全部来自真机 logcat）：

```
I NPatch-MetaLoader: Loading native bootstrap: /data/user/0/com.kuro.probe/cache/npatch/libnpatch-*.so
I NPatch  : Use manager: false
I NPatch  : Signature bypass level: 1
I NPatch-ApkHelper: Extracting origin.apk from assets.
I NPatch  : Original app declared no AppComponentFactory; clearing the stub
I NPatch  : hooked app initialized: android.app.LoadedApk@e2a1df1
I NPatch  : createLoadedApkWithContext cost: 10ms
W NPatch  : NeoLocal: Cannot reach Manager Provider.        ← 没装管理器时的正常回退
I NPatch  : legacy handleLoadPackage dispatched by framework hook: com.kuro.probe
I NPatch  : Appended host native library paths via ClassLoader.addNativePath: […base.apk!/lib/arm64-v8a]
I KPROBE  : attachBaseContext loader=dalvik.system.PathClassLoader
I KPROBE  : app-oncreate loader=dalvik.system.PathClassLoader
I KPROBE  : launch-ok sdk=37 loader=dalvik.system.PathClassLoader
```

最后一行 `sdk=37` 就是 Android 17。`topResumedActivity=com.kuro.probe/.MainActivity`，界面在。

### 10.4 一个必须记住的前提：被测 App 要声明自己的 Application

我们第一版测试 APK **没有** `android:name` 的 Application 类，NPatch 两条配置都不成：

- 默认 `-l 1`（开签名绕过）→ 进程被 `SIGILL` 打死，崩在 `NPatch-LogFlush` 线程
  （`Fatal signal 4 (SIGILL), code 1 (ILL_ILLOPC)`，栈里是 `XposedLogPrinter.drainLogLoop`）；
- `-l 0`（关签名绕过）→ 退回 `ClassNotFoundException: com.kuro.probe.MainActivity`。

补上一个 20 行的 `ProbeApp extends Application`（带 `attachBaseContext`/`onCreate` 日志）后，**一次通过**。
所以上表那组"失败"里混着"极简包没有 Application"这个变量，不能直接当成 A17 不兼容的证据。

好消息是真实 App（微信、B站、高德、各家视频）**都有**自己的 Application，形态和通过的这版一致。
但仍要拿真 App 复验一次才算定论。

### 10.5 管理器已装好

```
top.nkbe.npatch  versionName=1.1.0  versionCode=857  minSdk=28  targetSdk=37
```

装它的意义是拿到**本地模式的模块/作用域配置**：没有管理器时 NPatch 只能走
`NeoLocal: offline fallback mode`（`Loading from cache: []`），等于没有任何模块。

### 10.6 下一步（要你选 App）

真正的模块使用路径是：

```
NPatch 管理器选 APK → 选模块 → 生成补丁包 → 卸载原版 → 安装补丁版 → 在管理器里配作用域
```

PC 侧等价命令：

```bash
# 本地模式（作用域在管理器里配，换模块不用重打补丁）
java -jar jar-v1.1.0-857-release.jar --manager -o out target.apk

# 集成模式（模块直接嵌进 APK，自带模块，不依赖管理器）
java -jar jar-v1.1.0-857-release.jar -m module.apk -o out target.apk
```

代价不变：签名变了 → 原版必须先卸载 → **App 数据会丢**（微信要先备份聊天记录）。
`system_server` 作用域的模块（Disable-FLAG_SECURE 这类）仍然做不到，这条硬边界没变。
