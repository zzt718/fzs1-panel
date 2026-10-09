#!/bin/sh
# ---------------------------------------------------------------------------
# 本地交叉编译 fzs-atio → 直接产出到 ipk 的 data/usr/bin/（打包即可用）
#
# 为什么用 Zig 而不是 OpenWrt SDK：
#   本机是 Windows，SDK 是 Linux ELF 可执行文件（跑不了，WSL 也被安全策略禁）；
#   Zig 是 Windows 原生、自带 musl 交叉编译能力，一条命令出静态二进制，零环境配置。
#   Zig 通过 pip 装：pip install ziglang（走 PyPI 镜像，WiFi 下 5MB/s）
#
# ★ 注意：WorkBuddy 沙箱会挡住 Zig 子进程读取 site-packages 里的 lib（AccessDenied），
#   所以本脚本要在"关闭沙箱"的前提下调用；缓存目录也指到可写位置。
# ---------------------------------------------------------------------------
set -e

HERE=$(cd "$(dirname "$0")" && pwd)
SRC="$HERE/fzs-atio.c"
OUTDIR="$HERE/../luci-app-fzs/data/usr/bin"
OUT="$OUTDIR/fzs-atio"
TARGET="mipsel-linux-musleabi"
PY="/c/Users/zzt/.workbuddy/binaries/python/envs/default/Scripts/python.exe"

[ -f "$SRC" ] || { echo "[build] 找不到源码 $SRC" >&2; exit 1; }
mkdir -p "$OUTDIR"

# ★ 缓存目录必须是 Windows 风格路径：zig 是原生 Windows 程序，不认 /c/... 这种 POSIX 路径。
#   路径不对时它会读不到自己的 std 库，报 "unable to load 'std.zig': AccessDenied"。
WINTMP=$("$PY" -c "import tempfile,os;print(tempfile.gettempdir().replace(os.sep,'/'))" 2>/dev/null)
[ -n "$WINTMP" ] || WINTMP="C:/Users/zzt/AppData/Local/Temp"
export ZIG_GLOBAL_CACHE_DIR="${ZIG_GLOBAL_CACHE_DIR:-$WINTMP/zigcache}"
export ZIG_LOCAL_CACHE_DIR="${ZIG_LOCAL_CACHE_DIR:-$ZIG_GLOBAL_CACHE_DIR/local}"
mkdir -p "$ZIG_GLOBAL_CACHE_DIR"

echo "[build] target=$TARGET"
echo "[build] out=$OUT"

if command -v zig >/dev/null 2>&1; then
    zig cc -target "$TARGET" -Os -static -s -o "$OUT" "$SRC"
else
    "$PY" -m ziglang cc -target "$TARGET" -Os -static -s -o "$OUT" "$SRC"
fi

ls -l "$OUT"
echo "[build] 完成 —— 接着跑 build_ipk.py 打包即可"
