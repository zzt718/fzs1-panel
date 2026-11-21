# -*- coding: utf-8 -*-
"""打 tag 并推送 —— Release 由 GitHub Actions 建（令牌已失效，不再走 REST API）。

用法：python src/push_release.py v0.2.10

前置：先跑 src/push_repo.py，把 ipk 提交进仓库的 release/ 目录。
      本脚本只打 tag；Actions 会把仓库里那个 ipk 挂到 Release（不重新构建）。
"""
import os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(ROOT, ".git-pub")

if len(sys.argv) < 2:
    raise SystemExit("用法: python src/push_release.py v0.2.10")
TAG = sys.argv[1]
if not TAG.startswith("v"):
    raise SystemExit("tag 需要形如 v0.2.10")
VER = TAG[1:]

if not os.path.isdir(os.path.join(WORK, ".git")):
    raise SystemExit("没有 .git-pub —— 先跑 python src/push_repo.py \"...\"")

IPK = os.path.join(WORK, "release", "luci-app-fzs_%s_all.ipk" % VER)
if not os.path.isfile(IPK):
    raise SystemExit("仓库里没有 release/luci-app-fzs_%s_all.ipk\n"
                     "先构建该版本并跑 push_repo.py（它会自动取 src/dist 最新的 ipk）" % VER)

print("附件: %s (%d B)" % (os.path.basename(IPK), os.path.getsize(IPK)))


def g(*args):
    r = subprocess.run(["git", *args], cwd=WORK, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise SystemExit("git %s 失败:\n%s\n%s" % (" ".join(args), r.stdout, r.stderr))
    return r.stdout.strip()


head = g("rev-parse", "--short", "HEAD")
g("tag", "-f", TAG)
g("push", "-f", "origin", "refs/tags/" + TAG)
print("已推送 tag %s → commit %s" % (TAG, head))
print("Actions: https://github.com/zzt718/fzs1-panel/actions")
print("Release: https://github.com/zzt718/fzs1-panel/releases/tag/%s" % TAG)
