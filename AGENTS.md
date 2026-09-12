# AGENTS.md — feishu-bridge 仓库指南

面向在本仓库工作的 AI agent / 贡献者。README.md 面向用户；这里记录**不变量、踩坑与工作方式**，改代码前先读。

## 项目是什么

单文件 Python 守护进程（`bridge.py`，纯标准库）tail ZCode 的模型调用日志
`~/.zcode/cli/rollout/model-io-sess_*.jsonl`，把每个活动会话镜像成一张飞书 CardKit
流式卡片。**不修改 ZCode 任何东西**——所有数据来自落盘日志。

- 一行 `model_io` = 一次完成的模型调用；正文 `response.text`、思考 `response.reasoningText`、
  工具 `response.toolCalls[].name`、收尾 `finishReason == "stop"`、用量 `response.usage`
  （camelCase：`inputTokens` ≈ 当前上下文水位）。
- 多会话：每个 rollout 文件一张卡；会话类型取 `request.headers["x-zcode-session-type"]`，
  非 `main`（子代理等）直接跳过；项目标签从会话前几条消息里的路径提取
  （`GitHub Files\X` / `workspace\X` 的一级目录）。

## 设计不变量（改代码前必读）

1. **卡片正文是摘要不是镜像**：`TEASER_CHARS`（300 字）截断。完整回复只存在于 ZCode
   客户端——官方通道会投递最终回复，桥接再贴全文就是重复（已踩过）。
2. **统计行只在封卡出现**：进行中的卡只有正文 + loading 图标；综合面板
   （`📦 项目 · 模型 · 💭 · 🔧 · 上下文 · ⏱️`）是封卡脚注，单次呈现。
3. **fail-open**：任何异常打日志后继续跑，守护进程绝不能因单行脏数据或网络抖动退出。
4. **密钥只走环境变量**（`FEISHU_APP_ID/SECRET`），任何配置文件/日志/文档不得出现真实凭据。

## 飞书 CardKit 硬坑（违反即失败）

- 建卡 body 必须是信封 `{"type": "card_json", "data": "<卡片JSON字符串>"}`，传裸卡片对象报 99992402。
- 关流式：`PATCH /cardkit/v1/cards/:id/settings`，body `{"settings": "{\"streaming_mode\": false}", "sequence": n}`——**PUT 会 404**。
- Card 2.0 **没有 `note` 组件**，脚注用 `markdown` + `"text_size": "notation"`。
- 所有 cardkit 变更都要带单调递增 `sequence`。
- 流式正文元素要有 `"element_id"`（本仓 `streaming_content`），内容更新走
  `PUT .../elements/:element_id/content`。
- 卡片引用发送：`content = {"type": "card", "data": {"card_id": ...}}`。

## 测试方式

```bash
python bridge.py --probe   # 离线解析最新 rollout，打印每轮将渲染的内容
```

生命周期联调用假 rollout 目录（建 `ROLLOUT_DIR=x/.tmp`，边跑边 append 行），
观察日志应为 `card created → card sealed → （新任务）card created`，**每行至多一张卡**。

## Windows 运维坑

- ZCode 后台任务会在调用结束时关闭 stderr：`log()` 必须 try/except 并同时落盘 `bridge.log`。
- 杀 daemon 必须按进程树：`taskkill /PID <pid> /T /F`；`Stop-Process` 杀不干净会留僵尸实例，
  表现为每行建 N 张卡。`WindowsApps\python.exe`（stub）+ `pythoncore\python.exe`（child）
  是**一个** daemon（父子进程），清点时看 ParentProcessId。
- `setx` 不影响已运行的 shell，验证配置时要显式传环境变量。
- 桥接只跑**一个实例**（`bridge.pid` 幂等）。

## 约定

- Python 标准库 only，不引入第三方依赖。
- 文档、注释、commit message 用中文；commit 前缀 `Feat: / Fix: / Docs: / style:`。
- `bridge.log` / `bridge.pid` 已 gitignore，不得入库。
