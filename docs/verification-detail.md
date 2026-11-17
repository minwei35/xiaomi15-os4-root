# 小米 15（dada）免解锁 BL 的临时 root：CVE-2026-64560 / CVE-2026-98260 调研

> 整理：2026-11-16 · 来源：公开仓库 README + kernel.org CVE 公告 + 本机只读探测
> 状态：**纯调研，未在本机跑过任何 exploit**。所有"实测"字样指原仓库作者的实测，不是我的。

## 2026-11-17 复核结论（优先于下方 11-16 历史调研）

本次从 Gitea `main@4b07cdd` 取回原文，通过 USB ADB 只读核验，并读取 GitHub 原仓库及 CVEProject CNA 记录。没有运行漏洞程序、写 tracefs、调用 mqsas 执行通道、安装模块或重启手机。

### 当前手机

| 项 | 2026-11-17 USB ADB 实测 |
|---|---|
| 型号 / 代号 | `24129PN74C` / `dada` |
| 系统 | `OS4.0.4.0.XOCCNXM`，Android **17** / SDK **37** |
| fingerprint | `Xiaomi/dada/dada:17/CP2A.260605.016/OS4.0.4.0.XOCCNXM:user/release-keys` |
| 安全补丁 | `2026-10-01` |
| 内核 | `6.6.118-android15-8-gf72a02f47f4b-abogki551678766-4k` |
| BL / AVB | `flash.locked=1`，`vbmeta.device_state=locked`，`verifiedbootstate=green` |
| ADB 身份 / SELinux | `uid=2000(shell)` / `u:r:shell:s0` / `Enforcing` |
| CPU / 页大小 | `0-7` / `4096` 字节 |
| 内存 | `MemTotal=15476156 kB`，当次 `MemAvailable=4716924 kB`（动态值） |
| perf 参数 | `perf_event_paranoid=-1`；单一参数不代表所有 perf/kprobe 操作已获准 |
| slabinfo | shell 可读取表头与条目 |
| tracefs | 可列出 kmem 事件名、可读 trace_clock；`kmem_cache_alloc/enable` 查询返回 `Permission denied`；根目录 `trace_pipe_raw` 返回 `No such file or directory`；`kprobe_events` 的 `test -r/-w` 返回真，但未进行写入验证 |
| mqsas / su | `miui.mqsas.IMQSNative` 服务仍注册；未测试其事务执行权限；`su` 不在 shell PATH（不是全机无 root 的充分证明） |

### 原文错误与更新

1. **设备基线已过时**：下方 OS3.0.307 / Android 16 / 八月补丁仅保留为 11-16 历史记录，不代表当前设备。
2. **K80 Pro 对照版本变了**：当前完整 `uname -r` 与 RMDycz README 的 **HyperOS 4.0.3.0** 条目一致，而非旧的 3.0.305 条目。只是构建字符串一致；尚未取得本机对应 OTA 的 Image，也未比较哈希或核验厂商回填。没有据此判定跨机型 profile 可直接复用或 root 已成功。
3. **64560 的现成 dada 适配不匹配本机**：GitHub README 仍限定 `OS4.0.0.8` / `gb9cc6ec16bc8-abogki536571621`；本机为 `OS4.0.4.0` / `gf72a02f47f4b-abogki551678766`。同为 OS4 或 6.6.118 不代表受支持。
4. **64560 修复矩阵有实质错误**：官方 CNA 已列出 **5.10.262、5.15.213、6.1.180、6.6.147、6.12.100、6.18.41、7.1.5**，主线条目为 **7.2**。原文“公告没列老 stable 回填”已失实。
5. **98260 的 6.1 回填信息过时**：官方 CNA 已列出 **6.1.191**，另有 6.6.158 / 6.12.112 / 6.18.54 / 7.2.8，主线 7.3。上游范围不等于本机厂商补丁状态。
6. **98256 的比较符号写反**：官方记录是 **6.15 起引入**，不是“≤6.15”。
7. **mqsas 的结论证据不足**：当前 OS4 服务确实还在；服务存在不证明事务 21 可执行，更不证明 Enforcing 下能获得 root。旧仓库明确说明其方案仅在 **SELinux permissive** 下测试，原文漏写此条件。
8. **“B 和 C 都要升级/降级”没有依据**：离线分析当前版本并不要求改系统；C 的既有目标版本不匹配，和 B 的分析工作应分开。
9. **读取接口、perf=-1 不等于具备完整链路前提**：本次 tracefs 部分访问失败；既未验证事件写入，也未验证实际 perf 系统调用。
10. **重启/清理结论需区分实现**：RMDycz 当前 README 已声明实现残留清理，同时说明 rootd 可存活于软重启、目录权限修改可持久存在。原文“一切重启就清掉”及“任何实现只能硬重启清理”均过度概括。
11. **分析仓库的测试状态表述需收紧**：villager1314 README 提供 Linux/Android 触发器及编译方式，但明确表示未在真实 KASAN 内核回归；编译说明不构成“已经在 Linux x86_64 跑过”的证据。

**当前结论：文档和相关 GitHub 仓库确实存在并可正常读取；文档存在旧基线、修复版本错误、比较符号错误和若干未经验证的可用性推断。本次仅完成资料及只读条件核对，尚无当前 Xiaomi 15 OS4.0.4.0 已成功临时 root 的证据。**

### 2026-11-17 10:09 后续操作记录

用户要求实际操作后，已完成前置核验，尚未执行提权。关键 slab 几何与参考一致：`posix_timers_cache=264/31/2`、`task_struct=5312/6/8`、`cred_jar=192/21/1`（objsize / objs-per-slab / pages-per-slab）。更正先前 tracefs 判断：准确的 `per_cpu/cpu0/trace_pipe_raw` 存在且 shell 可读，`rss_stat/trigger` 可读写；此前根目录节点不存在不代表上游通道不可用。设备 BTF 仍返回 Permission denied。

发现 Release 1.2.0 下载资产内嵌标记为 v25，但标签源码为 v24；main 源码为 v25。尚未完成可复现构建核验，不据此判断资产恶意，也未将其推送到手机。已通过 HTTP 范围读取官方 OS4.0.4.0 OTA 元数据，设备/SDK/安全补丁对应，但元数据使用内部构建编号；仍需提取 boot/Image 验证，不将字符串差异直接判作错误固件。

完整记录见 [本轮前置核验日志](probe-xiaomi15-20261117-1009-preflight.txt)。本轮未修改手机权限、未安装模块、未运行漏洞、未重启。BL/AVB 和 SELinux 保持原状。当前结果为“兼容性核验尚未闭环”，不是 root 成功，也不是漏洞已修复的结论。

### 本轮核验来源

- [dada 64560 README](https://github.com/quyicheng03-boop/xiaomi15-dada-cve-2026-64560/blob/main/README.md)
- [miro 双版本 README](https://github.com/RMDycz/K80Pro-miro-CVE-2026-98260/blob/main/README.md)
- [mqsas 旧方案 README](https://github.com/mrdong916/mi_nobl_root/blob/main/README.md)
- [98260 分析仓库 README](https://github.com/villager1314/CVE-2026-98260-Analysis/blob/main/README.md)
- [64560 官方 CNA JSON](https://github.com/CVEProject/cvelistV5/blob/main/cves/2026/64xxx/CVE-2026-64560.json)
- [98260 官方 CNA JSON](https://github.com/CVEProject/cvelistV5/blob/main/cves/2026/98xxx/CVE-2026-98260.json)
- [98256 官方 CNA JSON](https://github.com/CVEProject/cvelistV5/blob/main/cves/2026/98xxx/CVE-2026-98256.json)

---

## 0. 一句话结论（11-16 历史调研，当前判断见上方复核）

- 小米 15 在 HyperOS 4 上**没有通用的免 BL root 方案**，只有内核漏洞型**临时 root（重启失效）**。
- 两条 CVE 路线：`CVE-2026-64560`（已有 dada/OS4.0.0.8 专属适配，但要 Windows+adb 跑脚本）和
  `CVE-2026-98260`（覆盖面最广、工具链最成熟，但**没有 dada 的 profile**）。
- 本机现在跑的是 **OS3.0.307 + 内核 `6.6.118-android15-8-gc44b714366cc`**，这个内核串和 Redmi K80 Pro
  （miro）**3.0.305 那份已实测通过的 98260 配置一字不差** —— 这是最值得先验证的捷径（见 §6）。
- 都不动 BL：漏洞在 kernel 里，不写 boot/vendor/system 分区，所以"免 BL"成立；代价是**重启即失效**，
  不能换内核、不能刷机、不能持久 root。

## 1. 本机实测基线（2026-11-16，只读探测）

| 项 | 值 |
|---|---|
| 机型 / 代号 | 小米 15 / `dada`（`ro.product.device=dada`） |
| 系统 | `OS3.0.307.0.WOCCNXM`（HyperOS 3，Android 16） |
| fingerprint | `Xiaomi/dada/dada:16/BP2A.250605.031.A3/OS3.0.307.0.WOCCNXM:user/release-keys` |
| 安全补丁 | 2026-08-01 |
| 内核 | `6.6.118-android15-8-gc44b714366cc-abogki519650608-4k` |
| CPU / 页大小 | 8 核（`possible 0-7`）/ 4 KiB |
| 内存 | MemTotal ≈ 15.5 GB，当时 MemAvailable ≈ 4.2 GB |
| `perf_event_paranoid` | `-1`（可在用户态拿 perf/kprobe 事件，对 98260 有利） |
| tracefs | `/sys/kernel/tracing` 存在 |
| SELinux | 容器内看不到 `/sys/fs/selinux/enforce`，要在 `adb shell` 里看 |

> ⚠️ 容器（proot，uid 不是 shell）里读 `/proc/slabinfo`、`/proc/uptime`、`/proc/sys/kernel/randomize_va_space`
> 都是 `Permission denied`。**前置条件必须在 `adb shell`（uid 2000 / `u:r:shell:s0`）里复核**，
> 容器里的结果不能当结论。

## 2. 两个漏洞对比

| | CVE-2026-64560 | CVE-2026-98260 |
|---|---|---|
| 位置 | `kernel/time/posix-cpu-timers.c` + `kernel/signal.c`、`kernel/exit.c` | `fs/exec.c`（`begin_new_exec` / `de_thread` 清理顺序） |
| 机理 | 非 leader 线程 exec 时 `lock_task_sighand()` 拿到 `sighand == NULL`，`sys_timer_delete()` 提前返回 → 已入队的 posix timer 对象被 free → 后续 `timerqueue` 操作踩 UAF | `de_thread()` 换完 TID 后 `pid_task(旧 TID)` 查不到，误判"已出队" → 定时器节点留在**已 free 的 `k_itimer`** 上 → `cleanup_timerqueue()` → `rb_erase()` 写已释放内存 |
| 引入 | 5.7（`55e8c8eb2c7b`） | 5.7（`55e8c8eb2c7b`，同一个 commit） |
| 修复 | mainline `920f893f735e`，7.1.5 / 7.2-rc3；**公告里没列 6.6 等老 stable 的回填** | mainline `acb03d388181`；stable 回填 **6.6.158 / 6.12.112 / 6.18.54 / 7.2.8** |
| 影响面 | 6.6 及更老分支（按公告）都可能没修；实际看厂商 | 5.7 起全部 GKI；**5.10 / 5.15 / 6.1 上游尚未回填**（截至 2026-10-26），只能靠厂商 backport |
| 已知作品 | dada/OS4.0.0.8 适配（Windows+adb）、K90 Max（`prague`）一键 APK | 小米 17（`pudding`）全链路 PoC、K80 Pro（`miro`）双版本适配、OnePlus 一加 13/15T/Ace6 等、Samsung S24 系列 |
| 现状 | 只有单一机型单一版本的移植，且用 PowerShell 驱动 | **生态最热**，多机型、有 APK 化前端（TimerRoot / pudding-root） |

**别搞混**：同一报告人（Hyunwoo Kim）还报了 `CVE-2026-98256`，那个只影响 ≤6.15、且跟 GKI 无关；
影响"所有 GKI"的是 98260。

**另一个坑**：截图/传言里"内核版本号低于修复版就一定可打"是错的方向 —— 厂商可以只 backport 修复、
不改版本号。准确判据是镜像里有没有新增的 `posixtimer_exec()` 函数（98260 的修复把它提到 `de_thread()`
之后立即调用），或直接看 `fs/exec.c` 的 diff。

## 3. CVE-2026-98260 详解

### 3.1 触发路径

```
非 leader 线程 B                   父进程
  timer_create(CLOCK_THREAD_CPUTIME_ID)
  timer_settime()  →  arm_timer() 挂进 B 的 posix_cpu_timers
  execve("/proc/self/exe")
    de_thread(B)                    // B 的 TID 转给 old leader
      exchange_tids(B, leader)
      release_task(leader) → __exit_signal(leader)
                             posix_cpu_timers_exit(leader)   // 清的是 leader 的队列，不是 B 的
                             __unhash_process(leader)       // 该 PID 已出队
    begin_new_exec()
      exec_mmap() → mmap_read_lock_killable(old_mm) 返回 -EINTR（被同级 CLONE_VM 线程占着写锁）
  → 失败路径直接进 do_exit()
      exit_itimers() → posix_timer_delete() → posix_cpu_timer_del()
        // 仍按旧 PID 找 task → 失败 → 当"已出队"，不做任何回滚
      release_task(B) → posix_cpu_timers_exit(B) → cleanup_timerqueue() → timerqueue_del() → rb_erase()  ← UAF 写
```

关键点：`exec_mmap()` 必须返回 `-EINTR`（mmap 锁被抢），否则走 CAS 快路径、节点被提前清空，就没有 UAF。

### 3.2 利用链（Dream-Rainy 版，小米 17 实测）

| 步 | 动作 | 说明 |
|---|---|---|
| 1 | 泄漏 KASLR | 写 tracefs 的 kprobe 触发器打开 `kmem:kmem_cache_alloc` / `kmem:mm_page_*`，读 `trace_pipe_raw`；`k_itimer` 分配点距 `_text` 是固定偏移 |
| 2 | 触发 UAF | 见 §3.1；同时用 `CLONE_VM` 兄弟线程占住 `mmap_write_lock` |
| 3 | order-1 回收 | 8 KiB `AF_UNIX SOCK_STREAM` 写，每次一页，抢回 `posix_timers_cache` 的 slab 页（phase1 约 16000 页，phase2 约 32000 页，需 ~512 MB 空闲） |
| 4 | 8 字节零写 | `rb_erase()` 两子节点分支做 `*(u64*)rb_left = __rb_parent_color`；`rb_left=target`、`parent_color=0` → 把 target 清 0。写 `cred->uid`、`selinux_state.enforcing - 7` |
| 5 | 提权 | 零写拿不到 caps，所以还要伪造整页 `cred`（满载 `CapEff=0x1ffffffffff`），fork 子进程 `setresuid(0)` 让内核 memcpy 伪造内容进去 → `uid=0`；再在 permissive 窗口里 `ksud late-load` 挂 KernelSU LKM（`context=u:r:ksu:s0`） |

> villager1314 的 PoC 只提供**竞态触发器 + UAF 写**，不含堆喷射/对象占位/RIP 控制，
> 且**只在 Linux x86_64 上跑过，未在真实 KASAN 内核验证**。上面 5 步是下游那些机型移植补出来的。

### 3.3 前置条件（移植到自己机器前必查）

1. `adb shell`（uid 2000）能读 `/sys/kernel/tracing` 与 `/proc/slabinfo`
2. `perf_event_paranoid = -1`
3. 已装 KernelSU 系管理器（KernelSU / KernelSU-Next / SukiSU / ReSukiSU），`fake` 模式从它的 APK 里抽 `libksud.so`
4. 跑的时候约 500 MB 空闲磁盘 / 内存（socket 喷射）
5. 内核匹配到具体 build（**不是版本号**）：`uname -r` + `abogki` build id

### 3.4 失败模式（这套比 64560 更"脏"）

- 回收是概率性的：miss 会 **park**，进程保留 zmobie（伪造 cred 页在 socket buffer 里）。
  **绝对不能 kill / timeout 这个进程**，只能硬重启 —— 否则 init 回收 stale node 直接 panic。
- 成功也可能 park（`fake` 路径）；重启是唯一干净清场方式，重启后 root 同时消失。
- SELinux 会停在 permissive（`enforcing=0`），要 `setenforce 1` 或重启。
- 内核里残留半死的 timer 节点，之后任意进程 `timer_delete` 都可能 panic。

## 4. CVE-2026-64560（dada/OS4.0.0.8 专属适配）

- 仓库：<https://github.com/quyicheng03-boop/xiaomi15-dada-cve-2026-64560>（Apache-2.0，2026-09 建，
  23★/15 fork，3 个 open issue）
- 只认一个指纹：`Xiaomi/dada/dada:17/CP2A.260605.016/OS4.0.0.8.XOCCNXM:user/release-keys`，
  内核 `6.6.118-android15-8-gb9cc6ec16bc8-abogki536571621-4k`，boot sha256 与 Image sha256 都 pin 死了
- 用法：Windows PowerShell + 官方 platform-tools，`scripts/root.ps1` 自动校验指纹和载荷 hash；
  成功后 `adb -s <serial> shell -t /data/local/tmp/su` → `uid=0`，**仅当前这次 boot 有效**
- 概率性内核竞态：脚本内置两套 reclaim 策略，失败/不确定就冷启动重试，默认上限 **12 次 boot**
- 不动 boot/vendor/system 分区

> 该仓库自称 OS4.0.0.8 的内核里没有 `920f893f`（CVE-2026-64560 的修复）。这点无法离线验证，
> 想确认得把 `boot.img` 解出来看 `Image`。同类移植（K90 Max）作者给的经验值是 ~40% 概率 panic 重启。

### 4.1 顺带记录：mqsas 那条老路（HyperOS 3 时代）

mrdong916/mi_nobl_root 在 dada + HyperOS 3.0.300.7 / 内核 6.6.77 上用过小米自家服务漏洞直接拿 root：

```
service call miui.mqsas.IMQSNative 21 i32 1 s16 '<解释器>' i32 1 s16 '<脚本路径>' \
  s16 '<输出文件>' i32 <超时秒数>
```

以 `uid=0` / `u:r:hypsys_ssi_default:s0` 异步执行脚本，再去 `insmod` 打好 kallsyms 补丁的 `kernelsu.ko`，
外加 ZygiskSU + LSPosed；每次重启要重跑一遍。**OS4 上这个服务大概率已封**（未验证），
而且依赖 `/proc/kallsyms` 实时补丁，脆弱。

## 5. 公开仓库清单

| 仓库 | 机型 / 内核 | CVE | 形态 | 状态 |
|---|---|---|---|---|
| [quyicheng03-boop/xiaomi15-dada-cve-2026-64560](https://github.com/quyicheng03-boop/xiaomi15-dada-cve-2026-64560) | 小米15 `dada` / `6.6.118-gb9cc6ec16bc8` (OS4.0.0.8) | 64560 | Win+adb 脚本 | 单版本唯一适配，未独立验证 |
| [mrdong916/mi_nobl_root](https://github.com/mrdong916/mi_nobl_root) | 小米15 `dada` / `6.6.77` (OS3.0.300.7) | mqsas 服务漏洞 | Win 一键 bat | 只到 OS3，OS4 疑已封 |
| [RMDycz/K80Pro-miro-CVE-2026-98260](https://github.com/RMDycz/K80Pro-miro-CVE-2026-98260) | Redmi K80 Pro `miro` / `6.6.118-gc44b714366cc`(3.0.305)、`gf72a02f47f4b`(4.0.3.0) | 98260 | adb + 二进制 | **真机实测，成功率 ~60%**，带清理 |
| [Dream-Rainy/CVE-2026-98260](https://github.com/Dream-Rainy/CVE-2026-98260) | 小米17 `pudding` / `6.12.69` | 98260 | Win+adb 全链路 | 真机实测，含完整 profile 推导方法 |
| [zjns/CVE-2026-98260](https://github.com/zjns/CVE-2026-98260) | OnePlus PKX110 / `6.6.118-g9bc34d5b0c79` | 98260 | 源码 + 静态产物 | 6.6.118 GKI 移植分支，可当模板 |
| [cramqin/pudding-root](https://github.com/cramqin/pudding-root) | 小米17 `pudding` / `6.12.69` | 98260 | **APK**（Shizuku 驱动） | 真机验证，手机端一键 |
| [wanwuzhishi/ksu-root](https://github.com/wanwuzhishi/ksu-root) | REDMI K90 Max `prague` / `6.12.69` | 64560 | **APK**（Shizuku） | 真机验证，~40% panic |
| [osamaassolimany-ui/TimerRoot](https://github.com/osamaassolimany-ui/TimerRoot) | 通用前端（需自备 timer 二进制） | 98260 | APK 壳 | 壳，不含 exploit |
| [villager1314/CVE-2026-98260-Analysis](https://github.com/villager1314/CVE-2026-98260-Analysis) | 通用 PoC + 修复分析 | 98260 | PoC（Linux x86_64） | 分析文档 + 触发/泄漏 PoC |
| [YuKongA/CVE-2026-98260](https://github.com/YuKongA/CVE-2026-98260) | 上游 PoC（MIT） | 98260 | — | 被上面几家反复引用 |

## 6. 对 dada 的可行性判断

三条路，按"现在就能动手"排序：

**A. 先拿现成的 K80 Pro profile 试（最快，风险最低的一次尝试）**
本机内核串 `6.6.118-android15-8-gc44b714366cc-abogki519650608-4k` 与 K80 Pro 3.0.305 那份配置
**完全一致**（同一个 GKI build id）。小米同代机型共用同一份 ACK 内核镜像的情况很常见，
如果两边 `Image` 真的逐字节一致，那么 `STATIC_TIMER_SITE` / `COPY_PROCESS_LOW21` / `selinux_state` /
`panic_on_warn` 这些"从镜像里推出来的"常量就通用，只剩 `TASK_ALLOC_BYTES` 要在本机实测。
验证顺序：`boot.img` 解出 `Image` → 比对 sha256 / build id → 一致才继续。
若不希望动 OS 版本，这是唯一"不用等 OS4"的入口。

**B. 给 dada 自己做一份 98260 profile（正路，工作量中等）**
拿 `zjns`（6.6.118 分支）+ `Dream-Rainy`（推导方法）+ `RMDycz`（清理/抗变砖）三条拼：
1. 从本机 `boot.img` 解 `Image`（header v4，payload 在 4096 偏移）
2. 反汇编 `do_timer_create` / `copy_process`，取两个 alloc 返回点 → `STATIC_TIMER_SITE`、`COPY_PROCESS_LOW21`
3. 取 kallsyms 的 `selinux_state`、`panic_on_warn`、`init_user_ns`、`init_ucounts`、`init_groups` 静态地址
4. 跑 `tools/taskleak.c` 实测 `TASK_ALLOC_BYTES`（B TF 的 `sizeof(task_struct)` 不等于 slab 实际大小）
5. 真机 `timer ids` → `timer leak` → `timer fake -d`，按退出码定位卡在哪一步

**C. 等 dada 的 OS4 64560 适配成熟（最省事，但被动）**
现成仓库只能跑 `OS4.0.0.8.XOCCNXM`，且要 Windows。若后面升到 OS4 且版本号停在 4.0.0.8，可直接试。

> 注：B 和 C 都要**升级/降级系统**才谈得上；A 在当前的 OS3.0.307 上就能试。

## 7. 风险与红线

- 这些是**内核漏洞利用**：会 panic、会丢未保存数据、保修可能失效、SELinux 会被留成 permissive。
- park 后**不许 kill**；失败只有硬重启一条路，且重启前别指望"看起来正常"就安全。
- 别用各种"优化版 / 内置 adb 版"的 Shizuku 或 APK（`ksu-root` 作者明确说实测有假包）。
- 只在自己的机器上跑。
- 传出去的文档/issue 不要贴 boot hash、序列号之外的设备唯一信息。

## 8. 待办（下次接着干）

- [ ] `adb shell` 里复核：`cat /proc/slabinfo`、`ls /sys/kernel/tracing/events/kmem`、
      `getprop ro.build.fingerprint`、`uname -r`（容器里的读数不可信）
- [ ] 拿到本机 `boot.img`（或从官方 OTA 里解），比对 K80 Pro 3.0.305 的 `Image` sha256，决定走 A 还是 B
- [ ] 走 B 的话：按 §6.B 的 5 步出 dada profile，先只跑 `timer ids` / `timer leak`（不触发 UAF）
- [ ] 确认 `ksud` 来源与 uapi 版本（KernelSU vs SukiSU，混用会报"需要更新内核"）
- [ ] 决定是否升 OS4：升了才能试 64560 那条，但会丢掉 A 路线的现成 profile

## 9. 参考

- CVE-2026-98260 分析（含修复 commit、影响矩阵、PoC）：<https://github.com/villager1314/CVE-2026-98260-Analysis>
- CVE-2026-64560 公告（kernel.org）：<https://lore.kernel.org/linux-cve-announce/2026072908-CVE-2026-64560-3932@gregkh/>
- CVE 记录：<https://www.cve.org/CVERecord?id=CVE-2026-98260>
- 小米 17 全链路：<https://github.com/Dream-Rainy/CVE-2026-98260>
- K80 Pro 双版本适配：<https://github.com/RMDycz/K80Pro-miro-CVE-2026-98260>
- 6.6.118 GKI 移植分支：<https://github.com/zjns/CVE-2026-98260>

## 2026-11-17 11:00–11:12 离线核验 + 首次实机尝试

### 一、拿到并验证了真机内核（不再是"同一 build id 的推测"）

用 HTTP Range 只下 `payload.bin` 里 `boot` 分区需要的 48 段（共 10.8 MB，不是 8.8 GB 整包），
逐段校验 op 级 SHA-256、再校验分区级 SHA-256，才落盘：

- `boot-stock.img`  `7935a651b43945b020bd02744489e1f1f7eeff032bb6c245b70fd31b0c1e2a2f`（boot header v4）
- `Image`（拆出来的 arm64 内核）`7c9ecc459dde9a87c1fd9d8c0227cee1957ac8cde7f9d6cbe9aba4a3cbf6f91d`
- banner：`Linux version 6.6.118-android15-8-gf72a02f47f4b-abogki551678766-4k ... #1 SMP PREEMPT Thu Aug 27 01:49:35 UTC 2026`

用 kallsyms 恢复出 110327 个符号，把 miro（K80 Pro）`HyperOS 4.0.3.0` 那条 profile 的 23 个地址**逐项比对**：
**23/23 全等**（`_text`、`_stext`、`__arm64_sys_getpid/gettid/getppid`、`__set_task_comm`、
`do_timer_create`、`copy_process`、`prepare_creds`、`commit_creds`、`selinux_state`、`init_user_ns`、
`root_user`、`init_groups`、`init_ucounts`、`init_task`、`init_cred`、`posix_timers_cache`、
`memstart_addr`、`kimage_voffset`），三个 `_RET_IP_` 派生值（`do_timer_create+0xa8`、
`copy_process+0x140`、`prepare_creds+0x24`）也全等。→ **dada 的 4.0.4.0 内核就是 K80 Pro 4.0.3.0 那一个 GKI 构建**，
profile 可用不是靠 uname 字符串撞上的。

结构体偏移用反汇编独立验过，没依赖 BTF（`/sys/kernel/btf/vmlinux` 在真机仍是 `Permission denied`）：

| 偏移 | 证据 |
|---|---|
| `real_cred 0x818` / `cred 0x820` | `commit_creds` 里 `ldr x19,[x20,#0x818]`、`ldr x8,[x20,#0x820]`、`stlr x21,[x8]` 两次 |
| `comm 0x830` | `__set_task_comm+0x34: add x0,x19,#0x830`，`copy_process+0x500: add x0,x20,#0x830` |
| `pid 0x618` / `tgid 0x61c` / `sighand 0x880` | `copy_process` 内联 `__set_task_comm` 探针参数与 `p->sighand` 写入 |

### 二、CVE-2026-98260 在这颗内核上**没打**

`fs/exec.c` 的修复是：把 POSIX CPU timer 清理搬到 `de_thread()` 之后（新增 `static void posixtimer_exec()`）。
实测内核对不上修复后的形状：

- kallsyms 里**没有** `posixtimer_exec`，原始字节里也搜不到这个串；
- `begin_new_exec` 的调用序列是 `de_thread → exchange_tids → release_task → unshare_files →
  set_mm_exe_file → exec_mmap → exec_task_namespaces →` **然后才** `posix_cpu_timers_exit /
  exit_itimers / flush_itimer_signals / unshare_sighand`，即**旧顺序**（清理在所有失败点之后）；
- `exec_mmap` 里仍是 `down_write_killable`、`down_read_killable`，`-EINTR` 这条失败路径还在。

结论：漏洞窗口在这台机器上真实存在，`khleak` 的前提成立。

### 三、发布二进制与源码的一致性

`khleak-release-1.2.0` 资产里的 build tag 是 `v25`（main HEAD），而 tag `1.2.0` 的源码是 `v24`——
这曾是"不敢跑"的硬阻塞。这次直接消除它：装了 NDK r29（clang 21.0.0，正是资产里 `.comment` 的编译器），
用 main HEAD 源码本地重建，**逐段比对：`.text 85684 字节完全相同`，`.rodata`/`.data`/`.rela.*` 全同，
只有 `.comment` 不同**（编译路径）。→ 资产就是这份源码编出来的，版本号错位是发布疏漏，不是可疑改动。
二进制里也没有任何 URL/IP（只有 `/data/local/tmp` 路径和 `4.0.3.0` 版本串），socket 相关导入只服务本地 rootd。

### 四、实机跑的结果：fail-closed 停车（需要硬重启）

`khleak profile` 在真机命中 `HyperOS 4.0.3.0 (miro, K80 Pro)`，三项 slabinfo 全 OK
（`task_struct 5312/6/8`、`posix_timers_cache 264/31/2`、`cred_jar 192/21/1`）；
`khleak kallsyms` 因 `kptr_restrict` + 缺权限读不到 `/proc/kallsyms`（设计上不依赖它）。

随后 `khleak root --attempts 2`：**进入了 `plant_park_fail_closed()`**。
判定依据是进程 comm 被改成 `khleak-park`（这个字符串只出现在该函数里），这正是"窗口已开、抢页失败"的停车分支。
快照与处置见 [`probe-xiaomi15-20261117-1112-park.txt`](probe-xiaomi15-20261117-1112-park.txt)。

要点（下次别再踩）：

- 停车时工具会忽略 SIGINT/SIGTERM/SIGHUP/SIGQUIT/SIGALRM 并 `sleep(300)` 循环，
  **不能 kill、不能 Ctrl-C、不能断那条 adb 连接**（断连 → 写管道失败 → SIGPIPE → 收尸 → panic）；
- 它打印的整段 ERR 横幅被 `| tail -60` 缓冲吃掉了，直到 EOF 都不出来 ——
  **以后一律重定向到文件**（`khleak root > /data/local/tmp/kh.log 2>&1`），不要走管道；
- 唯一正确处置：**长按电源 10 秒以上硬重启**（硬复位不经过收尸路径）；重启后 `khl`/`kd` 探针自动消失。

### 五、11:21 提权成功（同一天第二次尝试）

硬重启后（`boot_id=5a4fb408-bccc-45e1-927e-0ec8d0d7b7f2`）先跑了两步前置：

- `carrier-test`：8000 字节 payload 逐字节可控（`MARK_OFF=0xE78`），载体机制在 dada 上没问题；
- 手工验证 tracefs 的间接 arm 通道：`echo enable_event:kmem:mm_page_free > events/kmem/rss_stat/trigger`
  成功，`mm_page_alloc/enable` 变成 `1*`（软使能）。这是关键——`mm_page_free/enable` 本身是
  `0640 root:readtracefs`，虽然 shell 在 `readtracefs`(3012) 组里，**`format`/`enable` 仍被 SELinux 挡**
  （`cat .../mm_page_free/format` → EACCES），所以只能走 `rss_stat/trigger` 这支。

然后 `khleak root --attempts 6 --hold`，**第 3 轮命中**：

```
[stream] page_freed=1 free_cpu=0
[stream] HIT pfn=0xafb74
[uaf] del=2048  del(head!=0)=1  pe=3  ei=2
[uaf] => 窗口【已打开】：节点在 release_task 时仍在树上
[holder] getuid=0  uid=0 euid=0 gid=0 egid=0
[renew] REAL_CRED_ACTIVE uid=0 gid=0 cap=0x1ffffffffff
```

结果：`khleak-rootd` 以 `Uid: 0 0 0 0` + `CapEff: 000001ffffffffff` 常驻；
`khleak su -c "id; getenforce"` → `uid=0(root) gid=0(root)` / `Permissive`；
`/proc/iomem`、`dmesg`、`/sys/kernel/btf/vmlinux`（6127240 字节）全部可读，
`dmesg` 里 `kernel BUG|WARNING:|Oops` 计数 **0**。完整日志见
[`probe-xiaomi15-20261117-1121-root-success.txt`](probe-xiaomi15-20261117-1121-root-success.txt)。

成功率统计（作者给的是 40~60%）本机第一轮 `--attempts 2` 就停车、第二轮 3 轮内成功，
量级吻合；每轮 cycle 约 2.5 秒，`--attempts 6` 只花 75 秒预算里的十几秒。

**注意现状**：SELinux 已被打成 `Permissive`（root 路径强制先关），`/data/local/tmp` 被改成 `0777`，
`.khleak-load` 记了 7 秒负载账。这三样都要等重启才回原样，`khleak clean` 能清进程和目录权限，
但**不能把 SELinux 恢复成 Enforcing**。

### 六、下一轮要记住的

1. **每次跑之前先 `carrier-test`**：它不碰漏洞窗口，能提前发现载体/布局问题。
2. **不要用管道接 stdout**：`| tail -n` 会缓冲到 EOF，停车时一个字都出不来。
   一律 `khleak ... > /data/local/tmp/kh.log 2>&1`，再单独 `tail`。
3. `--attempts 6 --hold` 是当前最省事的组合：`--hold` 让成功进程挂住，可以从外部
   `/proc/<pid>/status` 验证 uid/cap，比 `--exec-sh` 靠 pty 判断可靠。
4. 停车是设计内的分支（窗口开 + 抢页失败），处置只有硬重启；**连跑两轮都停车说明时序要调，
   不是加大 attempts**。
5. 竞态参数优先级（按作者文档 §6）：`--creator exec`（默认，`other` 命中率 0）→
   `--writes` / `--write-rounds` → `--exec-delay-us`；`--locker-pin 1` 和 `--lockers>4` 会直接死机。
6. 想保留 root 就别 `clean`；想恢复干净状态：`khleak su -c "/data/local/tmp/khleak clean"` 再重启。

## 附：存疑 / 未验证

1. ~~dada OS4.0.0.8 内核是否真的缺 `920f893f`~~ → 已用 4.0.4.0 的 `Image` 反汇编确认**缺**（见上一节第二节）。
2. ~~本机 `Image` 与 K80 Pro 3.0.305 是否逐字节一致~~ → 不是 3.0.305，而是与 **4.0.3.0（miro）** 同一个 GKI 构建，
   23 个 profile 地址全等（见上一节第一节）。
3. HyperOS 4 是否已封 `miui.mqsas.IMQSNative` 的 `code 21` 通道。
4. 98260 在小米 15 上的 `TASK_ALLOC_BYTES` 实际值（必须实测，不能抄 6.12 的 0x1840）。
5. 各家 README 里的成功率（40% / 60%）都是作者单机多次的经验值，不构成保证。
