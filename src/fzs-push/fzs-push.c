/*
 * fzs-push —— 通用 HTTP 推送工具（短信转发渠道用）
 * ============================================================================
 *
 * 为什么需要它（2026-10-07 立项）
 * ---------------------------------------------------------------------------
 * 国内主流推送渠道（钉钉 / 飞书 / 企业微信 群机器人）**都要求
 *   POST + Content-Type: application/json + JSON body**
 * 这是三家官方文档写死的标准格式，不是谁的私有约定。
 *
 * 但设备自带的 HTTP 客户端 `uclient-fetch` **把 Content-Type 硬编码成
 *   application/x-www-form-urlencoded**
 * 且没有暴露自定义 header 的参数（strings 里能看到它写死的那个串），
 * 所以「拿现成命令发 JSON」这条路是堵死的。
 *
 * 我们**不自己实现 HTTP/TLS**（重造轮子 + 要背协议栈的 bug），而是
 * **直接链接 OpenWrt 官方的 libuclient**（就是 uclient-fetch 用的那个库）。
 * 从设备上 libuclient.so 的动态符号表已确认它导出了：
 *     uclient_http_set_header       ← 自定义任意 header（含 Content-Type）
 *     uclient_http_set_request_type ← 设 POST
 *     uclient_http_set_ssl_ctx      ← HTTPS（对接 libustream-ssl + wolfssl）
 *   → **库本身支持，只是 uclient-fetch 这个命令行壳没暴露出来。**
 *     本工具只是把参数传进去的那层薄胶水，骨架（Connect/Request/uloop）
 *     严格照抄官方 uclient-fetch.c 的用法。
 *
 * 设计约束（吸取 fzs-atio 的经验）
 * ----------------------------------------------------------------------------
 * 1. **不引入新依赖**：动态链接设备已有的 libuclient.so / libustream-ssl.so /
 *    libwolfssl.so（固件自带）。**不静态编译 TLS**。
 * 2. **参数化、不写死渠道**：本工具不认识钉钉/飞书，它只做「发一个带指定
 *    Content-Type 的 POST」。**JSON 长什么样由 shell 侧（fzs-fwd）按官方
 *    文档拼好传进来** → 以后加渠道**不用重编译**，改 shell 就行。
 * 3. **退出码语义明确**：0=成功(HTTP 2xx) / 1=参数错 / 2=连接失败 / 3=HTTP 非 2xx。
 *    上层（fzs-smsd 的转发重试）据此判断成败。
 * 4. **响应体打到 stdout**：很多渠道失败也回 HTTP 200，真正的成败在 body 里
 *    （例如 `errcode != 0`）。把 body 原样输出，便于上层判断与用户排查。
 *
 * 用法
 * ----------------------------------------------------------------------------
 *   fzs-push <url> <content-type> [body]
 *   fzs-push --json <url> [body]          # content-type 预设为 application/json
 *   body 省略时从 **stdin** 读（避免命令行长度限制与引号转义问题）
 *
 * 退出码
 * ----------------------------------------------------------------------------
 *   0   成功（HTTP 2xx）
 *   1   参数错误
 *   2   连接 / 请求失败（含 TLS 失败、超时）
 *   3   HTTP 状态码非 2xx
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>

#include <libubox/uloop.h>
#include <libubox/ustream.h>
#include <libubox/usock.h>
#include <uclient/uclient.h>

/* ------------------------------------------------------------------ */
/* 全局：请求结果。uloop 是异步驱动，结果通过回调写到这里。            */
/* ------------------------------------------------------------------ */
static int g_exit = 2;          /* 默认失败（连接级），回调里改 */
static size_t g_body_len = 0;

/* ------------------------------------------------------------------ */
/* 从 stdin 读完整个 body                                             */
/* ------------------------------------------------------------------ */
static char *read_stdin_all(size_t *out_len)
{
    size_t cap = 4096, len = 0;
    char *buf = malloc(cap);
    if (!buf) return NULL;

    for (;;) {
        if (len + 1024 + 1 > cap) {
            cap *= 2;
            char *nb = realloc(buf, cap);
            if (!nb) { free(buf); return NULL; }
            buf = nb;
        }
        size_t n = fread(buf + len, 1, 1024, stdin);
        if (n == 0) break;
        len += n;
    }
    buf[len] = '\0';
    *out_len = len;
    return buf;
}

/* ------------------------------------------------------------------ */
/* 回调：数据到达 → 原样打到 stdout（交给上层/用户看）                 */
/* ------------------------------------------------------------------ */
static void read_data_cb(struct uclient *cl)
{
    char buf[1024];
    int len;

    while ((len = uclient_read(cl, buf, sizeof(buf) - 1)) > 0) {
        buf[len] = '\0';
        fputs(buf, stdout);
    }
    fflush(stdout);
}

/* 数据发送完毕（POST body 已送出）—— 无需动作 */
static void data_sent_cb(struct uclient *cl)
{
    (void)cl;
}

/* 响应头收完 —— 此时 status_code 可用，据此定成败 */
static void header_done_cb(struct uclient *cl)
{
    if (cl->status_code >= 200 && cl->status_code < 300)
        g_exit = 0;                          /* HTTP 2xx = 传输层成功 */
    else
        g_exit = 3;                          /* 非 2xx */
}

/* 整个响应结束 → 收尾 */
static void eof_cb(struct uclient *cl)
{
    (void)cl;
    uloop_end();
}

/* 出错 */
static void handle_error(struct uclient *cl, int code)
{
    const char *type = "unknown";
    switch (code) {
    case UCLIENT_ERROR_CONNECT:              type = "连接失败";         break;
    case UCLIENT_ERROR_TIMEDOUT:             type = "超时";             break;
    case UCLIENT_ERROR_SSL_INVALID_CERT:     type = "SSL 证书无效";     break;
    case UCLIENT_ERROR_SSL_CN_MISMATCH:      type = "SSL 域名不匹配";   break;
    case UCLIENT_ERROR_MISSING_SSL_CONTEXT:  type = "缺少 SSL 上下文";  break;
    default: break;
    }
    fprintf(stderr, "fzs-push: %s (code=%d)\n", type, code);
    g_exit = 2;
    (void)cl;
    uloop_end();
}

static void log_msg_cb(struct uclient *cl, enum uclient_log_type type, const char *msg)
{
    (void)cl;
    /* SSL 日志：只在出错时打，避免噪音 */
    if (type == UCLIENT_LOG_SSL_VERIFY_ERROR || type == UCLIENT_LOG_SSL_ERROR)
        fprintf(stderr, "fzs-push: ssl: %s\n", msg ? msg : "(null)");
}

static const struct uclient_cb cb = {
    .data_read   = read_data_cb,
    .data_sent   = data_sent_cb,
    .header_done = header_done_cb,
    .data_eof    = eof_cb,
    .error       = handle_error,
    .log_msg     = log_msg_cb,
};

static int usage(void)
{
    fprintf(stderr,
        "用法: fzs-push <url> <content-type> [body]\n"
        "      fzs-push --json <url> [body]\n"
        "      body 省略时从 stdin 读取\n"
        "退出码: 0=成功  1=参数错  2=连接失败  3=HTTP 非 2xx\n");
    return 1;
}

int main(int argc, char **argv)
{
    const char *url = NULL;
    const char *ctype = NULL;
    char *body = NULL;
    size_t body_len = 0;
    int body_owned = 0;
    int rc;

    /* ---- 参数解析 ------------------------------------------------ */
    if (argc >= 3 && strcmp(argv[1], "--json") == 0) {
        url = argv[2];
        ctype = "application/json";
        if (argc >= 4) { body = argv[3]; body_len = strlen(body); }
    } else if (argc >= 3) {
        url = argv[1];
        ctype = argv[2];
        if (argc >= 4) { body = argv[3]; body_len = strlen(body); }
    } else {
        return usage();
    }

    /* body 省略 → 从 stdin 读（避免命令行长度限制与引号转义地狱） */
    if (body == NULL) {
        body = read_stdin_all(&body_len);
        if (body == NULL) {
            fprintf(stderr, "fzs-push: 读取 stdin 失败\n");
            return 1;
        }
        body_owned = 1;
    }

    uloop_init();

    struct uclient *cl = uclient_new(url, NULL, &cb);
    if (cl == NULL) {
        fprintf(stderr, "fzs-push: uclient_new 失败（URL 非法？）\n");
        if (body_owned) free(body);
        return 2;
    }

    /* HTTPS：用 libustream-ssl 的上下文（与 uclient-fetch 同样做法）。
     * 若设备缺 ssl_ops（纯 HTTP 场景）也不致命 —— 库会自行处理。      */
    extern const struct ustream_ssl_ops ustream_ssl_ops;
    struct ustream_ssl_ctx *ssl_ctx = NULL;
    const struct ustream_ssl_ops *ssl_ops = NULL;
    ssl_ops = uclient_new_ssl_context(&ssl_ctx);
    if (ssl_ops && ssl_ctx)
        uclient_http_set_ssl_ctx(cl, ssl_ops, ssl_ctx, true /* 校验证书 */);

    uclient_set_timeout(cl, 20000);          /* 弱网留余量：20 秒 */

    /* ---- 核心三步（这正是 uclient-fetch 命令行做不到的）--------- */
    uclient_http_set_request_type(cl, "POST");
    uclient_http_set_header(cl, "Content-Type", ctype);
    uclient_http_set_header(cl, "User-Agent", "fzs-push/1.0");

    rc = uclient_connect(cl);
    if (rc != 0) {
        fprintf(stderr, "fzs-push: 连接失败 rc=%d\n", rc);
        uclient_free(cl);
        if (body_owned) free(body);
        uloop_done();
        return 2;
    }

    if (body_len > 0)
        uclient_write(cl, body, body_len);

    if (body_owned) free(body);

    rc = uclient_request(cl);
    if (rc != 0) {
        fprintf(stderr, "fzs-push: 发送请求失败 rc=%d\n", rc);
        uclient_free(cl);
        uloop_done();
        return 2;
    }

    uloop_run();                             /* 异步跑完整个响应 */

    if (g_exit == 0)
        fputc('\n', stdout);

    uclient_free(cl);
    uloop_done();
    return g_exit;
}
