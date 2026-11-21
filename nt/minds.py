"""Resident minds: memory stream, prompts, daily plan, conversation turns. Live (Claude) + Mock (dry-run only).
Sterile by design: residents get who they are, where they are, what they can see and what they remember. Nothing else.
No suggestions, no meta-talk, no exact numbers they wouldn't be thinking about, and no rankings of ours: each resident
rates how much their own memories matter."""
import datetime as dt, json, math, random, re
from .world import plural
from . import econ, law

# ======================================================================================================
# The resident prompt is built from labeled BLOCKS. Each block is one function, documented, and part of the
# published rule fingerprint. Blocks can be added, removed or swapped; nothing in them ranks or suggests anything.
#   SYSTEM:  frame -> identity -> life (interests, faith, people, role pack)
#   USER:    today (only what they'd notice) -> memory -> new memories to rate -> yesterday -> notes -> response format
# ======================================================================================================

# The one line of temperament framing is being A/B tested (Nov 18): "fact" = a plain fact about who they are; "none" = nothing at all.
FRAME_VARIANT = "fact"
FRAME_LINES = {"fact": "You have your own temperament, moods, wants and faults.\n", "none": ""}
WORLD_RULES = """You are {name}.
You know only what you have seen, heard, been told or remember. You know nothing about anything that happens after today's date.
{frame}
Reply with one JSON object only, in the format you are asked for."""

PLAN_FORMAT = """Live your day as yourself. Return JSON:
{"thoughts": ["0-3 short thoughts, in your own words"],
 "feelings": {"<person's full name>": <-20..20>}  (optional: only if something changed how you feel about someone),
 "rate": {"<number of a NEW memory above>": <1-10, how much it matters to you>},
 "slots": [ {"slot": "morning"|"midday"|"evening"|"night", "place": "<place id>", "do": "<action>", "target": "<full name, measure id, or null>", "amount": <dollars or null>, "detail": "<what exactly, in your own words>"} x4 ]}
Actions the town understands (alphabetical): apply_job, approve_loan, ask_loan, attempt, bank_loan, build, buy, chores, court, declare_candidacy, deny_loan, deposit, dig, eat_at_diner, end_relationship, enforce, explore, farm, fire, fish, give, hire, home, lend, leave_town, pay, phone, propose_marriage, propose_measure, quit_job, repair, school, sell, set_price, set_wage, shop, shop_at, side_work, sleep, start_business, talk, trip, turn_down, visit, vote, withdraw, work, write_letter.
- talk, phone, court, ask_loan, propose_marriage, end_relationship: target = a person.
- vote: target = a candidate's full name or a measure id; detail = "yes" or "no" for a measure.
- chores: everyday work around the house, yard, farm or errands; say what in detail.
- repair: fix up your home; amount = dollars you put into it (or null for all of it); say what.
- side_work: odd jobs or extra hours for pay; say what. sell: say what and to whom.
- buy: say what (add "on time" to pay in installments); amount = the most you'll pay, or null.
- shop_at: where your household buys its groceries from now on ("the general store" or "the county seat").
- bank_loan: amount = dollars, detail = what it's for; target = a bank in town or its owner, or null for the bank in the county seat.
- deposit / withdraw: amount = dollars (target = which bank, or null).
- apply_job / hire: target = the person who does the hiring / the person you hire; amount = weekly pay offered, or null.
- turn_down (if someone asked you for work): target = that person; detail = what you tell them, or null.
- set_price (if you run the store or the diner): store: amount = percent above (+) or below (-) county-seat prices; diner: amount = cents for a meal.
- set_wage (if people work for you): amount = dollars a week; target = one worker, or null for everyone.
- approve_loan / deny_loan (if you own a bank): target = the applicant; amount; detail = the rate and months.
- enforce (if you're the town's lawman): target = the person; detail = which town law.
- trip: go away for a while and come back (to see kin, a funeral, business elsewhere); detail = where; amount = how many days. leave_town is for leaving for good.
- attempt: anything not listed; describe exactly what you do."""

SAY_FORMAT = """Return JSON: {"say": "<exactly what you say out loud, the way you'd really say it>", "aside": "<private thought, optional>", "end": true|false, "deal": null | {"type": "pay"|"lend"|"promise"|"agree"|"refuse", "amount": <number or null>, "terms": "<short>"}}
Real speech: usually short; people don't repeat back what was just said to them, and they don't recap the conversation.
Speak of what you actually know: your memories and what's in front of you. Wondering or guessing aloud is fine; passing on news you never heard is not.
Set end=true when you want to stop talking. Only include a deal if you actually commit to something."""

MONEY_WORDS = re.compile(r"\$|money|loan|lend|owe|debt|pay|price|cost|buy|sell|wage|rent|mortgage|savings|dollar|cash|afford", re.I)
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# ---- role packs: the plain texture of a working life (period-accurate; knowing your own job is not steering)
INDUSTRY_DAYS = {"mill": "shifts at the mill: the noise, the dust, the whistle at noon", "mine": "shifts underground: the cage down at dawn, the dark, the dust",
                 "cannery": "shifts on the cannery line: the smell, the steam, the season's rush", "oil": "work on the rigs: long hours, mud, the crew boss",
                 "lumber": "work in the woods and at the mill: saws, the log trucks, the foreman", "timber": "work in the woods: saws, the log trucks, the foreman",
                 "ferry": "runs on the ferry: the schedule, the weather, the regulars", "boat": "work at the boatyard: planking, caulk, paint",
                 "fishery": "work with the fishing boats: early starts, nets, the catch", "fish": "work with the boats: early starts, nets, the catch",
                 "feedlot": "work at the feedlot: feeding, cattle, the smell that follows you home", "grain": "work at the grain mill: sacks, the elevator, harvest rush",
                 "farm equipment": "work at the dealer: tractors, parts, farmers who want it fixed yesterday", "ranch": "work supplying the ranches: feed, wire, saddles, talk",
                 "motor court": "work at the motor court: travelers, linens, the neon sign", "hotel": "work at the hotel: guests, linens, the summer rush",
                 "resort": "work at the lodge: guests, the boats, the summer season", "depot": "work at the railroad depot: freight, the schedule, the telegraph",
                 "quarry": "work at the quarry: blasting days, stone dust, heavy loads", "sugar": "work at the sugar mill: cane, heat, the grinding season",
                 "paper": "work at the paper mill: the smell, the shifts, the river", "turpentine": "work at the turpentine still: pine gum, the woods, the heat",
                 "salt": "work at the salt works: brine pans, sun, heavy rakes", "shrimp": "work on the shrimp boats: nets, ice, the season", "oyster": "work on the oyster beds: tongs, cold water, the shucking house",
                 "ice": "work at the ice house: cutting, hauling, sawdust", "copper": "shifts at the copper mine: heat, ore, the company store"}
JOB_DAYS = {"homemaker": "running the house: meals, wash day, ironing, the garden, the children, neighbors at the door",
            "runs the diner": "up before dawn for the breakfast trade; you hear everything that's said at the counter",
            "runs the general store": "opening at seven, stocking shelves, folks buying on credit you keep in the book",
            "schoolteacher": "the schoolhouse: lessons, a stove to keep going, every child in town and their parents",
            "nurse": "tending the sick, house calls with the doctor, knowing more than you can say",
            "postmaster": "sorting the mail; you know who gets letters from where",
            "telephone operator": "the switchboard: you connect every call in town",
            "barber": "the chair, the strop, the radio, and all the talk that goes with a haircut",
            "mechanic": "engines, grease, parts that take a week to come", "carpenter": "jobs around town: porches, roofs, cabinets, whatever comes",
            "farmer": "the fields, the animals, the weather, the price of feed", "fisherman": "the boat, the nets, early mornings on the water",
            "trucker": "long hauls out of town and back", "bookkeeper": "columns of figures for whoever pays you to keep them",
            "newspaper editor": "the weekly paper: news, notices, ads, the press on Wednesday night", "handyman": "odd jobs for whoever needs a hand",
            "preacher's assistant": "the church: Sunday, visits to the sick, weddings and funerals", "salesman": "the road and the sample case, small towns and front porches",
            "town marshal": "keeping the peace part-time: the one-cell jail behind the town hall, the county sheriff a phone call away, everybody's business",
            "deputy sheriff": "the county's man in town: the patrol car, the county seat on the telephone, the one cell behind the town hall",
            "town doctor": "the office, house calls at all hours, births and deaths", "seamstress": "dresses, mending, alterations, a needle always going",
            "store clerk": "the counter, the shelves, the customers you know by name", "diner cook": "the grill, the breakfast rush, the smell of bacon",
            "retired": "your time is your own now", "out of work": "no job right now", "looking for work": "no job yet in this town"}


def trait_words(t):
    w = []
    def band(v, lo, hi): return lo if v < 35 else hi if v > 65 else None
    for k, lo, hi in (("openness", "set in their ways, distrusts new ideas", "curious and imaginative"),
                      ("conscientiousness", "careless and impulsive", "disciplined and dependable"),
                      ("extraversion", "quiet and private", "outgoing and talkative"),
                      ("agreeableness", "blunt, competitive, quick to quarrel", "kind, trusting, eager to please"),
                      ("neuroticism", "calm and steady", "anxious, moody, easily wounded")):
        b = band(t[k], lo, hi)
        if b: w.append(b)
    return "; ".join(w) or "fairly ordinary in temperament"


def feeling_word(a):
    return "very fond of them" if a >= 50 else "fond of them" if a >= 20 else "bitter toward them" if a <= -50 else "cool toward them" if a <= -20 else None


def role_pack(w, p):
    j = (p.get("job") or "").lower()
    if p["age"] < 18:
        return "School on weekdays, chores at home, and whatever you and your friends get up to." if p.get("education") == "in school" else "You're not in school."
    if j.startswith("owner"): return f"You own {w.companies['co1']['name']}: the payroll every Friday, the orders, the books."
    if j.startswith("works at"):
        ind = next((c["industry"] for c in w.companies.values() if c["name"] in p["job"]), "")
        return "Your days: " + next((v for k, v in INDUSTRY_DAYS.items() if k in ind.lower()), "shift work") + "."
    return "Your days: " + next((v for k, v in JOB_DAYS.items() if k in j), "whatever the day brings") + "."


# ---------------------------------------------------------------- SYSTEM blocks
def identity_block(w, p):
    h = w.households[p["household"]]
    fam = [f"{w.people[i]['name']} ({w.people[i]['role']}, {w.people[i]['age']})" for i in h["members"] if i != p["id"] and w.people[i]["alive"]]
    return "\n".join([f"{p['name']}, {p['sex']}, age {p['age']} (born {p['born']}). At home: {p['role']}.",
                      f"Job: {p['job'] or 'none'}" + (f" (about ${ww:.0f} a week)" if (ww := econ.wage_week(w, p)) else "") + f". Schooling: {p['education']}. Health: {p['health']}." + (" Served in the war." if p["veteran"] else ""),
                      *([f"What you want most out of life: {p['goal']}."] if p.get("goal") else []),
                      f"Temperament: {trait_words(p['traits'])}. Quirks: {', '.join(p['quirks'])}.",
                      f"Household: the {plural(h['surname'])}. Lives with: {', '.join(fam) or 'nobody'}. Home: {h['home'] if h['home'] != 'none' else 'none right now'}."
                      + (f" At home you have {econ.owns_text(w, h)}." if h.get("owns") else ""),
                      f"Town: {w.town['name']}, {w.gen['region']}. The main employer is {w.companies['co1']['name']}."])


def life_block(w, p):
    rel = []
    for oid, r in p["rel"].items():
        if oid in w.people and "family" not in r["tags"]:
            fw = feeling_word(r["affinity"])  # how they feel now; the history behind it lives in their memories
            if fw: rel.append(f"{w.people[oid]['name']}: {fw}")
    lines = [role_pack(w, p)]
    if p.get("interests"): lines.append("What you like to do: " + ", ".join(p["interests"]) + ".")
    if p.get("faith"): lines.append(f"Church: you {p['faith'].replace('goes', 'go').replace('doesn' + chr(39) + 't go', 'don' + chr(39) + 't go').replace('keeps', 'keep')}.")
    if rel: lines.append("Other people: " + "; ".join(rel[:10]))
    return "\n".join(lines)


def persona_block(w, p): return identity_block(w, p) + "\n" + life_block(w, p)  # kept for tools that print the persona


class Memory:
    """A resident's own memories. Nothing we write ranks them: each starts unrated (neutral) and the resident rates it."""
    CAP, KEEP, NEUTRAL = 450, 360, 5
    def __init__(self): self.items = []; self.next_id = 1
    def add(self, day, slot, text, importance=None, tags=()):  # importance from the engine is ignored on purpose
        self.items.append({"id": self.next_id, "day": day, "slot": slot, "text": text, "imp": None, "tags": set(tags)}); self.next_id += 1
        if len(self.items) > self.CAP:  # forgetting: old memories that mattered little to them fade first
            keep = sorted(self.items, key=lambda m: self.w(m) * 3 + m["day"] / 30, reverse=True)[: self.KEEP]
            self.items = sorted(keep, key=lambda m: (m["day"], m["slot"]))
    def w(self, m): return m["imp"] if m["imp"] is not None else self.NEUTRAL
    def unrated(self, k=15): return [m for m in self.items if m["imp"] is None][-k:]
    def rate(self, ratings):
        by = {m["id"]: m for m in self.items}
        for k, v in (ratings or {}).items():
            try: m = by.get(int(k)); v = max(1, min(10, int(v)))
            except (TypeError, ValueError): continue
            if m: m["imp"] = v
    def recall(self, day, context_words, k=14, exclude=()):
        cw = {x.lower() for x in context_words if len(x) > 2}; ex = {m["id"] for m in exclude}
        def score(m):
            rec = 0.97 ** max(0, day - m["day"])
            rel = len(cw & {x.lower().strip(".,!?") for x in m["text"].split()}) * 0.15
            return rec + self.w(m) / 10 + rel
        top = sorted((m for m in self.items if m["id"] not in ex), key=score, reverse=True)[:k]
        return sorted(top, key=lambda m: (m["day"], m["slot"]))
    def since(self, day): return [m for m in self.items if m["day"] >= day]
    def recent(self, day, days=3): return [m for m in self.items if m["day"] >= day - days and not m["text"].startswith("Talked with")]


def weather_words(wx):
    """Only notable weather is mentioned: a disaster, real extremes, rain or snow. An ordinary day goes unremarked."""
    t = wx.get("temp")
    if t is None: return ""
    if not (wx.get("disaster") or t < 22 or t > 96 or wx.get("sky") == "snow"): return ""  # rain is ordinary; you see it, you don't remark on it
    feel = "Bitter cold" if t < 22 else "Cold" if t < 40 else "Cool" if t < 60 else "Warm" if t < 80 else "Hot" if t <= 96 else "Blistering hot"
    sky = {"clear": "clear", "cloudy": "overcast", "rain": "raining", "snow": "snowing"}.get(wx.get("sky"), "")
    return f"{feel} and {sky}." + (f" A {wx['disaster']} is hitting town." if wx.get("disaster") else "")


def body_words(p):
    n = p["needs"]; out = []
    if n["hunger"] > 70: out.append("You're hungry.")
    if n["energy"] < 25: out.append("You're worn out.")
    if n["mood"] < 25: out.append("You've been feeling low.")
    if p["illness"]: out.append(f"You're sick with {p['illness']['name']}.")
    if p["injury"]: out.append("You're hurt and still healing.")
    return " ".join(out)


MOOD_WORDS = {"good": "You woke up in good spirits.", "sour": "You woke up out of sorts.", "tired": "You slept badly."}


# ---------------------------------------------------------------- USER blocks
def today_block(w, p):
    """Only what this person would notice today. No standing reminders about money or town business."""
    from .world import SLOTS
    h = w.households[p["household"]]; t = w.town; off = t["offices"]; in_office = p["id"] == off["mayor"] or p["id"] in off["council"]
    here = [w.people[i]["name"] for i in w.people if i != p["id"] and w.people[i]["alive"] and w.people[i]["location"] == p["location"] and not w.people[i]["offtown"]]
    notes = []
    if h["savings"] < 0: notes.append("The household has run out of money.")
    pl = w.places.get(h["place"], {})
    if h.get("homeless"): notes.append("You have no home of your own right now.")
    elif h.get("behind"): notes.append(f"You're {h['behind']} month{'s' if h['behind'] > 1 else ''} behind on the {'rent' if h['home'] == 'rented' else 'mortgage'}.")
    if pl.get("burned"): notes.append(f"Your house burned down. Rebuilding would cost about ${int(h.get('repairs_needed', 0))}.")
    elif h.get("repairs_needed", 0) > 0 and pl.get("condition", 1) < 0.95: notes.append(f"Your house is damaged; fixing it would cost about ${int(h['repairs_needed'])}.")
    if p["pregnant"] and w.day - p["pregnant"]["start"] >= 60: notes.append("You're expecting a baby.")
    sick = [q for q in [p] + [w.people[i] for i in h["members"] if i != p["id"]] if q["alive"] and (q.get("illness") or q.get("injury"))]
    if sick:  # fix 2: someone at home is sick or hurt, so you'd know who the doctor is
        from .routine import doctor_line
        notes.append(doctor_line(w))
    if p.get("items"): notes.append("You have: " + "; ".join(it["desc"] for it in p["items"]) + ".")
    if p["age"] < 18 and w.date.weekday() < 5 and p["education"] == "in school": notes.append("It's a school day.")
    for e in t["elections"]:
        if e["status"] == "scheduled" and p["age"] >= 18:  # fix 11 (season break): the posted notice is public fact, as election day is
            import datetime as _dt
            when = (w.date + _dt.timedelta(days=e["day"] - w.day)).strftime("%A, %B %d")
            notes.append(f"Notice is posted at the town hall: {t['name']} elects a mayor and a council of three on {when}. Anyone {t['charter']['voting_age']} or over may put their name in."
                         + (f" Running so far: {', '.join(w.name(c) + ' (' + e['cand_office'][c] + ')' for c in e['candidates'])}." if e["candidates"] else " Nobody has put their name in yet."))
        if e["status"] == "open": notes.append(f"Today is {'the runoff' if e.get('runoff') else 'election day'}. On the ballot: {', '.join(w.name(c) + ' (' + e['cand_office'][c] + ')' for c in e['candidates']) or 'nobody yet'}. Polls close tonight.")
    if in_office and w.date.weekday() == t["charter"].get("meeting_weekday", 1):
        opens = [m for m in t["motions"] if m["status"] == "open"]
        notes.append(f"Tonight is the council meeting at the town hall; you sit on it as {'mayor' if p['id'] == off['mayor'] else 'a council member'}."
                     + ("".join(f" On the agenda: {m['id']}, \"{m['text']}\" (proposed by {w.name(m['by'])})." for m in opens) if opens else ""))
    tl = law.law_lines(w, 8)
    if tl: notes.append("Town laws in force: " + " | ".join(tl) + ".")
    if p["location"] == "store" and econ.shop_runners(w, "store"):
        lv = w.shops["store"]["level"]; pc = round((lv - 1) * 100)
        notes.append("Prices here are about the same as in the county seat." if pc == 0 else f"Prices here run about {abs(pc)}% {'above' if pc > 0 else 'below'} the county seat's.")
    if p["location"] == "diner": notes.append(f"A meal here costs {int(round(w.shops['diner']['meal'] * history_P(w) * 100))} cents.")
    oh = w.places.get(p["location"], {}).get("household")
    if oh and oh != p["household"] and oh in w.households and w.households[oh].get("owns"):
        notes.append(f"The {plural(w.households[oh]['surname'])} have {econ.owns_text(w, w.households[oh])}.")
    mine = [x for x in getattr(w, "threads", []) if x["status"] == "open" and p["id"] in x["people"]]
    if mine: notes.append("Unsettled in your life: " + "; ".join(f"{x['title']} (since {x['opened']})" for x in mine[-4:]) + ".")
    on = [v for v in w.places.values() if v.get("kind") == "event"]
    if on: notes.append("Going on in town: " + "; ".join(f"{v['name']} ({v['hours']}" + (f", {int(round(float(v['price']) * 100))} cents" if v.get("price") and float(v["price"]) < 1 else f", ${v['price']}" if v.get("price") else ", free") + f", through {v['until_date']}; place id {v['id']})" for v in on) + ".")
    return "\n".join(x for x in [f"It is {w.date.strftime('%A, %B %d, %Y')}, {SLOTS[w.slot]}. {weather_words(w.weather.get('today', {}))}".strip(),
                                  f"You are at {w.places.get(p['location'], {}).get('name', p['location'])}." + (f" With you: {', '.join(here)}." if here else ""),
                                  " ".join(x for x in (MOOD_WORDS.get(p.get("mood_today")), body_words(p)) if x), " ".join(notes)] if x)


def history_P(w):
    from . import history
    return history.price_index(w.date.year)


def places_block(w): return "Places (id = name): " + "; ".join(f"{k} = {v['name']}" for k, v in w.places.items())


def memory_block(memories, new=()):
    lines = ["What you remember:"] + [f"- {m['text']}" for m in memories]
    if new: lines += ["", "NEW since you last planned (numbered so you can rate them):"] + [f"[{m['id']}] {m['text']}" for m in new]
    return "\n".join(lines)


def situation_block(w, p, memories, extra, exact_money=False, new=()):
    h = w.households[p["household"]]
    parts = [today_block(w, p)]
    if exact_money: parts.append(f"Household money: ${int(h['savings'])} saved, ${int(h['debt'])} owed.")
    parts += [places_block(w), memory_block(memories, new)]
    if extra: parts.append(extra)
    return "\n".join(parts)


REFLECT_FORMAT = """Looking back over your week, what do you make of it? Answer as yourself, privately, in your own words: up to 3 short thoughts, one sentence each.
Reply with only JSON: {"reflections": ["...", "..."]}"""


# ------------------------------------------------------------------ live mind
class LiveMind:
    def __init__(self, llm): self.llm = llm
    def system(self, w, p): return [WORLD_RULES.format(name=p["name"], frame=FRAME_LINES[FRAME_VARIANT]), identity_block(w, p) + "\n" + life_block(w, p)]

    def plan(self, w, p, memories, extra="", new=()):
        msg = situation_block(w, p, memories, extra, new=new) + "\n\n" + PLAN_FORMAT
        out, raw = self.llm.call_json("resident", self.system(w, p), [{"role": "user", "content": msg}], max_tokens=900, mind=p.get("model"))
        return out or {"slots": [], "thoughts": [], "feelings": {}, "_raw": raw[:200]}

    def reflect(self, w, p, week):
        """Sunday: the resident looks back on their own week, in their own words (Generative Agents-style reflection). We supply no topics."""
        lines = "\n".join(f"- {m['text']}" for m in week[-40:]) or "- (a quiet week)"
        msg = (f"{today_block(w, p)}\nIt's Sunday. What you remember of this past week:\n{lines}\n\n" + REFLECT_FORMAT)
        out, raw = self.llm.call_json("resident", self.system(w, p), [{"role": "user", "content": msg}], max_tokens=400, mind=p.get("model"))
        return [str(x)[:300] for x in ((out or {}).get("reflections") or [])][:3]

    def say(self, w, p, other, transcript, memories, purpose, mind_seed=None, chance=False, last=None):
        hist = "\n".join(f"{s}: {t}" for s, t in transcript) or "(you are starting the conversation)"
        exact = bool(MONEY_WORDS.search(purpose or "") or MONEY_WORDS.search(hist))
        where = w.places.get(p["location"], {}).get("name", "here")
        who = f"{other['name']} ({other['age']}, {other['job'] or 'no job'})"
        lead = (f"You've run into {who} at {where}." if chance else f"You are talking with {who}.") + (f" You wanted to: {purpose}." if purpose else "")
        if mind_seed: lead += f"\nOn your mind today: {mind_seed}"
        if last: lead += f"\n{last}"
        # The speaker's situation is identical on every turn of one conversation, so it goes first and is cached;
        # only the growing transcript is new each turn (prompt caching, approved Nov 18).
        h = w.households[p["household"]]
        money = f"Household money: ${int(h['savings'])} saved, ${int(h['debt'])} owed.\n" if exact else ""
        content = [{"type": "text", "text": situation_block(w, p, memories, ""), "cache_control": {"type": "ephemeral"}},
                   {"type": "text", "text": f"{money}\n{lead}\nConversation so far:\n{hist}\n\n" + SAY_FORMAT}]
        out, raw = self.llm.call_json("talk", self.system(w, p), [{"role": "user", "content": content}], max_tokens=300, cache_system=False, mind=p.get("model"))
        return out or {"say": "...", "end": True, "deal": None}


# ------------------------------------------------------------------ mock mind (DRY RUN ONLY, never content)
class MockMind:
    def __init__(self, seed=0): self.r = random.Random(seed)
    def plan(self, w, p, memories, extra="", new=()):
        r = self.r; t = p["traits"]; places = list(w.places)
        others = [q for q in w.adults() if q["id"] != p["id"]]
        slots = []
        for s in ("morning", "midday", "evening", "night"):
            if s == "night": slots.append({"slot": s, "place": w.households[p["household"]]["place"], "do": "sleep", "target": None, "amount": None, "detail": "[MOCK]"}); continue
            roll = r.random()
            if p.get("employer") and s in ("morning", "midday") and roll < 0.8: a = {"do": "work", "place": "company"}
            elif roll < 0.25 and others: a = {"do": "talk", "place": "diner", "target": r.choice(others)["name"], "detail": "[MOCK] chat"}
            elif roll < 0.33: a = {"do": "eat_at_diner", "place": "diner"}
            elif roll < 0.4: a = {"do": "dig", "place": r.choice([k for k in places if k.startswith("lm_")])}
            elif roll < 0.43 and others: a = {"do": "phone", "place": w.households[p["household"]]["place"], "target": r.choice(others)["name"], "detail": "[MOCK] call"}
            elif roll < 0.45: a = {"do": "attempt", "place": "town_hall", "detail": "[MOCK] tries to get a streetlight put in"}
            else: a = {"do": "home", "place": w.households[p["household"]]["place"]}
            a.update({"slot": s, "amount": None}); a.setdefault("target", None); a.setdefault("detail", "[MOCK]"); slots.append(a)
        h = w.households[p["household"]]; roll2 = r.random(); home = h["place"]
        if p["age"] >= 21:
            if roll2 < 0.004: slots[1] = {"slot": "midday", "place": "store", "do": "buy", "target": None, "amount": None, "detail": r.choice(["a television set", "a used car on time", "a washing machine on time", "a radio", "a new car on time", "the house we rent"])}
            elif roll2 < 0.006: slots[1] = {"slot": "midday", "place": home, "do": "bank_loan", "target": None, "amount": r.choice([100, 300, 1500]), "detail": r.choice(["to fix the roof", "to start a business", "to pay doctor bills"])}
            elif roll2 < 0.016: slots[1] = {"slot": "midday", "place": home, "do": "deposit", "target": None, "amount": None, "detail": "[MOCK]"}
            elif roll2 < 0.018: slots[1] = {"slot": "midday", "place": home, "do": "shop_at", "target": None, "amount": None, "detail": r.choice(["the county seat", "the general store"])}
            elif roll2 < 0.021: slots[1] = {"slot": "midday", "place": "town_hall", "do": "propose_measure", "target": None, "amount": None, "detail": r.choice(["Raise the town tax to $8 a quarter", "Ban fishing off the public dock, fine $5", "Spend $50 to fix the town hall roof"])}
        k = econ.shop_of(w, p)
        if k and roll2 > 0.97: slots[1] = {"slot": "midday", "place": k, "do": "set_price", "target": None, "amount": r.choice([-5, 5, 10, 15]) if k == "store" else r.choice([55, 65, 75]), "detail": "[MOCK]"}
        co = next((c for c in w.companies.values() if c["owner"] == p["id"]), None)
        if co and co["employees"] and roll2 > 0.985: slots[1] = {"slot": "midday", "place": "company", "do": "set_wage", "target": None, "amount": r.choice([55, 62, 70]), "detail": "[MOCK]"}
        if any(x in (p.get("job") or "") for x in ("marshal", "sheriff")) and roll2 < 0.05 and others:
            slots[2] = {"slot": "evening", "place": "town_hall", "do": "enforce", "target": r.choice(others)["name"], "amount": None, "detail": "[MOCK]"}
        off = w.town["offices"]
        if (p["id"] in off["council"] or p["id"] == off["mayor"]) and w.date.weekday() == w.town["charter"].get("meeting_weekday", 1):
            for m in w.town["motions"]:
                if m["status"] == "open": slots[2] = {"slot": "evening", "place": "town_hall", "do": "vote", "target": m["id"], "amount": None, "detail": "yes" if r.random() < 0.6 else "no"}
        evs = [k for k, v in w.places.items() if v.get("kind") == "event"]
        if evs and r.random() < 0.3: slots[2] = {"slot": "evening", "place": r.choice(evs), "do": "home", "target": None, "amount": None, "detail": "[MOCK] goes to the event"}
        for e in w.town["elections"]:
            if e["status"] == "open" and p["age"] >= 21:
                if r.random() < 0.15 + t["extraversion"] / 400: slots[0] = {"slot": "morning", "place": "town_hall", "do": "declare_candidacy", "target": None, "amount": None, "detail": "mayor"}
                slots[2] = {"slot": "evening", "place": "town_hall", "do": "vote", "target": "__any_candidate__", "amount": None, "detail": "[MOCK]"}
        return {"slots": slots, "reflections": ["[MOCK] reflection"], "feelings": {}}

    def reflect(self, w, p, week): return [f"[MOCK] {p['name'].split()[0]} looks back on {len(week)} memories from the week."]

    def say(self, w, p, other, transcript, memories, purpose, mind_seed=None, chance=False, last=None):
        n = len(transcript)
        return {"say": f"[MOCK line {n + 1}] {p['name'].split()[0]} talks to {other['name'].split()[0]}.", "aside": f"[MOCK] {p['name'].split()[0]} privately thinks something.", "end": n >= self.r.randint(2, 5),
                "deal": ({"type": "lend", "amount": 20, "terms": "[MOCK]"} if n == 2 and self.r.random() < 0.1 else None)}


def assign_outside_minds(w, seed, per_model=3, models=None):
    """Dice give a few adult residents (18+) a mind from another lab, for life. A separate dice stream, so the town itself
    rolls exactly as before. Children stay on Claude (channel standards). Returns {pid: model}. Nobody in town knows."""
    import random
    from .llm import OUTSIDE
    models = list((models or OUTSIDE).values())
    pool = sorted((pid for pid, p in w.people.items() if p["alive"] and p["age"] >= 18), key=str)
    r = random.Random(f"{seed}-outside-minds"); picked = r.sample(pool, min(len(pool), per_model * len(models)))
    out = {}
    for i, pid in enumerate(picked):
        w.people[pid]["model"] = models[i % len(models)]; out[pid] = w.people[pid]["model"]
    return out


# The official roll (agreed with Aaron Nov 20): about 15-20% of adults get an outside mind, weighted toward DeepSeek.
OUTSIDE_SHARE = 0.175
OUTSIDE_WEIGHTS = {"deepseek": 0.5, "gpt": 0.25, "gemini": 0.25}


def assign_outside_share(w, seed, share=OUTSIDE_SHARE, weights=OUTSIDE_WEIGHTS):
    """Same dice stream as assign_outside_minds, but sized by share of adults and split by weight.
    Largest-remainder split so the counts always add up. Returns {pid: model}."""
    import random
    from .llm import OUTSIDE
    pool = sorted((pid for pid, p in w.people.items() if p["alive"] and p["age"] >= 18), key=str)
    total = max(1, round(share * len(pool)))
    raw = {k: total * v for k, v in weights.items()}
    n = {k: int(x) for k, x in raw.items()}
    for k in sorted(raw, key=lambda k: raw[k] - n[k], reverse=True)[: total - sum(n.values())]: n[k] += 1
    r = random.Random(f"{seed}-outside-minds"); picked = r.sample(pool, min(len(pool), total))
    order = [OUTSIDE[k] for k in weights for _ in range(n[k])]
    out = {}
    for pid, m in zip(picked, order):
        w.people[pid]["model"] = m; out[pid] = m
    return out
