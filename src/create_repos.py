# -*- coding: utf-8 -*-
"""Create fzs1-panel repos on Gitee + GitHub and push initial docs.
Reads tokens from ../fzs1_decloud/.gitee_token / .github_token (never printed)."""
import base64, json, os, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OLD = r"C:\Users\zzt\.zcode\workspace\default\fzs1_decloud"
REPO = "fzs1-panel"
OWNER = "zzt718"
BRANCH_GITEE, BRANCH_GH = "master", "main"

def token(fn, key):
    """token 文件为 KEY=value 格式（与 sync_repo.py 一致）"""
    raw = open(os.path.join(OLD, fn), "r", encoding="utf-8", errors="ignore")
    for l in raw:
        l = l.strip()
        if l.startswith(key + "="):
            v = l.split("=", 1)[1].strip()
            return v or None
    return None

def http(url, method="GET", body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        r = urllib.request.urlopen(req, timeout=30)
        return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")

FILES = [
    ("README.md", "docs: 项目索引"),
    ("00_时间线.md", "docs: 时间线"),
    ("需求文档.md", "docs: 需求文档"),
    ("src/build_ipk.py", "build: all-arch ipk 打包器"),
    ("src/luci-app-fzs/control/control", "build: ipk control"),
    ("src/luci-app-fzs/control/postinst", "build: ipk postinst"),
    ("src/luci-app-fzs/control/prerm", "build: ipk prerm"),
]

def read_local(rel):
    return open(os.path.join(HERE, "..", rel), "rb").read()

DESC = ("蜂助手面板 luci-app-fzs —— MIBOX-668M2 蜂窝运维 LuCI 应用：双模组状态 / "
        "锁频段·锁频点·锁小区(AT*CELL) / 短信转发 / IMEI。FZS cellular ops panel for MIBOX-668M2 OpenWrt.")

# ---------- Gitee ----------
gt = token(".gitee_token", "GITEE_TOKEN")
print("gitee token loaded:", bool(gt), "len=%d" % len(gt))
st, r = http("https://gitee.com/api/v5/user/repos", "POST",
             {"access_token": gt, "name": REPO, "description": DESC,
              "private": False, "auto_init": False, "has_issues": True})
print("gitee create repo:", st, (r[:120] if st >= 400 else "OK -> https://gitee.com/%s/%s" % (OWNER, REPO)))
for rel, msg in FILES:
    st, r = http("https://gitee.com/api/v5/repos/%s/%s/contents/%s" % (OWNER, REPO, urllib.parse.quote(rel)),
                 "POST", {"access_token": gt, "content": base64.b64encode(read_local(rel)).decode(),
                          "message": "init: " + msg, "branch": BRANCH_GITEE})
    print("  gitee push %-34s %s" % (rel, st if st >= 400 else "OK"))

# ---------- GitHub ----------
gh = token(".github_token", "GITHUB_TOKEN")
print("github token loaded:", bool(gh), "len=%d" % len(gh))
H = {"Authorization": "Bearer " + gh, "Accept": "application/vnd.github+json"}
st, r = http("https://api.github.com/user/repos", "POST",
             {"name": REPO, "description": DESC, "private": False, "auto_init": False,
              "has_wiki": False, "has_projects": False}, H)
print("github create repo:", st, (r[:120] if st >= 400 else "OK -> https://github.com/%s/%s" % (OWNER, REPO)))
for rel, msg in FILES:
    st, r = http("https://api.github.com/repos/%s/%s/contents/%s" % (OWNER, REPO, urllib.parse.quote(rel)),
                 "PUT", {"message": "init: " + msg,
                         "content": base64.b64encode(read_local(rel)).decode(),
                         "branch": BRANCH_GH}, H)
    print("  github push %-34s %s" % (rel, st if st >= 400 else "OK"))

print("\nverify:")
st, r = http("https://gitee.com/api/v5/repos/%s/%s" % (OWNER, REPO))
print("  gitee repo:", st, "full_name" in r and json.loads(r).get("full_name"))
st, r = http("https://api.github.com/repos/%s/%s" % (OWNER, REPO), headers=H)
print("  github repo:", st, "full_name" in r and json.loads(r).get("full_name"))
