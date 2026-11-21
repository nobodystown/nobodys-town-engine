"""Claude API client for Nobody's Town: prompt caching, retries, cost meter, hard budget cap.
MODE: 'live' calls the API; 'mock' forbids API calls (dry runs use the mock brain instead)."""
import json, os, time, threading, urllib.request, urllib.error

KEY_PATH = os.path.expanduser("~/.secrets/anthropic_key")
API = "https://api.anthropic.com/v1/messages"
# Outside minds (Nov 20, Aaron's idea): a few residents think with another lab's model, through OpenRouter (one key, one domain).
# A resident's model is fixed for life. Only their own plans, reflections and words go to it; the referee, world step,
# clerk and editor stay on Claude. OpenRouter reports each call's real cost, so the budget cap covers these too.
OR_KEY_PATH = os.path.expanduser("~/.secrets/openrouter_key")
OR_API = "https://openrouter.ai/api/v1/chat/completions"
OUTSIDE_GIVE_UP_S = 30  # fix 9: seconds to wait for an outside model before falling back to Claude
OUTSIDE = {"gpt": "openai/gpt-6.2-sol", "gemini": "google/gemini-4-carbon", "deepseek": "deepseek/deepseek-v4.1-flash-1017"}
OR_REASON = {}  # model -> the reasoning setting it accepts (some can't turn thinking off; then the least, hidden)
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

    def add_cost(self, role, model, cost, usage):
        """For outside models: OpenRouter reports the real price of each call."""
        with self.lock:
            self.spent += cost; self.calls += 1
            for key in (role, f"{role}@{model.split('/')[0]}"):
                r = self.by_role.setdefault(key, {"calls": 0, "usd": 0.0}); r["calls"] += 1; r["usd"] += cost
            self.tokens["in"] += usage.get("input_tokens", 0); self.tokens["out"] += usage.get("output_tokens", 0)
        return cost

    def check(self):
        if self.spent >= self.budget: raise BudgetExceeded(f"spent ${self.spent:.2f} of ${self.budget:.2f} cap")

    def summary(self): return {"usd": round(self.spent, 4), "calls": self.calls, "by_role": self.by_role, "tokens": self.tokens}


class LLM:
    def __init__(self, mode="mock", budget_usd=20.0, log_path=None):
        self.mode = mode; self.meter = Meter(budget_usd); self.log_path = log_path; self._log_lock = threading.Lock()
        self.key = open(KEY_PATH).read().strip() if mode == "live" else None
        self.or_key = open(OR_KEY_PATH).read().strip() if mode == "live" and os.path.exists(OR_KEY_PATH) else None

    def call(self, role, system, messages, max_tokens=600, cache_system=True, temperature=1.0, mind=None):
        """system: list of text blocks (stable prefix first, so it caches). Returns (text, usage).
        mind: an outside model id (OpenRouter) for a resident who thinks with another lab's model; None = Claude."""
        if self.mode != "live": raise MockModeError("API call attempted in mock mode")
        self.meter.check()
        if mind:
            try: return self._call_outside(role, mind, system, messages, max_tokens, temperature)
            except Exception as ex:  # an outage must not stop the town: this one call goes to Claude, and the log says so (the audit counts these)
                self._log({"role": role, "model": mind, "fallback": True, "error": str(ex)[:200]})
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

    def _call_outside(self, role, model, system, messages, max_tokens, temperature):
        if not self.or_key: raise RuntimeError("no OpenRouter key")
        flat = lambda c: c if isinstance(c, str) else "\n".join(b.get("text", "") for b in c)
        msgs = [{"role": "system", "content": "\n\n".join(system)}] + [{"role": m["role"], "content": flat(m["content"])} for m in messages]
        body = {"model": model, "messages": msgs, "max_tokens": max_tokens, "temperature": temperature, "usage": {"include": True},
                "reasoning": OR_REASON.get(model, {"enabled": False})}
        # fix 9 (season break): give up after about 30 seconds in all and fall back to Claude (logged), instead of hanging for minutes
        # until a 504 (8 times in Q2). Odds and dice are unaffected: this only decides how long to wait for the outside model.
        t_end = time.time() + OUTSIDE_GIVE_UP_S
        for attempt in range(5):
            left = t_end - time.time()
            if left < 3: raise RuntimeError(f"OpenRouter gave no answer within {OUTSIDE_GIVE_UP_S}s")
            req = urllib.request.Request(OR_API, data=json.dumps(body).encode(), headers={"Authorization": f"Bearer {self.or_key}", "Content-Type": "application/json", "X-Title": "Nobody's Town"})
            try:
                with urllib.request.urlopen(req, timeout=left) as resp: out = json.loads(resp.read())
                if out.get("error"): raise RuntimeError(str(out["error"])[:200])
                text = (out["choices"][0]["message"].get("content") or "")
                u = out.get("usage", {}) or {}
                usage = {"input_tokens": u.get("prompt_tokens", 0), "output_tokens": u.get("completion_tokens", 0)}
                cost = self.meter.add_cost(role, model, float(u.get("cost") or 0.0), usage)
                self._log({"role": role, "model": model, "usage": usage, "usd": round(cost, 6), "outside": True})
                return text, usage
            except urllib.error.HTTPError as e:
                msg = e.read().decode(errors="replace")[:300]
                if e.code == 400 and "mandatory" in msg and body["reasoning"].get("enabled") is False:
                    OR_REASON[model] = body["reasoning"] = {"effort": "minimal", "exclude": True}; continue
                if e.code in (408, 429, 500, 502, 503, 504, 529) and attempt < 4 and t_end - time.time() > 2 ** attempt + 4: time.sleep(2 ** attempt + 1); continue
                raise RuntimeError(f"OpenRouter {e.code}: {msg}")
            except (urllib.error.URLError, TimeoutError, KeyError, IndexError):
                if attempt < 4 and t_end - time.time() > 2 ** attempt + 4: time.sleep(2 ** attempt + 1); continue
                raise
        raise RuntimeError("OpenRouter retries exhausted")

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
