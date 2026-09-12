# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] - 2026-09-12

首个公开版本。

### 新增 / Added
- **rollout-tail 桥接** — tail ZCode 的 `~/.zcode/cli/rollout/model-io-sess_*.jsonl`，
  每完成一轮模型调用即更新飞书 CardKit 流式卡片（打字机效果），不改 ZCode 任何代码。
- **多会话支持** — 每个会话一张卡，项目标签（📦）自动从会话内容提取；
  子代理会话（`x-zcode-session-type != main`）自动跳过。
- **摘要卡设计** — 进行中的卡只有正文摘要（300 字 teaser）+ loading 图标；
  完整回复留在 ZCode 客户端，卡片不做全文镜像。
- **综合面板（封卡）** — fry-cards 同款统计行：
  `📦 项目 · glm-5.3-flash · 💭推理轮 · 🔧工具调用 · 上下文 243.7k/1.0m (24%) · ⏱️ 耗时`，
  上下文水位取自 `usage.inputTokens`，时间为本地时区。
- **双模式发送** — CardKit 实体卡优先（打字机流式），应用缺 `cardkit:card` 权限时
  自动降级为 message PATCH 整卡替换（无动画，其余相同）。
- **自动封卡** — `finishReason == "stop"` 或 5 分钟无活动 → 绿头「✅ 项目 · ZCode 完成」。
- **ZCode 插件封装** — `plugin.json` userConfig（notify_chat_id / context_total / auto_start）、
  SessionStart hook 自动拉起 daemon（`bridge.pid` 幂等）、
  skill `feishu-bridge`（运维知识）+ `/zcode-feishu-bridge:feishu-bridge` 命令。
- **零依赖** — 纯 Python 标准库（urllib/json），3.10+ 直接运行。

[1.0.0]: https://github.com/techysy/zcode-feishu-bridge/releases/tag/v1.0.0
