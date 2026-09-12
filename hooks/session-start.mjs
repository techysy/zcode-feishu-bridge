#!/usr/bin/env node
/**
 * SessionStart hook: auto-start the feishu-bridge daemon if the plugin userConfig
 * `auto_start` is true and no live daemon is found (bridge.pid liveness check).
 * The daemon is spawned DETACHED, so it outlives this hook and the session.
 * Any failure exits 0 silently — a convenience hook must never block startup.
 */

import { spawn } from "node:child_process";
import { existsSync, readFileSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";

let raw = "";
process.stdin.setEncoding("utf8");
for await (const chunk of process.stdin) raw += chunk;

const enabled = /^(1|true|yes)$/i.test(
  process.env.ZCODE_USER_CONFIG_AUTO_START || "",
);
if (!enabled) process.exit(0);

const root = fileURLToPath(new URL("..", import.meta.url));
const pidfile = fileURLToPath(new URL("../bridge.pid", import.meta.url)); // bridge.py writes at plugin root

// liveness: pidfile present, pid alive, and heartbeat fresh (hung-daemon recovery)
const heartbeat = fileURLToPath(new URL("../bridge.heartbeat", import.meta.url));
if (existsSync(pidfile)) {
  let alive = false;
  try {
    const pid = Number(readFileSync(pidfile, "utf8").trim());
    if (pid > 0) process.kill(pid, 0); // throws if the process is gone
    alive = true;
  } catch { /* stale pidfile — fall through and start */ }
  if (alive) {
    try {
      const ageMin = (Date.now() - fs.statSync(heartbeat).mtimeMs) / 60000;
      if (ageMin < 15) process.exit(0); // alive and healthy
      // hung: heartbeat stale — kill the tree and respawn below
      const { execSync } = await import("node:child_process");
      const pid = Number(readFileSync(pidfile, "utf8").trim());
      if (process.platform === "win32") execSync(`taskkill /PID ${pid} /T /F`, { stdio: "ignore" });
      else process.kill(pid, "SIGKILL");
      process.stderr.write(`[feishu-bridge] daemon hung (${ageMin.toFixed(0)}min no heartbeat), restarted
`);
    } catch {
      process.exit(0); // kill failed but pid alive — do not double-spawn
    }
  }
}

// pythonw = windowless interpreter; windowsHide as belt-and-braces — never pop a console
const python = process.platform === "win32" ? "pythonw.exe" : "python3";
const childEnv = {
  ...process.env,
  // all plugin userConfig → daemon env (daemon reads env only; real env vars still win as fallback)
  FEISHU_APP_ID: process.env.FEISHU_APP_ID || process.env.ZCODE_USER_CONFIG_APP_ID || "",
  FEISHU_APP_SECRET: process.env.FEISHU_APP_SECRET || process.env.ZCODE_USER_CONFIG_APP_SECRET || "",
  FEISHU_BASE_URL: process.env.FEISHU_BASE_URL || process.env.ZCODE_USER_CONFIG_BASE_URL || "",
  FEISHU_NOTIFY_CHAT_ID: process.env.FEISHU_NOTIFY_CHAT_ID || process.env.ZCODE_USER_CONFIG_NOTIFY_CHAT_ID || "",
    FEISHU_NOTIFY_OPEN_ID: process.env.FEISHU_NOTIFY_OPEN_ID || process.env.ZCODE_USER_CONFIG_NOTIFY_OPEN_ID || "",
  BRIDGE_CONTEXT_TOTAL: process.env.BRIDGE_CONTEXT_TOTAL || process.env.ZCODE_USER_CONFIG_CONTEXT_TOTAL || "1000000",
  BRIDGE_PANEL_FIELDS: process.env.BRIDGE_PANEL_FIELDS || process.env.ZCODE_USER_CONFIG_PANEL_FIELDS || "",
  ROLLOUT_DIR: process.env.ROLLOUT_DIR || process.env.ZCODE_USER_CONFIG_ROLLOUT_DIR || "",
  BRIDGE_DEBUG: process.env.BRIDGE_DEBUG || (process.env.ZCODE_USER_CONFIG_DEBUG || ""),
    BRIDGE_PROJECT_ALIAS: process.env.BRIDGE_PROJECT_ALIAS || process.env.ZCODE_USER_CONFIG_PROJECT_ALIAS || "",
};
let child = spawn(python, ["bridge.py"], {
  cwd: root, detached: true, stdio: "ignore", windowsHide: true, env: childEnv,
});
child.on("error", () => {  // pythonw not on PATH → console python, still hidden
  child = spawn("python", ["bridge.py"], {
    cwd: root, detached: true, stdio: "ignore", windowsHide: true, env: childEnv,
  });
  child.unref();
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
