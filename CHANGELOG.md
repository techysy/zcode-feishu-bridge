# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.1.0] - 2026-09-20

### 新增 / Added
- **通知目标支持 open_id** — `notify_open_id`（`ou_xxx`）单聊直达用户，与 `notify_chat_id` 二选一（chat id 优先）
- **综合面板可配置** — `panel_fields` 字段与顺序开关（fry-cards footer.fields 风格），新增 🎫 输出 token 用量
- **项目别名** — `project_alias`（默认 `default=workspace`），统一无意义目录名
- **全部配置收敛为键值对** — 凭据 / base_url / rollout_dir / debug 均入插件设置（hook 统一注入环境变量，真实 env 优先）
- **三层自愈** — 心跳文件 + SessionStart hook 僵死检测（15 分钟无心跳杀树重启）；运行期错误记日志重试不再退出；崩溃留完整 traceback
- **插件文案中英双语**（中文前置），覆盖全部 userConfig / 命令 / skill 描述

### 修复 / Fixed
- SessionStart hook 拉起 daemon **不再弹出控制台窗口**（pythonw + windowsHide）
- hook pidfile 路径修正（原来指向 hooks/ 子目录导致幂等失效、重复拉起）
- 📦 项目标签改读 system prompt 的 `Primary working directory`——会话压缩轮换后工作区名不再丢失
- **摘要卡垃圾过滤**——环境块回显 / 压缩总结（`<analysis>`）/ 裸 JSON 等辅助调用文本不再作为卡片正文
- `create()` 引用未定义 `chatId` 导致建卡失败；`BRIDGE_PANEL_FIELDS` 空串回落默认字段

[1.1.0]: https://github.com/techysy/zcode-feishu-bridge/releases/tag/v1.1.0

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
