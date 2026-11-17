#!/system/bin/sh
# 恢复 2026-11-17 删除的小米系统应用（仅对 user 0 生效）
# 用法（Windows/PC 侧）：
#   adb shell /data/local/tmp/khleak su -c "runcon u:r:shell:s0 sh /data/local/tmp/restore-miui-apps.sh"
# 前提：khleak root 会话存活（重启后需重新提权）

for p in \
  com.mobiletools.systemhelper \
  com.sohu.inputmethod.sogou.xiaomi \
  com.miui.personalassistant \
  com.miui.yellowpage \
  com.miui.hybrid \
  com.miui.analytics \
  com.miui.systemAdSolution \
  com.miui.guardprovider \
  com.xiaomi.macro \
  com.xiaomi.payment ; do
  echo -n "$p => "
  pm install-existing --user 0 "$p"
done
