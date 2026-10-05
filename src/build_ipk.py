# -*- coding: utf-8 -*-
"""build_ipk.py — 蜂助手面板 ipk 打包器（all-arch，纯 Python，无需 OpenWrt SDK）。

用法: py -3 build_ipk.py [版本号]
输入: luci-app-fzs/control/ (control, postinst, prerm, conffiles...)
      luci-app-fzs/data/    (文件树，按绝对路径落到目标系统)
输出: dist/luci-app-fzs_<ver>_all.ipk

格式（与 mifi-at_1.0-4_all.ipk 一致）:
  gzip( tar{ ./debian-binary, ./control.tar.gz, ./data.tar.gz } )
  control.tar.gz = ./control (+postinst/prerm)
  data.tar.gz    = ./data/ 的内容
"""
import gzip, io, os, sys, tarfile, time, hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.join(HERE, "luci-app-fzs")
DIST = os.path.join(HERE, "dist")

def read_ctl(name):
    p = os.path.join(PKG, "control", name)
    return open(p, "rb").read() if os.path.exists(p) else None

def get_version():
    ctl = read_ctl("control").decode("utf-8")
    for line in ctl.splitlines():
        if line.startswith("Version:"):
            return line.split(":", 1)[1].strip()
    return "0.0.0-1"

def make_tar_gz(files_spec, arc_prefix="."):
    """files_spec: [(arcname, bytes, mode)]"""
    raw = io.BytesIO()
    t = tarfile.open(fileobj=raw, mode="w")
    for arcname, data, mode in files_spec:
        ti = tarfile.TarInfo(arcname)
        ti.size = len(data)
        ti.mode = mode
        ti.mtime = 0
        t.addfile(ti, io.BytesIO(data))
    t.close()
    return gzip.compress(raw.getvalue(), 9, mtime=0)

def walk_data(droot):
    out = []
    for root, dirs, files in os.walk(droot):
        rel = os.path.relpath(root, droot).replace("\\", "/")
        for f in sorted(files):
            fp = os.path.join(root, f)
            arc = (rel + "/" + f).lstrip("./")
            mode = 0o755 if f.endswith((".sh", "")) and os.access(fp, os.X_OK) else 0o644
            out.append(("./" + arc, open(fp, "rb").read(), mode))
    return out

def main():
    ver = sys.argv[1] if len(sys.argv) > 1 else get_version()
    ctl = read_ctl("control")
    if not ctl:
        sys.exit("control 文件不存在")
    ctl = ctl.replace(b"@VERSION@", ver.encode())
    postinst = read_ctl("postinst")
    prerm = read_ctl("prerm")

    ctl_files = [("./control", ctl, 0o644)]
    if postinst:
        ctl_files.append(("./postinst", postinst, 0o755))
    if prerm:
        ctl_files.append(("./prerm", prerm, 0o755))

    data_dir = os.path.join(PKG, "data")
    data_files = walk_data(data_dir) if os.path.isdir(data_dir) else []
    if not data_files:
        print("警告: data/ 为空 —— 只打空包（骨架验证用）")

    control_tgz = make_tar_gz(ctl_files)
    data_tgz = make_tar_gz(data_files)

    inner = io.BytesIO()
    t = tarfile.open(fileobj=inner, mode="w")
    for name, content in [("./debian-binary", b"2.0\n"), ("./control.tar.gz", control_tgz), ("./data.tar.gz", data_tgz)]:
        ti = tarfile.TarInfo(name)
        ti.size = len(content)
        ti.mode = 0o644
        ti.mtime = 0
        t.addfile(ti, io.BytesIO(content))
    t.close()
    outer = gzip.compress(inner.getvalue(), 9, mtime=0)

    os.makedirs(DIST, exist_ok=True)
    out = os.path.join(DIST, "luci-app-fzs_%s_all.ipk" % ver)
    open(out, "wb").write(outer)
    print("输出: %s (%d bytes) md5=%s" % (out, len(outer), hashlib.md5(outer).hexdigest()))

if __name__ == "__main__":
    main()
