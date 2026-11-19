"""Claude API client for Nobody's Town: prompt caching, retries, cost meter, hard budget cap.
MODE: 'live' calls the API; 'mock' forbids API calls (dry runs use the mock brain instead)."""
import json, os, time, threading, urllib.request, urllib.error

KEY_PATH = os.path.expanduser("~/.secrets/anthropic_key")
API = "https://api.anthropic.com/v1/messages"
NO_THINK = {"resident", "talk", "referee", "referee_big", "world", "world_big", "law"}
THINK_OFF = {}  # model -> the thinking type that turns thinking off (learned from the API)
MODELS = {"resident": "claude-haiku-5-5", "talk": "claude-sonnet-5-5",  # conversations: Sonnet (chosen Nov 17 after the Haiku vs Sonnet A/B test)
           "referee": "claude-haiku-5-5", "referee_big": "claude-sonnet-5-5",
           "world": "claude-haiku-5-5", "world_big": "claude-sonnet-5-5",  # the world step and threads (Nov 18)
           "law": "claude-sonnet-5-5",  # the town clerk who writes down what a passed measure binds (Nov 18; rare, so the better model)
           "editor": "claude-sonnet-5-5"}
# $ per million tokens (checked Nov 17, 2026 on platform.claude.com/docs/en/about-claude/pricing)
PRICES = {"claude-haiku-5-5": {"in": 0.10, "out": 0.50, "cache_write": 0.125, "cache_read": 0.01},
          "claude-sonnet-5-5": {"in": 2.00, "out": 10.00, "cache_write": 2.50, "cache_read": 0.20}}


class BudgetExceeded(Exception): pass
class MockModeError(Exception): pass


class Meter:
    def __init__(self, budget_usd):
        self.budget = budget_usd; self.spent = 0.0; self.calls = 0; self.by_role = {}; self.lock = threading.Lock()
        self.tokens = {"in": 0, "out": 0, "cache_write": 0, "cache_read": 0}

    def add(self, role, model, usage):
        p = PRICES[model]
        cost = (usage.get("input_tokens", 0) * p["in"] + usage.get("output_tokens", 0) * p["out"]
                + usage.get("cache_creation_input_tokens", 0) * p["cache_write"] + usage.get("cache_read_input_tokens", 0) * p["cache_read"]) / 1e6
        with self.lock:
            self.spent += cost; self.calls += 1
            r = self.by_role.setdefault(role, {"calls": 0, "usd": 0.0}); r["calls"] += 1; r["usd"] += cost
            for k, uk in (("in", "input_tokens"), ("out", "output_tokens"), ("cache_write", "cache_creation_input_tokens"), ("cache_read", "cache_read_input_tokens")):
                self.tokens[k] += usage.get(uk, 0)
        return cost

    def check(self):
        if self.spent >= self.budget: raise BudgetExceeded(f"spent ${self.spent:.2f} of ${self.budget:.2f} cap")

    def summary(self): return {"usd": round(self.spent, 4), "calls": self.calls, "by_role": self.by_role, "tokens": self.tokens}


class LLM:
    def __init__(self, mode="mock", budget_usd=20.0, log_path=None):
        self.mode = mode; self.meter = Meter(budget_usd); self.log_path = log_path; self._log_lock = threading.Lock()
        self.key = open(KEY_PATH).read().strip() if mode == "live" else None

    def call(self, role, system, messages, max_tokens=600, cache_system=True, temperature=1.0):
        """system: list of text blocks (stable prefix first, so it caches). Returns (text, usage)."""
        if self.mode != "live": raise MockModeError("API call attempted in mock mode")
        self.meter.check()
        model = MODELS[role]
        sys_blocks = [{"type": "text", "text": s} for s in system]
        if cache_system and sys_blocks: sys_blocks[-1]["cache_control"] = {"type": "ephemeral"}
        body = {"model": model, "max_tokens": max_tokens, "system": sys_blocks, "messages": messages, "temperature": temperature}
        # 5.5 models think by default and can spend the whole token budget before answering.
        # Residents and the referee answer directly (fast, cheap, in character); the editor keeps its default thinking.
        if role in NO_THINK: body["thinking"] = {"type": THINK_OFF.get(model, "disabled")}
        data = json.dumps(body).encode()
        for attempt in range(6):
            req = urllib.request.Request(API, data=data, headers={"x-api-key": self.key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    out = json.loads(resp.read())
                text = "".join(b.get("text", "") for b in out.get("content", []) if b.get("type") == "text")
                usage = out.get("usage", {}); cost = self.meter.add(role, model, usage)
                self._log({"role": role, "model": model, "usage": usage, "usd": round(cost, 6)})
                return text, usage
            except urllib.error.HTTPError as e:
                msg = e.read().decode(errors="replace")[:300]
                if e.code == 400 and "between_tools" in msg and body.get("thinking", {}).get("type") != "between_tools":  # this model's way of saying "no thinking" (checked per request: thread-safe)
                    THINK_OFF[model] = "between_tools"; body["thinking"] = {"type": "between_tools"}; data = json.dumps(body).encode(); continue
                if e.code in (429, 500, 502, 503, 529) and attempt < 5: time.sleep(2 ** attempt + 1); continue
                raise RuntimeError(f"API error {e.code}: {msg}")
            except (urllib.error.URLError, TimeoutError) as e:
                if attempt < 5: time.sleep(2 ** attempt + 1); continue
                raise
        raise RuntimeError("API retries exhausted")

    def call_json(self, role, system, messages, max_tokens=600, **kw):
        text, usage = self.call(role, system, messages, max_tokens, **kw)
        return parse_json(text), text

    def _log(self, rec):
        if not self.log_path: return
        with self._log_lock, open(self.log_path, "a") as f: f.write(json.dumps(rec) + "\n")


def parse_json(text):
    """Extract the first JSON object from model text."""
    s = text.strip()
    if s.startswith("```"): s = s.split("\n", 1)[1].rsplit("```", 1)[0]
    i = s.find("{")
    if i < 0: return None
    depth, instr, esc = 0, False, False
    for j in range(i, len(s)):
        ch = s[j]
        if instr:
            if esc: esc = False
            elif ch == "\\": esc = True
            elif ch == '"': instr = False
        elif ch == '"': instr = True
        elif ch == "{": depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try: return json.loads(s[i:j + 1])
                except json.JSONDecodeError: return None
    return None


def ping(llm):
    """One tiny live call to confirm the key + credits work."""
    t, u = llm.call("resident", ["You are a test."], [{"role": "user", "content": "Reply with exactly: town engine online"}], max_tokens=20, cache_system=False)
    return t, u, llm.meter.summary()
