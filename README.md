<div align="center">

# 🌉 zcode-feishu-bridge

**把正在进行的 ZCode 会话实时镜像成飞书流式卡片：只读 rollout 日志、不改 ZCode 一行代码、纯 Python 标准库**

[![Release](https://img.shields.io/github/v/release/techysy/zcode-feishu-bridge?label=%E7%89%88%E6%9C%AC&color=2563eb)](https://github.com/techysy/zcode-feishu-bridge/releases/latest)
[![Platform](https://img.shields.io/badge/%E5%B9%B3%E5%8F%B0-Windows%20%7C%20macOS%20%7C%20Linux-6b7280)](#已知限制)
[![Python](https://img.shields.io/badge/Python-%E2%89%A5%203.10-3776ab?logo=python&logoColor=white)](https://www.python.org/)
[![ZCode](https://img.shields.io/badge/ZCode-%E6%8F%92%E4%BB%B6-2563eb)](https://github.com/zai-org/ZCode)
[![License](https://img.shields.io/github/license/techysy/zcode-feishu-bridge?label=%E8%AE%B8%E5%8F%AF&color=f59e0b)](LICENSE)

[工作原理](#工作原理) · [功能](#功能) · [安装](#安装) · [配置](#配置) · [命令](#命令) · [故障排查](#故障排查) · [更新日志](CHANGELOG.md) · [Agent 指南](AGENTS.md) · [运维 Skill](skills/feishu-bridge/SKILL.md)

</div>

## 工作原理

<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/architecture.svg">
  <img src="assets/architecture-light.svg" width="860" alt="ZCode 飞书桥接工作原理">
</picture>

</div>

ZCode 每完成一次模型调用，就往 `~/.zcode/cli/rollout/model-io-sess_<会话>.jsonl` 追加一行 `model_io` 记录。`bridge.py` 是一个常驻守护进程，每秒轮询这个目录，从各文件的**末尾**开始读新增行，解析出：

| 字段 | 用途 |
| --- | --- |
| `response.text` / `reasoningText` / `toolCalls[].name` | 卡片正文摘要 |
| `response.finishReason` | 为 `stop` 时封卡 |
| `response.usage.inputTokens` / `outputTokens` | 面板里的上下文水位 / 输出 token |
| `model.modelId` / `completedAt` | 面板里的模型名 / 耗时 |
| `request.headers["x-zcode-session-type"]` | 不是 `main` 的会话（子代理等）直接跳过 |
| system prompt 里的 `Primary working directory` | 提取 📦 项目标签 |

然后通过飞书开放平台把它们渲染成一张 CardKit v1 实体卡：

```text
进行中：蓝头「🔧 ZCode 工作中」+ 300 字摘要 + 打字机 + loading 图标
收  尾：绿头「✅ <项目> · ZCode 完成」+ 摘要 + 综合面板
        📦 项目 · 模型 · 💭推理轮 · 🔧工具调用 · 上下文 · 🎫输出 token · ⏱️耗时
```

**隐私**：桥接会在本机读取 rollout 请求体里的 system prompt 与前几条消息，但**只用来提取项目标签和会话类型**，不会发出去。推送到飞书的只有：回复正文的前 300 字、没有正文时的工具名或推理文本前 300 字、项目标签和用量统计。

## 功能

**卡片呈现**
- **流式卡片**：飞书 CardKit 打字机效果，每完成一轮模型调用刷新一次正文（至少间隔 1 秒）
- **摘要而非镜像**：正文只放 300 字预告；这一轮没有正文时显示「⚙️ 正在使用工具：…」或「💭 推理摘要」。完整回复留在 ZCode 客户端，不和官方回复通道重复
- **自动封卡**：`finishReason=stop` 或会话文件 5 分钟没有变化时，卡片转为绿头「✅ 项目 · ZCode 完成」并关闭流式模式；下一轮活动开一张新卡
- **综合面板**：封卡时附 fry-cards 同款统计行，字段和顺序可用 `panel_fields` 配置
- **双模式发送**：优先用 CardKit 实体卡（打字机）；应用没有 `cardkit:card` 权限时自动降级为消息 PATCH 整卡替换（无动画，见[已知限制](#已知限制)）

**会话识别**
- **多会话并行**：每个 rollout 文件独立跟踪、各自一张卡，互不干扰
- **项目标签**：从 system prompt 的 `Primary working directory` 提取（压缩轮换后也不会丢），取 `GitHub Files\` 或 `workspace\` 下的一级目录名，否则取目录本身的名字；找不到该字段时退回从前 4 条消息里的路径推断；可用 `project_alias` 重命名
- **过滤噪音**：子代理会话跳过；环境信息回显、会话压缩总结（`<analysis>`）、裸 JSON 等辅助调用输出不会作为卡片正文

**运行与自愈**
- **零侵入**：只读 ZCode 落盘日志，不修改 ZCode 任何文件，ZCode 升级不受影响
- **零第三方依赖**：`bridge.py` 只用 Python 标准库（`urllib` / `json` / `pathlib` 等）；插件 hook 只用 Node.js 内置模块
- **fail-open**：单行脏数据、网络抖动、飞书接口报错都只记日志，守护进程继续运行；崩溃时 `bridge.log` 留完整 traceback
- **心跳与僵死重启**：守护进程每秒写 `bridge.heartbeat`；SessionStart hook 发现进程还在但心跳超过 15 分钟没更新时，按进程树杀掉并重启
- **插件化**：ZCode 插件封装，SessionStart 自动拉起（无控制台窗口）、`/zcode-feishu-bridge:feishu-bridge` 命令、运维 skill、插件设置界面（中英双语）

## 安装

### 前置条件

- **飞书自建应用**：开启机器人能力，并开通 `im:message`（发消息）和 `cardkit:card`（卡片读写；没有也能用，会自动降级为 PATCH 模式）；机器人需要已加入接收卡片的群
- **Python ≥ 3.10**：Windows 上 hook 优先用 `pythonw.exe`（无窗口），找不到时退回 `python`；其他系统用 `python3`
- **Node.js**：只有 SessionStart hook（`hooks/session-start.mjs`）需要，命令名为 `node`

### 方式一：ZCode 插件（推荐）

1. Settings → Plugin Management → Discover → `+` → 添加本仓库：

   ```text
   https://github.com/techysy/zcode-feishu-bridge
   ```

2. 在插件设置里填写 `app_id`、`app_secret` 和 `notify_chat_id`（或 `notify_open_id`），打开 `auto_start`
3. 新开一个会话（或 `/clear`、会话压缩后），hook 会在后台拉起守护进程

> 插件设置只有经 SessionStart hook 启动时才会传给守护进程；`auto_start` 关闭时 hook 直接退出，此时需要按方式二用环境变量配置。

### 方式二：手动运行

```powershell
# Windows PowerShell
git clone https://github.com/techysy/zcode-feishu-bridge.git
cd zcode-feishu-bridge
$env:FEISHU_APP_ID = "cli_xxx"            # 飞书应用凭据
$env:FEISHU_APP_SECRET = "xxx"
$env:FEISHU_NOTIFY_CHAT_ID = "oc_xxx"     # 目标会话（机器人须在该会话中）
python bridge.py                          # 前台运行，Ctrl+C 退出
```

```bash
# macOS / Linux / Git Bash
git clone https://github.com/techysy/zcode-feishu-bridge.git
cd zcode-feishu-bridge
export FEISHU_APP_ID=cli_xxx FEISHU_APP_SECRET=xxx FEISHU_NOTIFY_CHAT_ID=oc_xxx
python3 bridge.py
```

需要后台常驻时用系统自带的后台机制，例如 Windows 下：

```powershell
Start-Process pythonw.exe -ArgumentList bridge.py -WorkingDirectory (Get-Location) -WindowStyle Hidden
```

启动后 `bridge.log` 第一行应为 `watching <rollout 目录> -> oc_xxx…`。

## 配置

全部配置都是键值对。`bridge.py` 本身**只读环境变量**；插件设置（userConfig）由 SessionStart hook 在拉起守护进程时转成对应的环境变量注入，已存在的真实环境变量优先。

| 插件设置键 | 环境变量 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `app_id` / `app_secret` | `FEISHU_APP_ID` / `FEISHU_APP_SECRET` | — | 飞书应用凭据（必需）；也兼容 `LARK_APP_ID` / `LARK_APP_SECRET` |
| `notify_chat_id` | `FEISHU_NOTIFY_CHAT_ID` | — | 接收卡片的群或单聊（`oc_xxx`）；也兼容 `FEISHU_CARD_CHAT_ID`。**建议用专属群**做工作实况 feed，与官方回复通道分开 |
| `notify_open_id` | `FEISHU_NOTIFY_OPEN_ID` | — | 单聊直达用户（`ou_xxx`），与 `notify_chat_id` 二选一，两者都填时 chat id 优先 |
| `base_url` | `FEISHU_BASE_URL` | `https://open.feishu.cn` | Lark 国际版改为 `https://open.larksuite.com` |
| `rollout_dir` | `ROLLOUT_DIR` | `~/.zcode/cli/rollout` | ZCode rollout 日志目录 |
| `context_total` | `BRIDGE_CONTEXT_TOTAL` | `1000000` | 模型上下文窗口，面板百分比的分母 |
| `panel_fields` | `BRIDGE_PANEL_FIELDS` | 全部字段 | 综合面板字段与顺序，逗号分隔，见下表；留空回落默认 |
| `project_alias` | `BRIDGE_PROJECT_ALIAS` | `default=workspace` | 项目标签重命名，逗号分隔的 `原名=新名` |
| `auto_start` | — | `false` | 会话启动时自动拉起守护进程（仅插件方式） |
| `debug` | `BRIDGE_DEBUG` | 关 | 每解析一行都写日志，排障用；环境变量为空或 `0` 时关闭 |
| — | `BRIDGE_LOG` | `<插件根目录>/bridge.log` | 日志路径；`bridge.pid`、`bridge.heartbeat` 会写在同一目录 |

凭据只走环境变量 / 插件设置，不写入仓库；`bridge.log`、`bridge.pid`、`bridge.heartbeat` 已加入 `.gitignore`。

**综合面板字段**（`panel_fields`，示例：`📦 imgmark · glm-5.3-flash · 💭3 · 🔧22 · 243.7k/1.0m (24%) · 🎫 12.3k · ⏱️ 18m 42s`）

| 字段 | 显示 | 来源 |
| --- | --- | --- |
| `project` | `📦 项目` | 项目标签（取不到时省略） |
| `model` | 模型名 | `model.modelId` 最后一段 |
| `reasoning` | `💭N` | 本卡中产生推理文本的轮数 |
| `tools` | `🔧N` | 本卡中工具调用总数 |
| `context` | `243.7k/1.0m (24%)` | 最近一轮 `inputTokens` / `context_total` |
| `tokens` | `🎫 12.3k` | 本卡累计 `outputTokens` |
| `elapsed` | `⏱️ 18m 42s` | 本卡第一轮到最近一轮的 `completedAt` 差 |

<details>
<summary><b>内置常量</b>（位于 <code>bridge.py</code> 顶部，不可通过配置修改）</summary>

| 常量 | 值 | 含义 |
| --- | --- | --- |
| `POLL_SEC` | `1.0` | 轮询 rollout 目录的间隔（秒） |
| `UPDATE_MIN_INTERVAL` | `1.0` | 两次卡片内容更新的最小间隔（秒） |
| `SEAL_IDLE_SEC` | `300` | 会话文件无变化多久后自动封卡（秒） |
| `TEASER_CHARS` | `300` | 每轮正文摘要长度 |
| `MAX_BODY_CHARS` | `24000` | 卡片 markdown 长度兜底上限 |

</details>

## 命令

安装插件后可在 ZCode 里用：

```text
/zcode-feishu-bridge:feishu-bridge [start|stop|status]    # 默认 status
```

手动运维：

```bash
python bridge.py              # 前台启动
python -X utf8 bridge.py --probe   # 离线：解析最新的 rollout 文件，逐轮打印将渲染的正文，不连飞书
```

- 状态：读插件根目录的 `bridge.pid`，确认进程存活；进度与错误看 `bridge.log`
- 停止：**按进程树**结束，Windows 用 `taskkill /PID <pid> /T /F`（`Stop-Process` 只杀启动器会留下真正的解释器）
- `--probe` 在中文 Windows 控制台下需要 `-X utf8`（或设置 `PYTHONIOENCODING=utf-8`），否则打印 emoji 时会报 `UnicodeEncodeError`

## 故障排查

| 现象 | 原因与处理 |
| --- | --- |
| 不出卡，日志里有 `missing FEISHU_APP_ID / FEISHU_APP_SECRET` | 缺凭据。手动运行时检查环境变量；插件方式检查 `app_id` / `app_secret` 与 `auto_start` |
| 进程起来就退出，`bridge.log` 里没有 `watching` | 没配目标会话（`missing notify target`），或凭据错误（`tenant_access_token failed`）。这两种情况进程直接退出，信息只打到终端，请前台运行 `python bridge.py` 查看 |
| 日志里有 `send card failed: <code> <msg>` | 发消息失败，按飞书错误码处理；常见原因是机器人不在目标群里 |
| 每条动作出现 N 张卡 | 起了 N 个守护进程，全部结束只留一个（Windows：`taskkill /PID <pid> /T /F`）。注意 `WindowsApps\python.exe` 启动器 + `pythoncore\python.exe` 子进程是**同一个**实例，清点时看 ParentProcessId |
| 没有打字机动画，日志有 `cardkit unavailable … falling back to message PATCH` | 应用缺 `cardkit:card` 权限，已降级 PATCH 模式；开通权限后重启守护进程 |
| 收不到某些会话 | 子代理会话（`x-zcode-session-type` 不是 `main`）被有意过滤，只镜像主会话 |
| 守护进程启动前已在进行的会话，前面的内容没出现 | 设计如此：新文件从末尾开始读，不回放历史 |

更多运维细节见 [SKILL](skills/feishu-bridge/SKILL.md) 与 [AGENTS.md](AGENTS.md)（CardKit API 的坑：信封格式、settings 要用 PATCH、Card 2.0 没有 note 组件、sequence 必须递增等）。

## 项目结构

```
zcode-feishu-bridge/
├── bridge.py                      守护进程（单文件，纯标准库）
├── .zcode-plugin/
│   ├── plugin.json                插件清单、版本号与 11 项 userConfig
│   └── marketplace.json           插件市场索引
├── hooks/
│   ├── hooks.json                 SessionStart hook 声明（startup / clear / compact 时触发）
│   └── session-start.mjs          自动拉起、心跳僵死检测、userConfig → 环境变量
├── commands/feishu-bridge.md      /zcode-feishu-bridge:feishu-bridge 命令
├── skills/feishu-bridge/SKILL.md  运维 skill
├── AGENTS.md                      给 AI Agent / 贡献者的不变量与踩坑记录
├── CHANGELOG.md · LICENSE
└── .tmp-bridge.log · .tmp-start-bridge.ps1   本地联调遗留文件
```

运行时会在插件根目录生成 `bridge.log`、`bridge.pid`、`bridge.heartbeat`（均不入库）。

<details>
<summary><b>开发者：联调与发版</b></summary>

**联调**

没有自动化测试。改代码后：

1. `python -X utf8 bridge.py --probe` 离线检查最新 rollout 的解析与正文渲染
2. 生命周期联调用假 rollout 目录：设置 `ROLLOUT_DIR` 指向一个临时目录，启动守护进程后往 `model-io-sess_*.jsonl` 里逐行追加记录，日志应为 `card created → card sealed →（新任务）card created`，**每行最多一张卡**；配合 `BRIDGE_DEBUG=1` 看逐行解析

改动前先读 [AGENTS.md](AGENTS.md) 里的设计不变量（摘要不是镜像、统计行只在封卡出现、fail-open、密钥只走环境变量）和 CardKit 硬坑。

**约定**

- Python 只用标准库，不引入第三方依赖
- 文档、注释、commit message 用中文；commit 前缀 `Feat: / Fix: / Docs: / style:`

**发版**

1. 在 [CHANGELOG.md](CHANGELOG.md) 顶部补充新版本小节
2. 同步 `.zcode-plugin/plugin.json` 与 `.zcode-plugin/marketplace.json` 中的 `version`
3. 推送 `v*` tag 并在 GitHub 上创建 Release（仓库没有 CI，Release 不附带构建产物，插件直接从仓库安装）

</details>

## 已知限制

- 主要在 Windows 上开发和使用。项目标签按 Windows 路径（`\`）解析：macOS / Linux 下 📦 标签会显示为完整路径，可用 `project_alias` 映射
- 降级 PATCH 模式下，进行中的卡片目前不会逐轮刷新（更新调用会报错并记入日志），只在封卡时整卡替换为最终内容；开通 `cardkit:card` 权限可避免
- 只跟随守护进程启动之后新增的日志行，不回放历史
- 单实例只由 SessionStart hook 保证（检查 `bridge.pid` 与心跳）；手动运行 `python bridge.py` 不检查是否已有实例，重复启动会导致一条动作出现多张卡
- 凭据错误或未配置目标会话时进程直接退出，不会重试
- 卡片正文是摘要，完整回复只在 ZCode 客户端

## 相关项目

- **[hermes-fry-cards](https://github.com/techysy/hermes-fry-cards)** 🍟：Hermes Gateway 飞书流式卡片插件，fry-cards 系列源头。本项目的卡片视觉（loading 图标、综合面板统计行）取材于它；区别在于它面向「飞书 ↔ bot」对话通道，本项目面向「ZCode 本地会话 → 飞书实况」，通过读落盘日志实现，零侵入
- **[claw-fry-cards](https://github.com/techysy/claw-fry-cards)** 🍤：OpenClaw 飞书通道插件，内置同款 fry 卡片引擎
- **[feige-fry-cards](https://github.com/techysy/feige-fry-cards)** 🕊️：跨 agent（ZCode / Claude Code / Codex）的会话收尾摘要卡插件，复用了本项目的 CardKit 流式卡核心；本项目推送过程实况，它推送最终战报，可以配合使用

## 许可证

[MIT](LICENSE)
