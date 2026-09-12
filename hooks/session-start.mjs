#!/usr/bin/env node
/**
 * SessionStart hook: auto-start the feishu-bridge daemon if the plugin userConfig
 * `auto_start` is true and no live daemon is found (bridge.pid liveness check).
 * The daemon is spawned DETACHED, so it outlives this hook and the session.
 * Any failure exits 0 silently — a convenience hook must never block startup.
 */

import { spawn } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

let raw = "";
process.stdin.setEncoding("utf8");
for await (const chunk of process.stdin) raw += chunk;

const enabled = /^(1|true|yes)$/i.test(
  process.env.ZCODE_USER_CONFIG_AUTO_START || "",
);
if (!enabled) process.exit(0);

const root = fileURLToPath(new URL("..", import.meta.url));
const pidfile = fileURLToPath(new URL("./bridge.pid", import.meta.url));

// liveness: pidfile present and the pid responds to signal 0
if (existsSync(pidfile)) {
  try {
    const pid = Number(readFileSync(pidfile, "utf8").trim());
    if (pid > 0) process.kill(pid, 0); // throws if the process is gone
    process.exit(0); // alive — nothing to do
  } catch {
    /* stale pidfile — fall through and start */
  }
}

const python = process.platform === "win32" ? "python" : "python3";
const child = spawn(python, ["bridge.py"], {
  cwd: root,
  detached: true,
  stdio: "ignore",
  env: {
    ...process.env,
    FEISHU_NOTIFY_CHAT_ID: process.env.ZCODE_USER_CONFIG_NOTIFY_CHAT_ID || "",
    BRIDGE_CONTEXT_TOTAL: process.env.ZCODE_USER_CONFIG_CONTEXT_TOTAL || "1000000",
    BRIDGE_PANEL_FIELDS: process.env.ZCODE_USER_CONFIG_PANEL_FIELDS || "",
  },
});
child.unref();

process.stderr.write(`[feishu-bridge] daemon spawned (pid ${child.pid})\n`);
process.stdout.write(
  JSON.stringify({
    hookSpecificOutput: {
      hookEventName: "SessionStart",
      additionalContext:
        "feishu-bridge daemon started in the background: ZCode session progress is being mirrored to Feishu.",
    },
  }),
);
