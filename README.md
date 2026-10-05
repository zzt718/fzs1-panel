# 蜂助手面板 —— MIBOX-668M2 蜂窝运维面板

> **新模型/新接手者从这里开始。** 项目定位一句话：
> **在社区的 MIBOX-668M2 OpenWrt 固件之上，交付"蜂窝运维专家面板"（LuCI 应用，ipk 包）。**
> 通用路由功能（WiFi/DHCP/防火墙/升级）全部留给 LuCI，我们一行不重复。

## 一句话背景

- 硬件：蜂助手 S1（MIBOX-668M2，MT7628 + EC200T/EC200N 双模组）；
- 平台：社区开发者的 OpenWrt 22.03.7 固件（`mibox,668m2` 自定义 DTS，双模组 RNDIS + mwan3 已配好，经大量网友实刷）——**平台不是我们的，应用是我们的**；
- 姊妹项目：`../fzs1_decloud`（厂商固件去云控 + v19.x 工具箱，厂商线存量用户的交付物）——本项目的知识资产（锁频/IMEI/短信/AT 经验）全部来自那里。

## 交付物

| 项 | 内容 |
|---|---|
| 形态 | `luci-app-fzs` **ipk 包**（Architecture: all，自包含 AT 引擎，不依赖 mifi-at 内部实现） |
| 分发 | 起步 = LuCI 软件页手动传包；成熟 = 自建 opkg 源（挂 GitHub/Gitee） |
| 平台契约 | 只依赖两样：固件版本号、`/etc/config/mifi` 字段。他改 mifi-at 我们不碎 |
| 命名 | 面板「蜂助手面板」/ 包 `luci-app-fzs`（沿用 fzs1 家族命名空间，用户零新增认知） |

## 功能范围（MVP）

- **P0**：双模组信息面板（型号/IMEI/IMSI/ICCID/RSRP-SINR/频段/驻网）；锁频段 + 锁频点/小区（AT\*BAND / AT\*CELL，解锁含补拨号）；短信中心（双模组收件箱 + 转发 TG/钉钉/webhook + 发送）
- **P1**：IMEI 读写（备份/恢复/确认）；APN 与数据开关（/etc/config/mifi 的 UI 化）
- **P2**：运维工具（RNDIS bind 救活、模组重启、日志、诊断）；网口与优先级（与 mwan3 整合，bench 后定）
- **不做**：WiFi/DHCP/防火墙/系统升级/密码——LuCI 全有

## 里程碑

1. **M1 备份**：13856 全量 mtd 备份（回滚唯一来源，动手前必须完成）
2. **M2 bench**：13856 刷社区固件，验证双模组/WiFi/稳定性 + 我方 AT 资产复测（AT\*CELL 等）
3. **M3 MVP**：P0 三件开发完成，ipk 可装可卸
4. **M4 发布**：README/发布素材/GitHub 仓库 + opkg 源（是否合流进上游固件，届时另议）

## 目录

| 目录/文件 | 内容 |
|---|---|
| `00_时间线.md` | 唯一时间线（先读） |
| `需求文档.md` | 需求与范围定义（立项文档） |
| `src/luci-app-fzs/` | ipk 源树（control/ + data/） |
| `src/build_ipk.py` | all-arch ipk 打包器（纯 Python，无需 SDK） |
| `bench/` | 13856 备份与刷机 bench 记录 |
| `docs/` | 设计文档、平台取证笔记 |
| `发布素材/` | 发布帖文案、截图 |

## 红线（继承自 fzs1_decloud，仍然有效）

1. 动 13856 之前先全量 mtd 备份；不碰 /dev/watchdog 之外的独占资源前先确认持有者；
2. AT 操作前确认端口归属（新底座上两模组 AT 口天然空闲，但仍以 `mifi-at ports`/sysfs 实测为准）；
3. 测试卡 IMEI 绝不改动（备份文件 `imei backup` 的产物永远只用于恢复本机）；
4. 对外发布（GitHub/源码/帖文）需用户确认。
