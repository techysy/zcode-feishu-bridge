# 🌉 zcode-feishu-bridge

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![ZCode](https://img.shields.io/badge/ZCode-%E2%89%A53.11-2463eb)](https://github.com/zai-org/ZCode)
[![Python](https://img.shields.io/badge/Python-%E2%89%A53.10-blue)](https://www.python.org/)
[![当前版本](https://img.shields.io/badge/Release-v1.0.0-2463eb?logo=github&logoColor=white)](https://github.com/techysy/zcode-feishu-bridge/releases)

> 🌉 把 ZCode 会话实时镜像到飞书流式卡片 — tail rollout 日志，不改 ZCode 一行代码

- [更新日志](CHANGELOG.md) · [运维指南（SKILL）](skills/feishu-bridge/SKILL.md) · [Agent 指南](AGENTS.md)

---

## ✨ 核心特性

| 能力 | 说明 |
|------|------|
| 🎴 **流式卡片** | 飞书 CardKit 打字机效果，每完成一轮模型调用实时刷新 |
| 📦 **多会话并行** | 每个 ZCode 会话一张卡，自动提取项目标签（📦），子代理会话自动跳过 |
| 📊 **综合面板** | 封卡展示 fry-cards 同款统计行：`📦 项目 · 模型 · 💭推理 · 🔧工具 · 上下文 · ⏱️耗时` |
| 🛡️ **摘要不镜像** | 卡片只做进度 feed（300 字预告），完整回复留在 ZCode 客户端，与官方推送互不重复 |
| ⏹️ **自动封卡** | 任务收尾（`finishReason=stop`）或 5 分钟无活动 → 绿头「✅ 项目 · ZCode 完成」 |
| 🔁 **双模式发送** | CardKit 实体卡优先（打字机），缺卡片权限自动降级 message PATCH（其余不变） |
| 🔌 **零侵入零依赖** | 纯 Python 标准库；不改 ZCode 源码，天然免疫 ZCode 更新 |
| 🚀 **插件化** | 标准插件封装：SessionStart 自动拉起、`/feishu-bridge` 命令、userConfig 配置 |

---

## 🏗️ 工作原理

```text
ZCode 会话（每个任务）
  └─ rollout JSONL 逐轮落盘  ~/.zcode/cli/rollout/model-io-sess_*.jsonl
       │   response.text / reasoningText / toolCalls / usage / finishReason
       ▼
bridge.py 守护进程（轮询 tail，按会话分卡，项目标签自动提取）
       ▼
飞书 CardKit v1 实体卡
  ├─ 进行中：蓝头「🔧 ZCode 工作中」+ 300 字摘要 + 打字机 + loading
  └─ 收  尾：绿头「✅ 项目 · ZCode 完成」+ 摘要 + 综合面板
       （📦 项目 · 模型 · 💭推理轮 · 🔧工具调用 · 上下文 · ⏱️ 耗时）
```

隐私：桥接只读模型**回复**侧数据推送到你自己的会话；rollout 里的请求体
（system prompt、历史消息）不经过桥接、不出本机。

---

## 🚀 快速安装

### 方式一：ZCode 插件（推荐）

Settings → Plugin Management → Discover → `+` → 添加本仓库：

```text
https://github.com/techysy/zcode-feishu-bridge
```

安装后在插件设置里填 `notify_chat_id`（收卡片的群/单聊 `oc_xxx`），需要开机自动拉起就打开 `auto_start`。

### 方式二：手动运行

```bash
git clone https://github.com/techysy/zcode-feishu-bridge.git
cd zcode-feishu-bridge
set FEISHU_APP_ID=cli_xxx          # 飞书应用凭据
set FEISHU_APP_SECRET=xxx
set FEISHU_NOTIFY_CHAT_ID=oc_xxx   # 目标会话（机器人须在该会话中）
python bridge.py                   # 前台运行；--probe 离线预览解析结果
```

飞书应用需要权限：`im:message`（发消息）+ `cardkit:card`（卡片读写，缺了自动降级 PATCH 模式）。

---

## ⚙️ 配置

全部配置都是**键值对**，两处等价：插件设置界面（userConfig）或环境变量——
hook 启动 daemon 时会把 userConfig 注入为环境变量，真实环境变量优先。

| 插件设置键 / 等价环境变量 | 说明 |
|---|---|
| `app_id` + `app_secret` / `FEISHU_APP_ID` + `FEISHU_APP_SECRET` | 飞书应用凭据（必需；或 LARK_* 兼容） |
| `notify_chat_id` / `FEISHU_NOTIFY_CHAT_ID` | 目标会话（`oc_xxx`）。**建议用专属群**做工作实况 feed，与官方回复通道分开 |
| `notify_open_id` / `FEISHU_NOTIFY_OPEN_ID` | 单聊直达用户（`ou_xxx`），与 notify_chat_id 二选一，chat id 优先 |
| `base_url` / `FEISHU_BASE_URL` | 默认 `https://open.feishu.cn`，Lark 国际版改 `https://open.larksuite.com` |
| `context_total` / `BRIDGE_CONTEXT_TOTAL` | 模型上下文窗口，面板百分比用；默认 `1000000`（1M） |
| `panel_fields` / `BRIDGE_PANEL_FIELDS` | 综合面板字段与顺序（fry-cards footer.fields 风格），可选值 `project, model, reasoning, tools, context, tokens, elapsed`；默认全部 |
| `auto_start` | 会话启动时自动拉起 daemon（`bridge.pid` 幂等，不会重复启动） |
| `rollout_dir` / `ROLLOUT_DIR` | rollout 目录，默认 `~/.zcode/cli/rollout` |
| `debug` / `BRIDGE_DEBUG` | 布尔开关，每行解析日志（排障用） |

凭据只走环境变量 / userConfig，不写入仓库；错误信息中的 token 与 secret 会打码后才落日志。

---

## 🖥️ 命令

安装插件后可用 `/zcode-feishu-bridge:feishu-bridge [start|stop|status]`；手动运维：

```bash
python bridge.py            # 前台启动（后台用普通后台机制即可）
python bridge.py --probe    # 离线：解析最新 rollout，打印每轮将渲染的内容
```

进度与错误看 `bridge.log`。

---

## 故障排查

| 现象 | 原因与处理 |
|---|---|
| 不出卡 | 看 `bridge.log`：`no transport` = 缺凭据；`no chat_id` = 未配目标会话；send 报错带飞书错误码 |
| 每条动作出现 N 张卡 | 起了 N 个 daemon——全杀只留一个（Windows：`taskkill /PID <pid> /T /F`） |
| 没有打字机动画 | 应用缺 `cardkit:card` 权限，已自动降级 PATCH 模式；开通权限后重启 daemon |
| 时间差 8 小时 | 已修复为本地时区；若复现请提 issue |
| 收不到某些会话 | 子代理会话（`x-zcode-session-type != main`）被有意过滤，只镜像主会话 |

更多运维细节见 [SKILL](skills/feishu-bridge/SKILL.md) 与 [AGENTS.md](AGENTS.md)
（CardKit API 的坑：信封格式、settings 用 PATCH、2.0 无 note 组件、sequence 递增——都有记录）。

---

## 🔗 相关项目

- **[hermes-fry-cards](https://github.com/techysy/hermes-fry-cards)** — 同作者的 Hermes Gateway
  飞书流式卡片插件。本项目的流式卡片视觉（loading 图标、综合面板、渐变上下文条）均致敬/取材于它；
  区别在于 fry-cards 面向「飞书 ↔ bot」对话场景（patch 网关源码），本项目面向「ZCode 本地会话 →
  飞书实况」场景（tail 落盘日志，零侵入）。
- **[zcode-feishu-card](https://github.com/techysy/zcode-feishu-card)** — 同作者的另一个 ZCode 插件：
  会话内主动发送飞书卡片通知（MCP 工具 + Stop hook），与本桥接互补。

---

## 📄 许可证

[MIT](LICENSE)
