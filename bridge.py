#!/usr/bin/env python3
"""zcode-feishu-bridge — tail ZCode rollout logs into a live Feishu streaming card.

Zero dependencies (stdlib only). Watches <rollout_dir>/model-io-sess_*.jsonl
(default %USERPROFILE%/.zcode/cli/rollout, override with ROLLOUT_DIR), parses each
appended `model_io` line (one completed model turn: response.text / reasoningText /
toolCalls[].name / finishReason) and mirrors the active session into ONE streaming
Feishu card in the configured chat:

  - new activity          -> create streaming card (CardKit v1) + send to chat
  - each new turn         -> update the streaming element (throttled)
  - finishReason == stop  -> seal card (streaming_mode off, green header)
  - 5 min idle            -> seal card

Transport: Feishu app credentials from env (same as the zcode-feishu-card plugin:
FEISHU_APP_ID / FEISHU_APP_SECRET / FEISHU_NOTIFY_CHAT_ID). If the CardKit API is
forbidden (missing cardkit:card scope), falls back to plain message PATCH updates
(no typewriter animation, otherwise identical).
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE_URL = (os.environ.get("FEISHU_BASE_URL") or "https://open.feishu.cn").rstrip("/")
API = BASE_URL + "/open-apis"
ROLLOUT_DIR = Path(os.environ.get("ROLLOUT_DIR") or (Path.home() / ".zcode" / "cli" / "rollout"))
POLL_SEC = 1.0
UPDATE_MIN_INTERVAL = 1.0     # seconds between card content updates
SEAL_IDLE_SEC = 300.0         # seal card after this much file inactivity
MAX_BODY_CHARS = 24_000       # hard backstop for card markdown size
TEASER_CHARS = 300            # per-turn text preview — the client already shows full text
STREAMING_ELEMENT_ID = "streaming_content"
LOADING_ELEMENT_ID = "loading_icon"
LOADING_IMG_KEY = "img_v3_02vb_496bec09-4b43-4773-ad6b-0cdd103cd2bg"  # from hermes-fry-cards
CTX_TOTAL = int(os.environ.get("BRIDGE_CONTEXT_TOTAL") or 200_000)  # model context window

APP_ID = os.environ.get("FEISHU_APP_ID") or os.environ.get("LARK_APP_ID") or ""
APP_SECRET = os.environ.get("FEISHU_APP_SECRET") or os.environ.get("LARK_APP_SECRET") or ""
CHAT_ID = os.environ.get("FEISHU_NOTIFY_CHAT_ID") or os.environ.get("FEISHU_CARD_CHAT_ID") or ""

_LOG_FILE = Path(os.environ.get("BRIDGE_LOG") or (Path(__file__).parent / "bridge.log"))


def log(msg: str) -> None:
    """stderr best-effort (background runners may close it), always to the log file."""
    stamp = time.strftime("%H:%M:%S")
    try:
        print(f"[{stamp}] {msg}", file=sys.stderr, flush=True)
    except (ValueError, OSError):
        pass
    try:
        with open(_LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(f"[{stamp}] {msg}\n")
    except OSError:
        pass

_token: dict = {"value": "", "expire_at": 0.0}


def get_token() -> str:
    if not APP_ID or not APP_SECRET:
        sys.exit("missing FEISHU_APP_ID / FEISHU_APP_SECRET env vars")
    now = time.time()
    if _token["value"] and now < _token["expire_at"]:
        return _token["value"]
    req = urllib.request.Request(
        f"{API}/auth/v3/tenant_access_token/internal",
        data=json.dumps({"app_id": APP_ID, "app_secret": APP_SECRET}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())
    if data.get("code") != 0:
        sys.exit(f"tenant_access_token failed: {data.get('code')} {data.get('msg')}")
    _token["value"] = data["tenant_access_token"]
    _token["expire_at"] = now + int(data.get("expire") or 3600) - 60
    return _token["value"]


def call_api(method: str, path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(
        API + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {get_token()}", "Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return json.loads(raw)
        except ValueError:
            return {"code": e.code, "msg": raw[:300]}


# ── card shapes (mirroring hermes-fry-cards cardkit streaming card) ─────────

def streaming_card(text: str, title: str = "🔧 ZCode 工作中", template: str = "blue") -> dict:
    return {
        "schema": "2.0",
        "config": {
            "width_mode": "default",
            "streaming_mode": True,
            "streaming_config": {
                "print_frequency_ms": {"default": 15},
                "print_step": {"default": 1},
                "print_strategy": "fast",
            },
            "summary": {"content": title},
        },
        "header": {"title": {"tag": "plain_text", "content": title}, "template": template},
        "body": {"elements": [
            {
                "tag": "markdown", "content": text, "text_align": "left",
                "text_size": "normal_v2", "margin": "0px 0px 0px 0px",
                "element_id": STREAMING_ELEMENT_ID,
            },
            # spinning loader (element shape borrowed from hermes-fry-cards)
            {
                "tag": "markdown", "content": " ",
                "icon": {"tag": "custom_icon", "img_key": LOADING_IMG_KEY, "size": "16px 16px"},
                "element_id": LOADING_ELEMENT_ID,
            },
        ]},
    }


def sealed_card(text: str, meta: str) -> dict:
    return {
        "schema": "2.0",
        "config": {"width_mode": "default", "streaming_mode": False,
                   "summary": {"content": "✅ ZCode 完成"}},
        "header": {"title": {"tag": "plain_text", "content": "✅ ZCode 完成"}, "template": "green"},
        "body": {"elements": [
            {"tag": "markdown", "content": text, "text_size": "normal_v2"},
            {"tag": "hr"},
            # schema 2.0 has no "note" tag; notation-size markdown plays that role
            {"tag": "markdown", "content": meta, "text_size": "notation"},
        ]},
    }


def clip(text: str) -> str:
    text = text or ""
    return text if len(text) <= MAX_BODY_CHARS else text[:MAX_BODY_CHARS] + "\n\n…（内容过长已截断）"


# ── live card session (CardKit mode with message-PATCH fallback) ────────────

class LiveCard:
    """One streaming card bound to one active rollout session."""

    def __init__(self, session_name: str):
        self.session = session_name
        self.mode = None          # "cardkit" | "patch" — decided on create
        self.card_id = None       # cardkit card_id
        self.message_id = None    # patch mode: message_id
        self.last_update = 0.0
        self.turns = 0
        self.sealed = False
        self.last_text = ""
        self.meta = ""
        self.sequence = 0         # cardkit mutations need a monotonic sequence
        self.ctx = 0              # last turn's inputTokens ≈ current context size
        self.out_total = 0        # cumulative outputTokens across turns

    def _next_seq(self) -> int:
        self.sequence += 1
        return self.sequence

    # -- create -------------------------------------------------------------
    def create(self, text: str, model: str) -> None:
        card = streaming_card(clip(text) or "…")
        # try CardKit entity card first (typewriter streaming); body is a
        # {"type": "card_json", "data": "<card json string>"} envelope
        r = call_api("POST", "/cardkit/v1/cards",
                     {"type": "card_json", "data": json.dumps(card, ensure_ascii=False)})
        if r.get("code") == 0 and r.get("data", {}).get("card_id"):
            self.mode = "cardkit"
            self.card_id = r["data"]["card_id"]
            content = {"type": "card", "data": {"card_id": self.card_id}}
        else:
            log(f"[cardkit unavailable: {r.get('code')} {r.get('msg')}] falling back to message PATCH")
            self.mode = "patch"
            content = card
        send = call_api("POST", "/im/v1/messages?receive_id_type=chat_id",
                        {"receive_id": CHAT_ID, "msg_type": "interactive",
                         "content": json.dumps(content, ensure_ascii=False)})
        if send.get("code") != 0:
            log(f"send card failed: {send.get('code')} {send.get('msg')}")
            return
        self.message_id = send.get("data", {}).get("message_id")
        self.last_update = time.time()
        log(f"[{self.session}] card created ({self.mode}) message_id={self.message_id}")

    # -- update --------------------------------------------------------------
    def update(self, text: str, meta: str, force: bool = False) -> None:
        now = time.time()
        if not force and now - self.last_update < UPDATE_MIN_INTERVAL:
            return
        if self.mode == "cardkit":
            r = call_api("PUT", f"/cardkit/v1/cards/{self.card_id}/elements/{STREAMING_ELEMENT_ID}/content",
                         {"content": text, "sequence": self._next_seq()})
            if r.get("code") != 0:
                log(f"element update failed: {r.get('code')} {r.get('msg')}")
        elif self.message_id:
            r = call_api("PATCH", f"/im/v1/messages/{self.message_id}",
                         {"content": json.dumps(streaming_card(text), ensure_ascii=False)})
            if r.get("code") != 0:
                log(f"patch update failed: {r.get('code')} {r.get('msg')}")
        self.last_update = now

    # -- seal ----------------------------------------------------------------
    def seal(self, text: str, meta: str) -> None:
        if self.sealed:
            return
        self.sealed = True
        if not (self.card_id or self.message_id):
            return
        if self.mode == "cardkit":
            r = call_api("PUT", f"/cardkit/v1/cards/{self.card_id}",
                         {"card": {"type": "card_json", "data": json.dumps(sealed_card(text, meta), ensure_ascii=False)},
                          "sequence": self._next_seq()})
            if r.get("code") != 0:
                log(f"card update failed: {r.get('code')} {r.get('msg')}")
            r = call_api("PATCH", f"/cardkit/v1/cards/{self.card_id}/settings",
                         {"settings": json.dumps({"streaming_mode": False}),
                          "sequence": self._next_seq()})
            if r.get("code") != 0:
                log(f"close streaming failed (non-fatal): {r.get('code')} {r.get('msg')}")
        elif self.message_id:
            call_api("PATCH", f"/im/v1/messages/{self.message_id}",
                     {"content": json.dumps(sealed_card(text, meta), ensure_ascii=False)})
        log(f"[{self.session}] card sealed")


# ── rollout parsing ─────────────────────────────────────────────────────────

def local_hhmmss(iso_utc: str) -> str:
    """'2026-09-12T05:47:09.386Z' -> '13:47:09' in the machine's local timezone."""
    try:
        dt = datetime.fromisoformat(str(iso_utc).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone().strftime("%H:%M:%S")
    except ValueError:
        return str(iso_utc)[11:19]


def compact(n: int) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}m"
    return f"{n/1000:.1f}k" if n >= 1000 else str(n)


_BAR_STEPS = ("█", "▓", "▒", "░")  # density gradient, ported from hermes-fry-cards


def context_bar(used: int, total: int, width: int = 8) -> str:
    if total <= 0:
        return ""
    n = min(used / total * 100, 100) / 100 * width
    cells = []
    for i in range(width):
        pos = i + 0.5
        if pos <= n:
            cells.append("█" if n - pos >= 0.5 else "▓" if n - pos >= 0.25 else "▒")
        elif pos - 1 <= n:
            frac = n - (pos - 1)
            cells.append("▓" if frac > 0.66 else "▒" if frac > 0.33 else "░")
        else:
            cells.append("░")
    return "".join(cells)


def context_text(used: int, total: int) -> str:
    """'███▓▒░░░ 86.5k/200.0k (43%)' — hermes-fry-cards text_bar style."""
    if total <= 0:
        return compact(used)
    pct = min(used / total * 100, 100)
    return f"{context_bar(used, total)} {compact(used)}/{compact(total)} ({pct:.0f}%)"


def extract(entry: dict) -> dict | None:
    """Return turn info from one model_io line, or None if not usable."""
    if entry.get("type") not in (None, "model_io"):
        return None
    resp = entry.get("response") or {}
    return {
        "text": (resp.get("text") or "").strip(),
        "reasoning": (resp.get("reasoningText") or "").strip(),
        "tools": [t.get("name") for t in (resp.get("toolCalls") or []) if t.get("name")],
        "finish": resp.get("finishReason"),
        "model": (entry.get("model") or {}).get("modelId", ""),
        "duration": entry.get("durationMs"),
        "at": entry.get("completedAt", ""),
        "usage": resp.get("usage") or {},
    }


def teaser(text: str, limit: int = TEASER_CHARS) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + " ……"


def render_body(turn: dict, turns: int, state: dict) -> str:
    """Content only — model/turn info lives solely in the sealed card's footer."""
    parts = []
    if turn["text"]:
        parts.append(teaser(turn["text"]))
    elif turn["tools"]:
        parts.append("⚙️ 正在使用工具：" + "、".join(dict.fromkeys(turn["tools"])))
    elif turn["reasoning"]:
        parts.append("💭 " + teaser(turn["reasoning"]))
    if not parts:
        return state.get("last_body", "…")
    body = clip("\n\n".join(parts))
    state["last_body"] = body
    return body


# ── main loop ───────────────────────────────────────────────────────────────

def watch() -> None:
    if not CHAT_ID:
        sys.exit("missing FEISHU_NOTIFY_CHAT_ID env var (target chat for the live card)")
    log(f"watching {ROLLOUT_DIR} -> chat {CHAT_ID[:14]}…")
    offsets: dict[str, int] = {}       # file -> consumed bytes (start at EOF)
    states: dict[str, dict] = {}       # file -> {"last_body": str}
    cards: dict[str, LiveCard] = {}    # file -> live card
    last_mtime: dict[str, float] = {}

    while True:
        try:
            files = [p for p in ROLLOUT_DIR.glob("model-io-sess_*.jsonl") if p.is_file()]
            now = time.time()
            mtimes = {}
            for p in files:
                try:
                    mtimes[p.name] = p.stat().st_mtime
                except OSError:
                    continue
            if not mtimes:
                time.sleep(POLL_SEC)
                continue

            # seal idle cards
            for name, card in list(cards.items()):
                if not card.sealed and name in mtimes:
                    idle = now - mtimes[name]
                    if idle > SEAL_IDLE_SEC:
                        card.seal(card.last_text, card.meta)

            # newest = active session
            active = max(mtimes, key=lambda n: mtimes[n])

            for p in sorted(ROLLOUT_DIR.glob("model-io-sess_*.jsonl")):
                name = p.name
                try:
                    size = p.stat().st_size
                except OSError:
                    continue
                if name not in offsets:
                    offsets[name] = size        # start at EOF: no history replay
                    last_mtime[name] = size
                    continue
                if size <= offsets[name]:
                    if size < offsets[name]:    # truncated/rotated
                        offsets[name] = size
                    continue

                with open(p, encoding="utf-8", errors="replace") as fh:
                    fh.seek(offsets[name])
                    chunk = fh.read()
                    offsets[name] = fh.tell()

                card = cards.get(name)
                state = states.setdefault(name, {})
                for line in chunk.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        turn = extract(json.loads(line))
                    except ValueError:
                        continue
                    if not turn:
                        continue
                    if card is None or card.sealed:
                        card = LiveCard(name)
                        cards[name] = card
                        card.create("…", turn["model"])
                    card.turns += 1
                    u = turn["usage"]
                    card.ctx = int(u.get("inputTokens") or 0) or card.ctx
                    card.out_total += int(u.get("outputTokens") or 0)
                    meta = f"{turn['model'].split('/')[-1]} · {card.turns} 轮"
                    if card.ctx:
                        meta += f" · 上下文 {context_text(card.ctx, CTX_TOTAL)}"
                    if card.out_total:
                        meta += f" · 输出累计 {compact(card.out_total)}"
                    card.meta = meta + f" · 最后活动 {local_hhmmss(turn['at'])}"
                    body = render_body(turn, card.turns, state)
                    card.last_text = body
                    if turn["finish"] == "stop":
                        card.update(body, card.meta, force=True)
                        card.seal(body, card.meta)
                        card = None
                        cards[name] = LiveCard(name)  # placeholder; next turn opens new card
                        cards[name].sealed = True     # avoid instant reopen before real activity
                    else:
                        card.update(body, card.meta)
        except Exception as exc:  # keep the daemon alive no matter what
            import traceback
            log(f"watch loop error: {exc!r}\n{traceback.format_exc()}")
        time.sleep(POLL_SEC)


def main() -> None:
    if "--probe" in sys.argv:
        # parse the newest file once, print what a card body would look like
        files = sorted(ROLLOUT_DIR.glob("model-io-sess_*.jsonl"), key=lambda p: p.stat().st_mtime)
        if not files:
            sys.exit("no rollout files found")
        lines = [json.loads(l) for l in open(files[-1], encoding="utf-8") if l.strip()]
        state = {}
        for i, e in enumerate(lines):
            t = extract(e)
            if t:
                print(f"turn {i+1}: finish={t['finish']} tools={t['tools']} text={t['text'][:60]!r}")
                print("  body:", render_body(t, i + 1, state)[:200].replace("\n", " | "))
        return
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    watch()


if __name__ == "__main__":
    main()
