# -*- coding: utf-8 -*-
"""把仓库根目录的 LICENSE 推到 GitHub（只传这一个文件，不动仓库其它内容）。
令牌复用 ../fzs1_decloud/.github_token（KEY=value 格式，绝不打印令牌本体）。
用法：python src/push_license.py
"""
import base64, json, os, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OLD = r"C:\Users\zzt\.zcode\workspace\default\fzs1_decloud"
OWNER, REPO = "zzt718", "fzs1-panel"
PATH_IN_REPO = "LICENSE"
LOCAL = os.path.join(ROOT, "LICENSE")
COMMIT_MSG = "Add GPL-3.0-or-later license"


def token(fn, key):
    for l in open(os.path.join(OLD, fn), "r", encoding="utf-8", errors="ignore"):
        l = l.strip()
        if l.startswith(key + "="):
            return l.split("=", 1)[1].strip() or None
    return None


GH = token(".github_token", "GITHUB_TOKEN")
if not GH:
    raise SystemExit("找不到 GITHUB_TOKEN")

# 不走本机那个回环代理，直连
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def api(url, method="GET", body=None):
    req = urllib.request.Request(url, data=(json.dumps(body).encode() if body else None), method=method)
    req.add_header("Authorization", "Bearer " + GH)
    req.add_header("Accept", "application/vnd.github+json")
    if body:
        req.add_header("Content-Type", "application/json")
    try:
        r = opener.open(req, timeout=30)
        return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


print("token loaded: len=%d" % len(GH))
data = open(LOCAL, "rb").read()
print("local LICENSE: %d bytes" % len(data))

url = "https://api.github.com/repos/%s/%s/contents/%s" % (OWNER, REPO, PATH_IN_REPO)
st, r = api(url)
sha = json.loads(r).get("sha") if st == 200 else None
print("remote before: %s%s" % (st, " sha=" + sha[:8] if sha else ""))

body = {"message": COMMIT_MSG, "content": base64.b64encode(data).decode()}
if sha:
    body["sha"] = sha
st, r = api(url, "PUT", body)
if st < 400:
    print("push OK -> https://github.com/%s/%s/blob/HEAD/%s" % (OWNER, REPO, PATH_IN_REPO))
else:
    print("push FAILED: %s %s" % (st, r[:300]))
