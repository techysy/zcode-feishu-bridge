---
description: 启动/停止/查看 feishu-bridge 守护进程（ZCode 会话 → 飞书流式卡片）。Start/stop/check the feishu-bridge daemon.
argument-hint: "[start|stop|status]"
---

Operate the feishu-bridge daemon per $ARGUMENTS (default: status).

- **status**: read `bridge.pid` in the plugin root; if the pid is alive report "运行中 (pid X)，日志 bridge.log"; otherwise report 未运行.
- **start**: if already running, say so; otherwise run `python bridge.py` detached in the plugin root, wait 2s, then check `bridge.log` for "watching" and report the target chat. If it exited, report the error from the log (usually missing credentials or chat id).
- **stop**: kill the pid from `bridge.pid` with its process tree (Windows: `taskkill /PID <pid> /T /F`), confirm the process is gone, then report stopped.

Never start more than one daemon — multiple instances create duplicate cards.
