# zcode-feishu-bridge

把 ZCode 的工作过程实时镜像到飞书：tail ZCode 的模型调用日志（`~/.zcode/cli/rollout/model-io-sess_*.jsonl`），每完成一轮模型调用就更新一张飞书流式卡片（CardKit 打字机效果）。**不修改 ZCode 任何代码**，天然免疫 ZCode 更新。

> **定位**：过程实况 feed。ZCode 官方的飞书推送只投递最终回复（机器人气泡）；本桥接补的是任务进行中的逐轮进度，建议指向一个**专用群**，与官方回复互不干扰。

```
ZCode 会话（每个任务）
  └─ rollout JSONL 逐轮落盘（response.text / reasoning / toolCalls / finishReason）
       └─ bridge.py（轮询 tail，识别活动会话）
            └─ CardKit 实体卡：创建 → 逐轮更新 streaming 元素 → finish=stop 封卡（绿头）
```

## 特性

- **逐轮流式**：模型每轮结束即更新卡片（工具调用轮显示工具名，文本轮显示正文，打字机动画）。
- **自动封卡**：`finishReason=stop` 或 5 分钟无活动 → 卡片变绿头「✅ ZCode 完成」+ meta 脚注；下个任务自动开新卡。
- **多会话跟踪**：自动跟随 mtime 最新的活动会话文件。
- **双模式**：CardKit 实体卡优先（打字机流式）；应用缺 cardkit 权限时自动降级为 message PATCH 整卡替换（无动画，其余相同）。
- **零依赖**：纯 Python 标准库（urllib/json），Python 3.10+ 直接跑。

## 配置（环境变量，与 zcode-feishu-card 插件共用）

| 变量 | 说明 |
|---|---|
| `FEISHU_APP_ID` / `FEISHU_APP_SECRET` | 飞书应用凭据（必需） |
| `FEISHU_NOTIFY_CHAT_ID` | 接收卡片的会话（单聊或群 `oc_xxx`，必需；机器人须在该会话中） |
| `FEISHU_BASE_URL` | 默认 `https://open.feishu.cn`，Lark 国际版改 `https://open.larksuite.com` |
| `ROLLOUT_DIR` | 默认 `~/.zcode/cli/rollout` |
| `BRIDGE_LOG` | 日志文件，默认脚本目录下 `bridge.log` |

应用需要权限：`im:message`（发消息）+ `cardkit:card`（卡片读写，缺了会自动降级 PATCH 模式）。

## 使用

```bash
python bridge.py          # 前台运行，Ctrl+C 退出
python bridge.py --probe  # 离线：解析最新 rollout，打印每轮将渲染的卡片内容
```

日志看 `bridge.log`。确认卡片出现在目标会话即工作正常。

## 已验证行为（2026-09-12）

- cardkit 创建/元素流式更新/封卡全链路（`{"type":"card_json","data":...}` 信封；settings 关流式用 **PATCH**）
- schema 2.0 无 `note` 组件 → 脚注用 `markdown` + `text_size: "notation"`
- 多进程同时 tail 同一文件会重复建卡 —— 只跑一个实例

## 已知边界

- 粒度是**逐轮**（模型调用完成即更新），不是 token 级打字机——卡片上的动画是飞书流式卡的呈现效果，数据源按轮推进。
- bridge 只读 rollout 日志，推送到**你自己配置的会话**；不会读取或发送 rollout 里的请求体（system prompt、历史消息都不出本机，只有 `response.text` 摘要上卡）。
