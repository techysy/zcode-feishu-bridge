---
name: feishu-bridge
description: Operate the feishu-bridge daemon that mirrors live ZCode sessions into Feishu streaming cards. Use when the user asks to 启动/停止/查看 feishu-bridge, 飞书直播/镜像 ZCode 进度, or reports bridge cards missing/duplicated/wrong.
---

# feishu-bridge operation

A stdlib-only Python daemon (`bridge.py`) tails ZCode rollout logs (`~/.zcode/cli/rollout/model-io-sess_*.jsonl`) and mirrors each active session into ONE Feishu CardKit streaming card in a dedicated chat: per-turn teaser (tools / text preview), typewriter streaming, fry-cards style stats panel (`📦 project · model · 💭 · 🔧 · context · ⏱️`) on the sealed card.

## Start / stop / status

- Start (background): `cd <plugin root> && python bridge.py` — it writes `bridge.pid`.
- Status: read `bridge.pid`, check the process is alive; progress goes to `bridge.log`.
- Stop: kill the pid **with its process tree** — Windows: `taskkill /PID <pid> /T /F`. A bare `Stop-Process` on the launcher stub leaves the real interpreter running.
- Dry run: `python bridge.py --probe` parses the newest rollout offline and prints what a card body would look like.

## Configuration (environment)

`FEISHU_APP_ID` + `FEISHU_APP_SECRET` (or plugin userConfig via the SessionStart hook), `FEISHU_NOTIFY_CHAT_ID` (target chat, oc_xxx — a dedicated group is recommended), `BRIDGE_CONTEXT_TOTAL` (context window for the usage panel, default 1000000), `ROLLOUT_DIR`, `BRIDGE_DEBUG=1` for per-line logs.

## Troubleshooting

- **No card appears** → check `bridge.log`: "no transport" = credentials missing; "no chat_id" = target chat unset; send errors carry the Feishu code.
- **N cards per line (N>1)** → N daemons are running. List them (`Get-CimInstance Win32_Process -Filter "Name='python.exe'"`), kill every tree, start one. Note: a WindowsApps python.exe stub + pythoncore child pair is ONE daemon (parent-child).
- **Time looks 8h off** → fixed by local-timezone conversion; if seen again, check `completedAt` parsing.
- **cardkit unavailable: 99992402** → app lacks `cardkit:card` scope; the daemon auto-falls back to message-PATCH updates (no typewriter, otherwise identical).
