"""World state + automated systems (physics). No storytelling here: only locked rules and dice."""
import datetime as dt, json, math, random
from . import history, econ

SLOTS = ["morning", "midday", "evening", "night"]
SEASON_OF_MONTH = {12: "winter", 1: "winter", 2: "winter", 3: "spring", 4: "spring", 5: "spring", 6: "summer", 7: "summer", 8: "summer", 9: "autumn", 10: "autumn", 11: "autumn"}
SEASON_START = {"spring": (3, 20), "summer": (6, 21), "autumn": (9, 22), "winter": (12, 21)}

# climate normals by geography: base temp (F) per season, base wet-day odds, disaster daily odds per season (scaled by anomalies)
CLIMATE = {
    "plains":    {"temp": {"winter": 35, "spring": 60, "summer": 85, "autumn": 62}, "wet": 0.25,
                  "disasters": {"tornado": {"spring": 0.004, "summer": 0.0015}, "hail": {"spring": 0.008, "summer": 0.005}, "blizzard": {"winter": 0.006}, "ice storm": {"winter": 0.004}, "heat wave": {"summer": 0.01}, "dust storm": {"spring": 0.003}}},
    "coast":     {"temp": {"winter": 45, "spring": 60, "summer": 78, "autumn": 64}, "wet": 0.35,
                  "disasters": {"hurricane": {"summer": 0.0015, "autumn": 0.002}, "nor'easter": {"winter": 0.006, "autumn": 0.003}, "flood": {"spring": 0.003}, "fog bank": {"spring": 0.01, "summer": 0.008}}},
    "island":    {"temp": {"winter": 40, "spring": 55, "summer": 74, "autumn": 60}, "wet": 0.38,
                  "disasters": {"hurricane": {"summer": 0.0015, "autumn": 0.002}, "gale": {"winter": 0.008, "autumn": 0.006}, "ice-in (ferry stops)": {"winter": 0.004}, "fog bank": {"spring": 0.012, "summer": 0.01}}},
    "mountains": {"temp": {"winter": 25, "spring": 48, "summer": 72, "autumn": 50}, "wet": 0.32,
                  "disasters": {"blizzard": {"winter": 0.009}, "rockslide": {"spring": 0.003}, "flash flood": {"spring": 0.003, "summer": 0.002}, "forest fire": {"summer": 0.003, "autumn": 0.002}, "avalanche": {"winter": 0.003}}},
    "desert":    {"temp": {"winter": 45, "spring": 70, "summer": 98, "autumn": 72}, "wet": 0.08,
                  "disasters": {"flash flood": {"summer": 0.004}, "dust storm": {"spring": 0.008}, "heat wave": {"summer": 0.02}, "brush fire": {"summer": 0.004}}},
    "lakeside":  {"temp": {"winter": 22, "spring": 50, "summer": 76, "autumn": 54}, "wet": 0.33,
                  "disasters": {"blizzard": {"winter": 0.007}, "lake squall": {"summer": 0.004, "autumn": 0.005}, "ice storm": {"winter": 0.004}, "flood": {"spring": 0.003}}},
    "swamp":     {"temp": {"winter": 55, "spring": 72, "summer": 90, "autumn": 74}, "wet": 0.40,
                  "disasters": {"hurricane": {"summer": 0.002, "autumn": 0.002}, "flood": {"spring": 0.004, "summer": 0.003}, "heat wave": {"summer": 0.01}, "fever outbreak": {"summer": 0.002}}},
    "forest":    {"temp": {"winter": 28, "spring": 50, "summer": 74, "autumn": 52}, "wet": 0.36,
                  "disasters": {"forest fire": {"summer": 0.004, "autumn": 0.002}, "blizzard": {"winter": 0.007}, "windstorm": {"autumn": 0.004, "winter": 0.003}, "flood": {"spring": 0.003}}},
}
DANGEROUS = ("mine", "lumber", "timber", "quarry", "fish", "shrimp", "oyster", "boat", "oil", "ferry", "paper", "turpentine", "feedlot", "sugar")
DISCOVERY_TABLE = {  # (weight, unlabeled description, true identity, value)
    "_common": [(30, "a chipped, pointed stone", "Native American arrowhead", 2), (20, "a few old coins, green with age", "1880s silver coins", 15),
                (18, "an old glass bottle with something rattling inside", "patent-medicine bottle with a brass key", 1), (12, "a worn leather wallet", "lost wallet with $14", 14)],
    "plains": [(4, "a dark, oily slick seeping up from the ground", "oil seep", 50000), (2, "a very large, heavy, odd-shaped bone", "dinosaur fossil (Triceratops horn core)", 4000)],
    "coast": [(4, "a barnacled wooden chest, half buried in sand", "shipwreck chest with Spanish coins", 3000), (2, "a strange heavy bone wedged in the bluff", "whale fossil", 1500)],
    "island": [(4, "a barnacled wooden chest, half buried", "shipwreck chest", 2500), (3, "a bed of oysters with something gleaming in one", "natural pearl", 800)],
    "mountains": [(4, "a vein of bright, heavy rock in the stream bank", "silver ore", 9000), (3, "a small, very heavy yellow pebble", "gold nugget", 600), (2, "a very large, heavy, odd-shaped bone", "dinosaur fossil (Allosaurus)", 5000)],
    "desert": [(3, "a small, very heavy yellow pebble", "gold nugget", 600), (3, "a very large, heavy, odd-shaped bone", "dinosaur fossil (T. rex)", 8000), (2, "a black, pitted rock that is strangely heavy", "iron meteorite", 1200)],
    "lakeside": [(3, "a rusted strongbox in the shallows", "bootlegger's strongbox with cash", 2200), (2, "a very large, heavy, odd-shaped bone", "mastodon tusk", 2500)],
    "swamp": [(4, "a rusted strongbox caught in cypress roots", "bootlegger's strongbox", 1800), (2, "a carved stone figure", "pre-Columbian artifact", 3000)],
    "forest": [(3, "a very large, heavy, odd-shaped bone", "mammoth bone", 2000), (3, "a rotted cabin with a tin can buried under the floor", "old prospector's savings", 900)],
    "_rare": [(1, "a black, pitted rock, still warm, at the bottom of a small fresh crater", "meteorite (fresh fall)", 2500)],
    "_unexplained": [(1, "lights in the sky that moved in ways no airplane does", "UNEXPLAINED", 0), (1, "a perfect circle of scorched grass", "UNEXPLAINED", 0),
                     (1, "a piece of thin, very light metal that won't bend or burn", "UNEXPLAINED", 0)],
}


# ---- What work pays (decided with Aaron, Nov 18): anyone who works gets paid, at real 1950 rates, rising every year with
# history.wage_index. Volunteers, homemakers, the retired and the out of work earn nothing. Nobody's earnings are capped.
# 1950 dollars a year. Anchors: average full-time employee $2,930 and public school teacher $3,010 (NCES, 1949-50);
# physicians about $11,000. The rest are estimates around those anchors for small-town work.
#   kind "salary": paid every Friday, sick or well. kind "trade": earned day by day (Mon-Sat), only when able to work,
#   swinging with the season, the weather and luck.  payer: who the money comes from ("outside" = county, state, federal
#   or customers out of town; "diner"/"store" = that business's household pays its own help).
JOB_PAY = {
    "schoolteacher": (3010, "salary", "outside"), "postmaster": (3200, "salary", "outside"), "town marshal": (2400, "salary", "outside"),
    "deputy sheriff": (2800, "salary", "outside"), "nurse": (2500, "salary", "outside"), "telephone operator": (2100, "salary", "outside"),
    "bookkeeper": (2600, "salary", "outside"), "newspaper editor": (3400, "salary", "outside"), "preacher's assistant": (1400, "salary", "outside"),
    "store clerk": (1900, "salary", "outside"), "diner cook": (1900, "salary", "outside"),  # a clerk or cook may work here or at a counter in the county seat
    "runs the diner": (2400, "trade", "outside"),  # a diner lives on lunch, coffee and passing trade, not just townsfolk; residents' own meals add to it
    "town doctor": (11000, "trade", "outside"), "farmer": (2400, "trade", "outside"), "fisherman": (2400, "trade", "outside"),
    "trucker": (3200, "trade", "outside"), "mechanic": (3000, "trade", "outside"), "carpenter": (3000, "trade", "outside"),
    "barber": (2400, "trade", "outside"), "seamstress": (1700, "trade", "outside"), "handyman": (2000, "trade", "outside"),
    "salesman": (3400, "trade", "outside"),
}
UNPAID = ("homemaker", "retired", "out of work", "looking for work", "volunteer", "unpaid", "student", "in school")
DEFAULT_PAY = (2300, "trade", "outside")  # a job title the town made up later (e.g. "takes in laundry"): about the 1952 median income
# seasonal swing for outdoor trades (each averages about 1 over the year)
SEASON_PAY = {"farmer": {"winter": 0.35, "spring": 1.0, "summer": 1.15, "autumn": 1.5}, "fisherman": {"winter": 0.5, "spring": 1.1, "summer": 1.35, "autumn": 1.05},
              "carpenter": {"winter": 0.6, "spring": 1.1, "summer": 1.25, "autumn": 1.05}}


SAVE_QUIRK = {"penny-pincher": 0.10, "hoarder": 0.06, "worrier": 0.03, "gambler": -0.10, "show-off": -0.06, "heavy drinker": -0.07, "dreamer": -0.02, "lazy": -0.02}


def job_pay(job):
    """(dollars a year in 1950, kind, payer) for a job title, or None if the job doesn't pay."""
    j = (job or "").lower().strip()
    if not j or j == "-" or any(u in j for u in UNPAID) or j.startswith(("owner", "runs the general store", "works at")): return None  # store owner earns the margin; company owners draw profits
    for k, v in JOB_PAY.items():
        if k in j: return v
    return DEFAULT_PAY

ING = {"dig": "digging", "explore": "exploring", "build": "building", "farm": "farming", "fish": "fishing"}


class World:
    def __init__(self, gen, seed_offset=0):
        self.gen = gen; self.rng = random.Random(gen["seed"] * 7919 + seed_offset)
        y = gen["start"]["year"]; m, d = SEASON_START[gen["start"]["season"]]
        self.date = dt.date.fromisoformat(gen["start"]["date"]) if gen["start"].get("date") else dt.date(y, m, d); self.day = 0; self.slot = 0
        self.geo = gen["geography"]; self.clim = CLIMATE[self.geo]
        self.people, self.households, self.places, self.companies = {}, {}, {}, {}
        self.town = {"name": gen["name"], "treasury": gen.get("treasury", 300), "charter": default_charter(), "offices": {"mayor": None, "council": []},
                     "laws": [], "motions": [], "elections": [], "tax_per_household_quarter": 6}
        self.weather = {"season": None, "temp_anom": 0.0, "moist_anom": 0.0, "dry_streak": 0, "today": {}}
        self.flags = {"draft": "off", "highway_program": False, "polio_vaccine": False, "bomb_shelter_fever": False, "market": 1.0}
        self.offtown = {}  # pid -> off-screen life record
        self.threads = []  # open and ended matters (see fate.py)
        self.next_pid = 1
        self._build()
        econ.setup(self)  # possessions, the mortgages and debts families already had, the shops (separate dice)

    # ------------------------------------------------------------------ setup
    def _build(self):
        g = self.gen; xs = 0
        for h in g["households"]:
            hid = h["id"]; home = f"home_{hid}"
            self.places[home] = {"name": f"the {h['surname']} house", "kind": "home", "household": hid, "x": 40 + xs * 140, "condition": 1.0}
            xs += 1
            self.households[hid] = {"id": hid, "surname": h["surname"], "kind": h["kind"], "members": [], "savings": h["savings"], "debt": h["debt"],
                                    "home": h["home"], "place": home, "monthly_housing": {"owned outright": 0, "mortgaged": 48, "rented": 38}[h["home"]],
                                    "withhold_tax": False, "has_tv": False}
            for p in h["members"]: self.add_person(p, hid)
        # family ties inside households
        for h in self.households.values():
            ms = [self.people[i] for i in h["members"]]
            for a in ms:
                for b in ms:
                    if a is b: continue
                    a["rel"][b["id"]] = {"affinity": 40 if {a["role"], b["role"]} != {"husband", "wife"} else 55, "trust": 50, "tags": ["family"]}
                    if {a["role"], b["role"]} == {"husband", "wife"}: a["spouse"] = b["id"]; a["rel"][b["id"]]["tags"].append("spouse")
                    if a["role"] in ("husband", "wife", "parent") and b["role"] == "child": b.setdefault("parents", []).append(a["id"]); a.setdefault("children", []).append(b["id"])
        for k, nm in (("diner", "the diner"), ("store", "the general store"), ("town_hall", "the town hall"), ("school", "the schoolhouse"), ("church", "the church"), ("company", g["company"]["name"])):
            self.places[k] = {"name": nm, "kind": k, "x": 0}
        for lm in g["landmarks"]: self.places["lm_" + lm.replace(" ", "_")] = {"name": "the " + lm, "kind": "outdoors", "x": 0}
        self.places["lm_woods"] = {"name": "the open country outside town", "kind": "outdoors", "x": 0}
        self.places["diner"]["household"] = g["diner_owner_household"]; self.places["store"]["household"] = g["store_owner_household"]
        c = g["company"]; owner_h = self.households[c["owner_household"]]
        owner = next((self.people[i] for i in owner_h["members"] if self.people[i]["job"] and self.people[i]["job"].startswith("owner")), self.people[owner_h["members"][0]])
        self.companies["co1"] = {"id": "co1", "name": c["name"], "industry": c["industry"], "owner": owner["id"], "cash": c["cash"],
                                 "employees": [], "wage_day": 11.0, "place": "company", "status": "open", "productivity": 16.0}  # wages = about 62% of what work produces (1950 manufacturing labor share)
        for p in self.people.values():
            if p["job"] and p["job"].startswith("works at"): p["employer"] = "co1"; self.companies["co1"]["employees"].append(p["id"])
        # the sitting government (rolled by the generator); next election falls on its normal two-year schedule
        gv = g.get("government") or {}
        pid_of = lambda x: self.households[x[0]]["members"][x[1]]
        self.town["offices"] = {"mayor": pid_of(gv["mayor"]) if gv.get("mayor") else None, "council": [pid_of(x) for x in gv.get("council", [])]}
        self.town["elected_days_ago"] = gv.get("elected_days_ago", 0)
        self.town["next_election_day"] = self.town["charter"]["term_days"] - gv["elected_days_ago"] if gv else 0
        # cross-household history links -> relationship seeds + memories
        for l in g["history_links"]:
            a_h, b_h = self.households[l["between"][0]], self.households[l["between"][1]]
            heads = lambda h: [i for i in h["members"] if self.people[i]["age"] >= 18][:2] or h["members"][:1]
            delta = {"grudge": -35, "debt": -10, "old romance": 10, "friendship": 30, "business partnership gone quiet": -5, "rivalry": -15, "church friends": 20, "neighbors who help each other": 18}[l["kind"]]
            for a in heads(a_h):
                for b in heads(b_h):
                    for x, y in ((a, b), (b, a)):
                        r = self.people[x]["rel"].setdefault(y, {"affinity": 0, "trust": 30, "tags": []}); r["affinity"] += delta; r["tags"].append(l["kind"])
            if l["kind"] == "debt":
                a_h["owes"] = a_h.get("owes", []) + [{"to": b_h["id"], "amount": l["amount"]}]
            l["_text"] = describe_link(l, a_h, b_h)

    def add_person(self, p, hid):
        pid = self.next_pid; self.next_pid += 1
        q = dict(p); q.update({"id": pid, "household": hid, "alive": True, "location": f"home_{hid}", "rel": {}, "flags": {}, "employer": None,
                               "needs": {"hunger": 20, "energy": 80, "social": 50, "mood": 55}, "illness": None, "injury": 0,
                               "pregnant": None, "born_day": -int(p["age"] * 365.25), "offtown": False, "cash_note": ""})
        self.people[pid] = q; self.households[hid]["members"].append(pid)
        return pid

    # ------------------------------------------------------------------ helpers
    @property
    def date_str(self): return self.date.isoformat()
    @property
    def season(self): return SEASON_OF_MONTH[self.date.month]
    def living(self, intown=True): return [p for p in self.people.values() if p["alive"] and (not intown or not p["offtown"])]
    def adults(self): return [p for p in self.living() if p["age"] >= 18]
    def name(self, pid): return self.people[pid]["name"]
    def first_names(self): return {p["name"].split()[0] for p in self.people.values()}  # living, dead and away: never reused
    def by_name(self, nm):
        """Full name first (living people before the dead); a first name alone only counts if exactly one person has it."""
        nm = (nm or "").strip().lower()
        full = sorted((p for p in self.people.values() if p["name"].lower() == nm), key=lambda p: not p["alive"])
        if full: return full[0]
        first = [p for p in self.people.values() if p["alive"] and p["name"].split()[0].lower() == nm]
        return first[0] if len(first) == 1 else None

    # ------------------------------------------------------------------ weather (rolled; persistence = memory)
    def roll_season(self, ev):
        s = self.season; prev_t, prev_m = self.weather["temp_anom"], self.weather["moist_anom"]
        self.weather["temp_anom"] = 0.45 * prev_t + self.rng.gauss(0, 0.9)
        self.weather["moist_anom"] = 0.55 * prev_m + self.rng.gauss(0, 0.9)
        self.weather["season"] = s
        ta, ma = self.weather["temp_anom"], self.weather["moist_anom"]
        label = (("a bitter " if ta < -1.2 else "a cold " if ta < -0.5 else "a scorching " if ta > 1.2 and s == "summer" else "a hot " if ta > 0.6 else "a mild " if ta > 0.3 and s == "winter" else "an ordinary ")
                 + s + (", bone-dry" if ma < -1.2 else ", dry" if ma < -0.5 else ", very wet" if ma > 1.2 else ", wet" if ma > 0.5 else ""))
        self.weather["season_label"] = label
        if ma < -0.6: self.weather["dry_streak"] += 1
        else: self.weather["dry_streak"] = 0
        ev("weather_season", text=f"The season turns: {label}.", importance=3, public=False)  # a record for us; residents feel the daily weather

    def roll_day_weather(self, ev):
        s = self.season; base = self.clim["temp"][s]; ta, ma = self.weather["temp_anom"], self.weather["moist_anom"]
        temp = int(base + ta * 8 + self.rng.gauss(0, 7))
        wet = self.rng.random() < max(0.02, self.clim["wet"] * (1 + 0.45 * ma))
        sky = ("snow" if wet and temp < 33 else "rain" if wet else "clear" if self.rng.random() < 0.6 else "cloudy")
        today = {"temp": temp, "sky": sky, "disaster": None}
        drought = self.weather["dry_streak"] >= 2
        for kind, by_season in self.clim["disasters"].items():
            p = by_season.get(s, 0)
            if not p: continue
            if kind in ("flood", "flash flood"): p *= max(0.2, 1 + ma)
            if kind in ("heat wave",): p *= max(0.2, 1 + ta)
            if kind in ("forest fire", "brush fire", "dust storm"): p *= (2.5 if drought else max(0.2, 1 - ma))
            if kind in ("blizzard", "ice storm", "avalanche"): p *= max(0.2, 1 - ta * 0.5)
            if self.rng.random() < p: today["disaster"] = kind; break
        self.weather["today"] = today
        if today["disaster"]: self.disaster(today["disaster"], ev)
        return today

    def disaster(self, kind, ev):
        severity = self.rng.choice(["minor", "minor", "serious", "severe"])
        if kind in ("fog bank", "ice-in (ferry stops)"):
            ev("weather_event", text=f"A {kind} settles over {self.town['name']}; boats and deliveries are stuck.", importance=3, public=True, data={"kind": kind}); return
        if kind in ("heat wave", "fever outbreak"):
            sick = []
            for p in self.living():
                risk = (0.04 if p["age"] > 65 or p["age"] < 3 else 0.006) * (2 if kind == "fever outbreak" else 1)
                if not p["illness"] and self.rng.random() < risk:
                    p["illness"] = {"name": "heatstroke" if kind == "heat wave" else "a fever", "serious": p["age"] > 65, "days": self.rng.randint(3, 10)}; sick.append(p["name"])
            ev("disaster", text=f"A {kind} grips {self.town['name']}." + (f" Laid low: {', '.join(sick)}." if sick else ""), importance=6 if sick else 4, public=True, data={"kind": kind, "severity": severity}); return
        hit = [h for h in self.households.values() if self.places.get(h["place"], {}).get("kind") == "home" and self.rng.random() < {"minor": 0.2, "serious": 0.45, "severe": 0.7}[severity]]
        dmg_txt = []
        for h in hit:
            cost = int({"minor": 40, "serious": 180, "severe": 650}[severity] * self.rng.uniform(0.5, 1.6) * history.price_index(self.date.year))
            self.places[h["place"]]["condition"] = max(0.1, self.places[h["place"]]["condition"] - cost / 1500)
            h.setdefault("repairs_needed", 0); h["repairs_needed"] += cost; dmg_txt.append(f"{h['surname']} house (${cost})")
        if severity != "minor" and self.companies:
            # a business loses in proportion to its size: lost days of work plus the repair bill its insurance doesn't cover
            # (half a week to a week and a half of output for a serious hit, 2-5 weeks for a severe one; most repairs were insured).
            # A closed business has nothing left to lose.
            c = self.companies["co1"]
            if c["status"] == "open":
                week = max(1, len(c["employees"])) * c["productivity"] * 6 * history.wage_index(self.date.year)
                loss = int(week * self.rng.uniform(*{"serious": (0.5, 1.5), "severe": (2, 5)}[severity])); c["cash"] -= loss; dmg_txt.append(f"{c['name']} (${loss})")
        hurt = []
        for p in self.living():
            if self.rng.random() < {"minor": 0.0, "serious": 0.02, "severe": 0.06}[severity]:
                if self.rng.random() < 0.12 and severity == "severe": self.kill(p, f"killed in the {kind}", ev); hurt.append(p["name"] + " (killed)")
                else: p["injury"] = self.rng.randint(5, 30); hurt.append(p["name"])
        said = f"The {kind} hit {'hard' if severity != 'minor' else 'but not too bad'}" + (f"; it damaged the {', the '.join(h['surname'] + ' place' for h in hit[:4])}" if hit else "") + (f"; {', '.join(hurt)} got hurt" if hurt else "") + "."
        ev("disaster", text=f"A {severity} {kind} hits {self.town['name']}." + (f" Damage: {', '.join(dmg_txt)}." if dmg_txt else "") + (f" Hurt: {', '.join(hurt)}." if hurt else ""),
           importance={"minor": 5, "serious": 8, "severe": 10}[severity], public=True, data={"kind": kind, "severity": severity, "said": said})

    # ------------------------------------------------------------------ economy (daily)
    def earned(self, h, amt): h["earned_m"] = h.get("earned_m", 0) + amt

    def living_costs(self, h, n, P, housing, store_h):
        """Everything else a household buys in a month: clothes, fuel, lights, the doctor, the car, furniture, a night out.
        Families spend what comes in and save a share: in the 1950s about 9% (BEA personal saving rate, 1950: 9.3%).
        How much a family saves comes from its own people (penny-pinchers save, gamblers and show-offs don't), so some get
        ahead and some fall behind. Even a family with nothing coming in still needs fuel, clothes and lights."""
        income = h.pop("earned_m", 0); outgo = h.pop("spent_m", 0) + housing
        adults = [self.people[i] for i in h["members"] if self.people[i]["alive"] and self.people[i]["age"] >= 18]
        # the 16% that families spent on cars, appliances and furniture is no longer spent for them: it stays in the household
        # until they decide to buy something (econ.DURABLES_SHARE; decided with Aaron, Nov 18)
        save = 0.09 + econ.DURABLES_SHARE + sum(SAVE_QUIRK.get(q, 0) for a in adults for q in a["quirks"])
        save = max(-0.15, min(0.55, save))
        floor = 0.25 * n * 30 * P  # bare necessities
        other = round(max(floor, income * (1 - save) - outgo), 2)
        h["savings"] -= other
        st = self.shops["store"]
        if h.get("groceries_at", "store") == "store" and store_h in self.households and store_h != h["id"] and econ.shop_runners(self, "store"):  # a share of it is bought at the general store
            m = other * 0.1 * (1 - econ.WHOLESALE / st["level"]); self.households[store_h]["savings"] += m; self.earned(self.households[store_h], m); st["week"] += m

    def unemployment_claim(self, c, laid, firm_size=None):
        """Laid-off or fired hands of a covered firm can draw unemployment pay (not if they quit; firms too small aren't covered)."""
        if (firm_size or len(laid)) < history.ui_min_firm(self.date.year): return
        W = history.wage_index(self.date.year)
        for i in laid:
            q = self.people[i]
            if q["alive"]: q["ui"] = {"weeks": history.UI_WEEKS, "amount": round(min(0.5 * c["wage_day"] * W * 5.5, history.UI_MAX_1950 * W), 2)}

    def social_security(self, h):
        """The monthly Social Security check(s) for this household, on the first of the month. Who draws it was decided by the
        dice in proportion to the real share of older people covered that year; a beneficiary who still works for pay gets no check."""
        y, mo = self.date.year, self.date.month; yy = max(1950, min(1959, y)); total = 0
        prev = history.SS_AGED_SHARE.get(yy - 1); share = history.SS_AGED_SHARE[yy]
        members = [self.people[i] for i in h["members"] if self.people[i]["alive"]]
        for q in members:
            old_age = 65 if q["sex"] == "male" or self.date_str < history.SS_WOMEN_62_FROM else 62
            if q["age"] >= old_age and not q.get("ss"):
                if q.get("ss_rolled") != y:  # once a year: newly covered old people come on the rolls as the real share grows
                    q["ss_rolled"] = y
                    first = not q.get("ss_seen"); q["ss_seen"] = True
                    p_on = share if first or prev is None else max(0.0, (share - prev) / max(0.01, 1 - prev))
                    if self.rng.random() < p_on: q["ss"] = True
            if not q.get("ss"): continue
            working = (q.get("employer") or job_pay(q.get("job"))) and q["age"] < history.ss_work_exempt_age(y)
            if working: continue
            kind = "retired_man" if q["sex"] == "male" else ("retired_woman" if q.get("job") not in (None, "homemaker") else "wife")
            if q["sex"] == "female" and q.get("widowed"): kind = "widow"
            total += history.ss_amount(kind, y, mo)
        # survivors of a covered worker: a widow 65+ (62 from late 1956), or a mother with children under 18, and the children
        dead = self.people.get(h.get("survivor_of"))
        if dead:
            kids = [q for q in members if q["age"] < 18 and dead["id"] in (q.get("parents") or [])]
            moms = [q for q in members if q.get("widowed") and q["sex"] == "female" and q.get("spouse") == dead["id"] and not q.get("ss")]
            fam = sum(history.ss_amount("child", y, mo) for _ in kids)
            for q in moms:
                widow_age = 65 if self.date_str < history.SS_WOMEN_62_FROM else 62
                if kids or q["age"] >= widow_age: fam += history.ss_amount("mother" if kids else "widow", y, mo)
            total += min(fam, 2.0 * history.ss_amount("retired_man", y, mo))  # family maximum (about double a worker's check)
            if not kids and not moms: h.pop("survivor_of", None)
        if total > 0:
            h["savings"] += total; self.earned(h, total); h["ss_month"] = round(total, 2)

    def wages_day(self, ev, W):
        """Everyone with a paying job earns (company hands are paid by their company's payroll instead)."""
        weekday = self.date.weekday(); hit = bool(self.weather["today"].get("disaster")); s = self.season
        dh, sh = self.places["diner"].get("household"), self.places["store"].get("household")
        for p in self.living():
            if p.get("ui"):  # unemployment pay, every Friday, until they work again or it runs out
                if p.get("employer") or job_pay(p.get("job")): p.pop("ui")
                elif weekday == 4:
                    hh = self.households[p["household"]]; hh["savings"] += p["ui"]["amount"]; self.earned(hh, p["ui"]["amount"])
                    p["ui"]["weeks"] -= 1
                    if p["ui"]["weeks"] <= 0: p.pop("ui")
            if p["age"] < 14 or p.get("employer"): continue
            jp = job_pay(p.get("job"))
            if not jp: continue
            yearly, kind, payer = jp; j = p["job"].lower()
            if kind == "salary":
                if weekday != 4: continue
                amt = yearly / 52 * W
            else:
                if weekday == 6 or (p["illness"] and p["illness"]["serious"]) or p["injury"] > 0: continue  # no work, no pay
                mult = next((v[s] for k, v in SEASON_PAY.items() if k in j), 1.0) * self.rng.uniform(0.55, 1.45)
                if hit: mult *= 0.0 if any(k in j for k in ("fisherman", "farmer", "carpenter")) else 0.5
                amt = yearly / 310 * W * mult
            amt = round(amt, 2)
            if amt <= 0: continue
            src = dh if payer == "diner" else sh if payer == "store" else None
            if src in self.households and src != p["household"]: self.households[src]["savings"] -= amt
            self.households[p["household"]]["savings"] += amt; self.earned(self.households[p["household"]], amt)

    def economy_day(self, ev):
        mult = self.flags["market"]; wx = self.weather["today"]
        weekday = self.date.weekday()
        P, W = history.price_index(self.date.year), history.wage_index(self.date.year)  # real 1950s prices and wages (base figures are 1950's)
        for c in self.companies.values():
            if c["status"] != "open": continue
            yld = 0.7 if wx.get("disaster") else 1.0
            if self.weather["dry_streak"] >= 2 and any(k in c["industry"] for k in ("grain", "farm", "cattle", "sugar")): yld *= 0.7
            workers = ([c["owner"]] if c["id"] != "co1" and self.people[c["owner"]]["alive"] else []) + [i for i in c["employees"] if self.people[i]["alive"] and not self.people[i]["offtown"] and not self.people[i]["illness"] and self.people[i]["injury"] == 0]
            if weekday < 6:
                c["cash"] += len(workers) * c["productivity"] * W * yld * mult * self.rng.uniform(0.85, 1.15) - (4 + 1.5 * len(c["employees"])) * P
            if weekday == 4:  # Friday payroll
                pay = 0
                for i in c["employees"]:
                    p = self.people[i]
                    if not p["alive"]: continue
                    w = max(p.get("wage_day") or c["wage_day"] * W, econ.min_wage_day(self, c)) * 5.5; self.households[p["household"]]["savings"] += w; self.earned(self.households[p["household"]], w); pay += w
                c["cash"] -= pay
                c["broke_days"] = c.get("broke_days", 0) + 7 if c["cash"] < 0 else 0
                if c["broke_days"] >= 70 and c["status"] == "open":  # ten weeks in the red: it shuts its doors
                    c["status"] = "closed"; laid = list(c["employees"]); self.unemployment_claim(c, laid); c["employees"] = []
                    for i in laid: self.people[i]["employer"] = None; self.people[i]["job"] = "out of work"
                    ev("company_closed", actors=[c["owner"]] + laid, text=f"{c['name']} closes its doors for good.", importance=9, public=True, data={"laid_off": len(laid)})
                if c["cash"] < 0 and not c.get("warned_broke"):
                    c["warned_broke"] = True
                    ev("company_broke", actors=[c["owner"]], text=f"{c['name']} can't cover payroll; the books are in the red (${int(c['cash'])}).", importance=8, public=False)
                elif c["cash"] > 0: c["warned_broke"] = False
                # the owner takes home what the business makes beyond a working reserve (about six months of costs and payroll). No ceiling.
                reserve = 26 * (pay + 6 * (4 + 1.5 * len(c["employees"])) * P)  # about six months of payroll and costs kept back for hard times
                if "bank" in (c.get("industry") or "").lower(): reserve += sum(hh.get("deposits", {}).get(c["id"], 0) for hh in self.households.values())  # a bank's deposits aren't the owner's
                if c["status"] == "open" and c["cash"] > reserve and self.people[c["owner"]]["alive"]:
                    draw = round((c["cash"] - reserve) * 0.5, 2); c["cash"] -= draw
                    oh = self.households[self.people[c["owner"]]["household"]]; oh["savings"] += draw; self.earned(oh, draw)
        self.wages_day(ev, W)
        if weekday == 4: econ.shop_payroll(self, ev)
        # households: food, housing, debt interest; spending flows to the store owner
        store_h = self.places["store"]["household"]
        for h in self.households.values():
            n = sum(1 for i in h["members"] if self.people[i]["alive"] and not self.people[i]["offtown"])
            if n == 0: continue
            food = econ.groceries(self, h, 0.75 * n * P)  # bought where the family chooses, at the price the store sets
            h["savings"] -= food; h["spent_m"] = h.get("spent_m", 0) + food
            if h["savings"] < 0: econ.cover(self, h)  # short of cash: they write a check on their own bank account
            if self.date.day == 1:
                hc = h["monthly_housing"] * (P if h["home"] == "rented" else 1.0); h["savings"] -= hc  # rents follow prices; a mortgage payment is fixed
                self.social_security(h)
                h.setdefault("earn_hist", []).append(round(h.get("earned_m", 0), 2)); h["earn_hist"] = h["earn_hist"][-12:]  # what came in last month (lenders look at this)
                self.living_costs(h, n, P, hc + econ.payments(self, h, ("mortgage",)), store_h)
                econ.cover(self, h)
                if h["monthly_housing"] > 0:  # behind on the rent: the landlord evicts after 3 months (mortgages are loans now: see econ.pay_loans)
                    h["behind"] = h.get("behind", 0) + 1 if h["savings"] < 0 else 0
                    if h["behind"] >= (3 if h["home"] == "rented" else 6): self.lose_home(h, "evicted for unpaid rent" if h["home"] == "rented" else "lost to the bank after missed mortgage payments", ev)
            if h["savings"] < 0 and not h.get("broke_flag"):
                h["broke_flag"] = True
                ev("household_broke", actors=[i for i in h["members"] if self.people[i]["age"] >= 18], text=f"The {h['surname']} household has run out of money.", importance=7, public=False)
            elif h["savings"] > 50: h["broke_flag"] = False
        # quarterly tax to the treasury (households can choose to withhold)
        if self.date.day == 1 and self.date.month in (1, 4, 7, 10):
            got = 0
            for h in self.households.values():
                if h["withhold_tax"]: continue
                h["savings"] -= self.town["tax_per_household_quarter"]; got += self.town["tax_per_household_quarter"]
            self.town["treasury"] += got
            ev("taxes", text=f"Quarterly taxes collected: ${got} into the town treasury.", importance=2, public=False)
        # (TV sets, cars and appliances are bought when a family decides to: econ.buy. The old TV dice were removed Nov 18.)

    # ------------------------------------------------------------------ health, life and death (daily)
    def life_day(self, ev):
        s = self.season
        for p in list(self.living(intown=False)):
            age = p["age"]
            # aging
            if (self.day - p["born_day"]) % 365 == 0 and self.day > 0:
                p["age"] += 1
            if p["offtown"]: continue
            # recovery
            if p["injury"] > 0: p["injury"] -= 1
            if p["illness"]:
                p["illness"]["days"] -= 1
                if p["illness"]["days"] <= 0:
                    ev("recovered", actors=[p["id"]], text=f"{p['name']} has gotten over {p['illness']['name']}.", importance=2); p["illness"] = None
                elif p["illness"]["serious"] and self.rng.random() < 0.004 * (1 + max(0, age - 60) / 10):
                    self.kill(p, f"died of {p['illness']['name']}", ev); continue
            # catching something (household contagion, flu season)
            sick_home = any(self.people[i]["illness"] for i in self.households[p["household"]]["members"] if i != p["id"])
            base = {"winter": 0.0035, "autumn": 0.0015, "spring": 0.0012, "summer": 0.0008}[s] * (4 if sick_home else 1)
            if not p["illness"] and self.rng.random() < base:
                ill = self.rng.choices([("a cold", False, 5), ("the flu", False, 8), ("pneumonia", True, 18), ("a fever", False, 4), ("a bad stomach bug", False, 3)], [40, 33, 2, 14, 11])[0]
                if not self.flags["polio_vaccine"] and age < 15 and s == "summer" and self.rng.random() < 0.01: ill = ("polio", True, 40)
                p["illness"] = {"name": ill[0], "serious": ill[1] or (age > 70 and ill[0] == "the flu"), "days": ill[2] + self.rng.randint(0, 5)}
                ev("illness", actors=[p["id"]], text=f"{p['name']} comes down with {ill[0]}.", importance=5 if p["illness"]["serious"] else 2)
            # work accidents
            if p.get("employer") and any(k in self.companies[p["employer"]]["industry"] for k in DANGEROUS) and self.slot == 1:
                if self.rng.random() < 0.0004:
                    if self.rng.random() < 0.08: self.kill(p, f"killed in an accident at {self.companies[p['employer']]['name']}", ev); continue
                    p["injury"] = self.rng.randint(7, 45); ev("accident", actors=[p["id"]], text=f"{p['name']} is hurt in an accident at work.", importance=7, public=True)
            # background mortality (Gompertz)
            q_year = 0.0009 * math.exp(0.083 * max(0, age - 20)) + (0.03 if age < 1 else 0.001 if age < 15 else 0)  # ~1950 US life table
            q_year *= {"weak heart": 2.5, "frail": 2.0, "bad back": 1.0, "poor eyesight": 1.0, "asthma": 1.3}.get(p["health"], 1.0)
            if self.rng.random() < q_year / 365: self.kill(p, self.rng.choice(["died in their sleep", "died suddenly of a heart attack", "died after a stroke"]) if age > 45 else "died suddenly", ev); continue
            # pregnancy
            if p["pregnant"]:
                pr = p["pregnant"]; days = self.day - pr["start"]
                if days < 84 and not pr.get("checked_mc") and days > 40:
                    pr["checked_mc"] = True
                    if self.rng.random() < 0.15:
                        p["pregnant"] = None; ev("miscarriage", actors=[p["id"]] + ([p["spouse"]] if p.get("spouse") else []), text=f"{p['name']} lost the baby.", importance=6, public=False, sensitive=True); continue
                if days == 60: ev("pregnancy_known", actors=[p["id"]] + ([p["spouse"]] if p.get("spouse") else []), text=f"{p['name']} is expecting a baby.", importance=6, public=False)
                if days >= 270: self.birth(p, ev)
            elif p["sex"] == "female" and 18 <= age <= 42 and p.get("spouse") and self.people[p["spouse"]]["alive"] and not self.people[p["spouse"]]["offtown"]:
                kids = len(p.get("children", []))
                monthly = 0.07 * (0.5 if kids >= 4 else 1) * (0.5 if age > 37 else 1) * (p["flags"].get("fertility_mod", 1.0))
                if self.rng.random() < monthly / 30: p["pregnant"] = {"start": self.day}

    def birth(self, mother, ev):
        mother["pregnant"] = None; father = self.people.get(mother.get("spouse")) if mother.get("spouse") else None
        sex_m = self.rng.random() < 0.51; yr = self.date.year
        from .names import baby_name
        first = baby_name(self.rng, yr, sex_m, self.first_names())
        surname = self.households[mother["household"]]["surname"]
        par = [mother] + ([father] if father else [])
        traits = {}
        for k in mother["traits"]:
            avg = sum(x["traits"][k] for x in par) / len(par)
            traits[k] = max(1, min(99, int(0.45 * avg + 0.55 * 50 + self.rng.gauss(0, 16))))  # heritability ~0.45 + noise
        quirks = []
        for x in par:
            if x["quirks"] and self.rng.random() < 0.35: quirks.append(self.rng.choice(x["quirks"]))
        from .generator import QUIRKS, ADULT_ONLY
        while len(quirks) < 2: q = self.rng.choice([q for q in QUIRKS if q not in ADULT_ONLY]); quirks.append(q) if q not in quirks else None
        baby = {"name": f"{first} {surname}", "age": 0, "sex": "male" if sex_m else "female", "born": yr, "role": "child", "traits": traits, "quirks": quirks[:3],
                "education": "too young", "health": "good", "veteran": False, "job": None, "secret": None, "money_personal": 0}
        pid = self.add_person(baby, mother["household"]); b = self.people[pid]; b["born_day"] = self.day; b["parents"] = [x["id"] for x in par]
        for x in par: x.setdefault("children", []).append(pid); x["rel"][pid] = {"affinity": 70, "trust": 50, "tags": ["family", "child"]}
        ev("birth", actors=[x["id"] for x in par] + [pid], text=f"{mother['name']} gives birth to a {'boy' if sex_m else 'girl'}: {b['name']}.", importance=8, public=True)
        if self.rng.random() < 0.025: b["flags"]["frail_infant"] = True

    def kill(self, p, cause, ev):
        p["alive"] = False; p["death"] = {"date": self.date_str, "cause": cause}
        for c in self.companies.values():
            if p["id"] in c["employees"]: c["employees"].remove(p["id"])
        if p.get("spouse") and p["spouse"] in self.people: self.people[p["spouse"]]["widowed"] = True
        # Social Security survivors: if the one who died drew benefits, or worked a job that counted toward Social Security
        if p.get("ss") or ((p.get("employer") or job_pay(p.get("job"))) and self.rng.random() < history.SS_WORKER_COVERED.get(min(max(self.date.year, 1950), 1959), 0.9)):
            self.households[p["household"]]["survivor_of"] = p["id"]
        ev("death", actors=[p["id"]], text=f"{p['name']} ({p['age']}) {cause}.", importance=10, public=True, data={"said": f"{p['name']} {cause}."})

    # ------------------------------------------------------------------ discoveries (rolled when someone digs / explores / builds)
    def discovery_roll(self, p, activity, ev):
        odds = {"dig": 0.03, "explore": 0.018, "build": 0.015, "farm": 0.01, "fish": 0.008}.get(activity, 0.005)  # halved: finds should be rare
        if self.rng.random() > odds: return None
        pool = DISCOVERY_TABLE["_common"] + DISCOVERY_TABLE.get(self.geo, [])
        if self.rng.random() < 0.02: pool = DISCOVERY_TABLE["_rare"]
        if self.rng.random() < 0.004: pool = DISCOVERY_TABLE["_unexplained"]
        w, desc, truth, value = self.rng.choices(pool, [x[0] for x in pool])[0]
        item = {"desc": desc, "truth": truth, "value": value, "owner": p["id"], "found": self.date_str, "where": p["location"]}
        p.setdefault("items", []).append(item)
        ev("discovery", actors=[p["id"]], text=f"{p['name']} finds {desc} while {ING.get(activity, activity + 'ing')} at {self.places.get(p['location'], {}).get('name', 'somewhere')}.",
           importance=6 if value > 500 or truth == "UNEXPLAINED" else 3, public=False, data={"truth": truth, "value": value})
        return item

    # ------------------------------------------------------------------ outside world + real history (daily)
    def outside_day(self, ev):
        for d, head, eff in history.events_on(self.date_str):
            ev("history", text=f"On the radio: {head}", importance=4, public=True, data={"headline": head})
            if "draft" in eff: self.flags["draft"] = eff["draft"]
            if "market" in eff: self.flags["market"] = eff["market"].get("*", 1.0)
            for k in ("highway_program", "polio_vaccine", "bomb_shelter_fever"):
                if eff.get(k): self.flags[k] = True
        if self.day == 0:
            self.flags["draft"] = history.draft_state(self.date_str); self.flags["market"] = history.market_mult(self.date_str)
            self.flags["polio_vaccine"] = self.date_str >= "1955-04-12"; self.flags["highway_program"] = self.date_str >= "1956-06-29"
        if self.date.day != 15: return
        # draft notices (monthly)
        rate = history.DRAFT_MONTHLY.get(self.flags["draft"], 0)
        for p in self.living():
            if p["sex"] == "male" and 18 <= p["age"] <= 26 and not p.get("children") and not p["offtown"] and self.rng.random() < rate:
                ev("draft_notice", actors=[p["id"]], text=f"{p['name']} receives a draft notice from the Selective Service.", importance=8, public=True)
                p["flags"]["drafted_on"] = self.day
        # drafted men leave after ~3 weeks (they may try to dodge via actions)
        for p in self.living():
            dd = p["flags"].get("drafted_on")
            if dd is not None and self.day - dd >= 21 and not p["flags"].get("dodged"):
                self.leave_town(p, "the Army", ev, kind="army"); p["flags"].pop("drafted_on", None)
        # off-screen lives tick monthly
        for pid, rec in list(self.offtown.items()):
            p = self.people[pid]
            if not p["alive"]: continue
            if rec["kind"] in ("jail", "trip"): continue  # released / home again by the world step on the day (fix 5: trips)
            if rec["kind"] == "army":
                if history.at_war(self.date_str):
                    if self.rng.random() < history.WAR_DEATH_MONTHLY * 30: self.kill(p, "was killed in action overseas", ev); ev("telegram", actors=[i for i in self.households[p["household"]]["members"]], text=f"A Western Union telegram arrives at the {self.households[p['household']]['surname']} house.", importance=10, public=True); continue
                    if self.rng.random() < history.WAR_WOUND_MONTHLY * 30: rec["wounded"] = True; ev("letter", actors=self.households[p["household"]]["members"], text=f"Word comes that {p['name']} was wounded overseas.", importance=7, public=True)
                rec["months"] += 1
                if rec["months"] >= 24: self.return_home(p, "home from the Army" + (" with a limp" if rec.get("wounded") else ""), ev)
            else:
                rec["months"] += 1; luck = (p["traits"]["conscientiousness"] + p["traits"]["openness"]) / 200
                roll = self.rng.random()
                if rec["kind"] == "hollywood" and roll < 0.004 * luck * 2:
                    rec["status"] = "famous"; ev("fame", actors=[pid], text=f"{p['name']} lands a part in a picture. Their face is going up on billboards.", importance=9, public=True)
                elif roll < 0.05: ev("letter", actors=self.households[p["household"]]["members"], text=f"A letter arrives from {p['name']} in {rec['where']}.", importance=3, public=False)
                if rec["months"] > 6 and self.rng.random() < 0.025: self.return_home(p, "back in town" + (", famous" if rec.get("status") == "famous" else ", no richer than they left"), ev)
        # newcomers when jobs are open and the town is doing fine
        c = self.companies.get("co1")
        if c and c["status"] == "open" and c["cash"] > 3000 and self.rng.random() < 0.18:
            ev("opportunity", text=f"Word gets around that {c['name']} could use more hands.", importance=2, public=True)
            self.flags["newcomer_pending"] = True
        if self.flags.get("highway_program") and self.date.month == 3 and self.rng.random() < 0.3 and self.geo != "island":
            ev("highway", text="State highway engineers write to the town: the new interstate's route through the county is being surveyed.", importance=7, public=True)

    # (The old hand-written happenings/town-event lists were removed Nov 18: the world step in fate.py replaced them.)
    def house_fire(self, h, ev, sev=None):
        """A house fire: realistic odds (chimneys, stoves, wiring). Severity by dice; a destroyed home leaves the family burned out."""
        r = self.rng; sn = h["surname"]; members = [i for i in h["members"] if self.people[i]["alive"] and not self.people[i]["offtown"]]
        if sev not in ("small", "bad", "destroyed"): sev = r.choices(["small", "bad", "destroyed"], [55, 30, 15])[0]
        pl = self.places[h["place"]]
        cost = {"small": r.randint(30, 150), "bad": r.randint(200, 900), "destroyed": r.randint(1500, 4000)}[sev]
        pl["condition"] = max(0.05, pl["condition"] - {"small": 0.1, "bad": 0.4, "destroyed": 1.0}[sev]); h["repairs_needed"] = h.get("repairs_needed", 0) + cost
        if sev == "destroyed": pl["burned"] = self.date_str; h["burned_out"] = True
        hurt = []
        if sev != "small":
            for i in members:
                if r.random() < (0.15 if sev == "bad" else 0.3): self.people[i]["injury"] = max(self.people[i]["injury"], r.randint(5, 30)); hurt.append(self.people[i]["name"])
            if sev == "destroyed" and members and r.random() < 0.08: self.kill(self.people[r.choice(members)], "died in the fire", ev)
        text = {"small": f"A small fire in the {plural(sn)}' kitchen, put out quick.", "bad": f"Fire badly damages the {sn} house.", "destroyed": f"The {sn} house burns to the ground."}[sev]
        ev("town_event", actors=members, text=text + (f" Hurt: {', '.join(hurt)}." if hurt else ""), importance={"small": 5, "bad": 8, "destroyed": 9}[sev], public=True, data={"kind": "house_fire", "severity": sev})

    # ------------------------------------------------------------------ homes and households: anything real people do (move, lose a home, take people in)
    def _vacate(self, key):
        pl = self.places.get(key)
        if not pl: return
        if pl.get("kind") == "home": pl["household"] = None; pl["vacant"] = True; pl["name"] = pl["name"].replace("the ", "the empty ", 1) if "empty" not in pl["name"] else pl["name"]
        elif pl.get("kind") == "camp": self.places.pop(key, None)

    def lose_home(self, h, why, ev):
        """The household loses the roof over its head. They have nowhere of their own until they find somewhere (or someone takes them in)."""
        old = h["place"]; self._vacate(old); camp = f"camp_{h['id']}"
        self.places[camp] = {"name": f"nowhere: the {plural(h['surname'])} are sleeping wherever they can", "kind": "camp", "household": h["id"], "x": 0, "condition": 0.3}
        h.update({"place": camp, "home": "none", "monthly_housing": 0, "behind": 0, "homeless": True, "repairs_needed": 0})
        members = [i for i in h["members"] if self.people[i]["alive"] and not self.people[i]["offtown"]]
        for i in members: self.people[i]["location"] = camp
        ev("lost_home", actors=members, text=f"The {plural(h['surname'])} have lost their home ({why}).", importance=8, public=True, data={"why": why})

    def set_home(self, h, key, terms, ev, by=None):
        """The household moves into a vacant house or a new place, on the terms given (rent, mortgage, own outright, or free)."""
        terms = (terms or "rent").lower(); kind = "rented" if "rent" in terms else "mortgaged" if "mortgage" in terms else "owned outright" if "own" in terms or "buy" in terms else "free"
        if h["place"] != key: self._vacate(h["place"])
        if key not in self.places:
            self.places[key] = {"name": f"the {h['surname']} place", "kind": "home", "household": h["id"], "x": 0, "condition": 0.85}
        pl = self.places[key]; pl.update({"household": h["id"], "vacant": False, "name": f"the {h['surname']} house"})
        h.update({"place": key, "home": kind, "monthly_housing": {"rented": 38, "mortgaged": 48}.get(kind, 0), "homeless": False, "behind": 0})
        for i in h["members"]:
            if self.people[i]["alive"] and not self.people[i]["offtown"]: self.people[i]["location"] = key
        ev("moved", actors=[i for i in h["members"] if self.people[i]["alive"]], text=f"The {plural(h['surname'])} move into {pl['name']}" + (f" ({kind})" if kind != "free" else "") + ".", importance=6, public=True)

    def move_person(self, p, to_h, ev, why=""):
        """One person changes households: moves in with someone, or is taken in."""
        old = self.households[p["household"]]
        if old is to_h: return
        old["members"].remove(p["id"]); to_h["members"].append(p["id"]); p["household"] = to_h["id"]; p["location"] = to_h["place"]
        if not [i for i in old["members"] if self.people[i]["alive"]]: self._vacate(old["place"])
        ev("moved", actors=[p["id"]], text=f"{p['name']} moves in with the {plural(to_h['surname'])}" + (f" ({why})" if why else "") + ".", importance=6, public=True)

    def new_household(self, p, ev):
        """Someone sets up on their own (a grown child, a spouse after a split, a boarder). They start with no money of their own."""
        old = self.households[p["household"]]; hid = max(self.households) + 1; sn = p["name"].split()[-1]
        self.households[hid] = {"id": hid, "surname": sn, "kind": "moved out", "members": [], "savings": 0, "debt": 0, "home": "none", "place": None,
                                "monthly_housing": 0, "withhold_tax": False, "has_tv": False}
        old["members"].remove(p["id"]); self.households[hid]["members"].append(p["id"]); p["household"] = hid
        if not [i for i in old["members"] if self.people[i]["alive"]]: self._vacate(old["place"])
        return self.households[hid]

    def repair(self, h, p, amount, ev, how="", payer=None, labor=0):
        """Someone puts money into fixing up their home (their choice, at their price). Damage is fixed in proportion to what's spent;
        a burned-out house stands again once the whole bill is paid. Nothing repairs itself."""
        need = h.get("repairs_needed", 0); pl = self.places.get(h["place"]) or {}
        if need <= 0 or not pl: return 0
        payer = payer or h
        if labor and labor > 0: need_after = max(0, need - labor); pl["condition"] = min(1.0, pl["condition"] + (1.0 - pl["condition"]) * (need - need_after) / need); h["repairs_needed"] = need = round(need_after, 2)
        spend = round(min(need, max(0, payer["savings"]), amount if amount and amount > 0 else need), 2)
        if spend <= 0 and not labor: return 0
        payer["savings"] -= spend; frac = spend / need if need else 1; h["repairs_needed"] = round(need - spend, 2)
        pl["condition"] = min(1.0, pl["condition"] + (1.0 - pl["condition"]) * frac)
        if h["repairs_needed"] <= 0.5:
            h["repairs_needed"] = 0; pl["condition"] = 1.0
            if pl.get("burned"): pl["burned"] = None; h["burned_out"] = False; pl["rebuilt"] = self.date_str
        done = h["repairs_needed"] == 0
        rebuilt = pl.get("rebuilt") == self.date_str
        text = (f"The {h['surname']} house stands again: {p['name']} pays the last ${int(spend)} to finish rebuilding it." if rebuilt else
                f"{p['name']} puts " + (f"${int(spend)}" if spend else "") + (" and " if spend and labor else "") + ("a hand" if labor else "") + f" into fixing up the {h['surname']} house" + (f" ({how})" if how else "") + ("; it's all fixed now." if done else "."))
        ev("repair", actors=[p["id"]], text=text,
           importance=6 if rebuilt else 3, public=rebuilt, data={"spent": spend, "left": h["repairs_needed"]})
        return spend or labor

    def leave_town(self, p, where, ev, kind="city"):
        p["offtown"] = True; p["location"] = "away"
        self.offtown[p["id"]] = {"kind": kind, "where": where, "months": 0, "left": self.date_str}
        for c in self.companies.values():
            if p["id"] in c["employees"]: c["employees"].remove(p["id"])
        ev("left_town", actors=[p["id"]], text=f"{p['name']} leaves for {where}.", importance=7, public=True)

    def trip(self, p, where, days, ev):
        """Fix 5 (season break): a resident goes away for a while and comes back (kin, a funeral, business elsewhere). Unlike leave_town they
        keep their job and home; they are marked away so the town's record knows where they are, and they come home on the day they said."""
        days = max(1, min(60, int(days or 3)))
        p["offtown"] = True; p["location"] = "away"
        self.offtown[p["id"]] = {"kind": "trip", "where": where, "months": 0, "left": self.date_str, "until": self.day + days}
        ev("left_town", actors=[p["id"]], text=f"{p['name']} goes away to {where} for about {days} day{'s' if days > 1 else ''}.", importance=5, public=True)

    def return_home(self, p, how, ev):
        p["offtown"] = False; p["location"] = self.households[p["household"]]["place"]; self.offtown.pop(p["id"], None)
        ev("returned", actors=[p["id"]], text=f"{p['name']} is {how}.", importance=8, public=True)

    # ------------------------------------------------------------------ snapshot for render / ledger
    def snapshot(self):
        return {"day": self.day, "date": self.date_str, "season": self.season, "weather": dict(self.weather.get("today", {})), "season_label": self.weather.get("season_label"),
                "people": {pid: {k: p[k] for k in ("name", "age", "sex", "alive", "location", "offtown", "job", "household", "needs", "illness", "injury")} for pid, p in self.people.items()},
                "households": {hid: {"surname": h["surname"], "savings": round(h["savings"]), "debt": h["debt"], "members": h["members"], "condition": (self.places.get(h["place"]) or {}).get("condition", 1.0), "has_tv": h["has_tv"], "place": h["place"], "homeless": bool(h.get("homeless")), **econ.snapshot_bits(self, h)} for hid, h in self.households.items()},
                "companies": {cid: {"name": c["name"], "cash": round(c["cash"]), "employees": list(c["employees"]), "owner": c["owner"], "status": c["status"], "industry": c.get("industry", "")} for cid, c in self.companies.items()},
                "town": {"treasury": self.town["treasury"], "offices": dict(self.town["offices"]), "laws": list(self.town["laws"]), "store_level": self.shops["store"]["level"], "meal": round(self.shops["diner"]["meal"] * history.price_index(self.date.year), 2)},
                # what the camera can see: house condition, fires, new buildings (a record only; nothing here feeds back into the town)
                "places": {k: {x: v[x] for x in ("name", "kind", "condition", "burned", "rebuilt", "built", "owner", "household", "vacant") if x in v} for k, v in self.places.items() if v.get("kind") in ("home", "building", "business", "camp")}}


def default_charter():
    return {"text": [
        "1. The town is governed by a Mayor and a Council of three, elected by residents aged 21 and over, one vote each, by secret ballot.",
        "2. Elections are held on the town's first day and every two years after. Any resident aged 21 or over may stand.",
        "3. Any resident may propose a measure. The Council decides by majority; the Mayor votes only to break a tie.",
        "4. The Council may set the town tax and spend the treasury by majority vote.",
        "5. This charter may be changed or abolished by a majority of all eligible voters at a town meeting."],
        "voting_age": 21, "term_days": 730, "council_seats": 3, "meeting_weekday": 1}


def plural(sn): return sn + ("es" if sn.endswith(("s", "x", "z", "ch", "sh")) else "s")


def describe_link(l, a, b):
    if l["kind"] == "grudge": return f"The {plural(a['surname'])} and the {plural(b['surname'])} have had bad blood for {l['years']} years over {l['over']}."
    if l["kind"] == "debt": return f"The {plural(a['surname'])} owe the {plural(b['surname'])} ${l['amount']}."
    if l["kind"] == "old romance": return f"Someone in the {a['surname']} house and someone in the {b['surname']} house were sweethearts once."
    if l["kind"] == "friendship": return f"The {plural(a['surname'])} and the {plural(b['surname'])} are old friends."
    if l["kind"] == "rivalry": return f"The {plural(a['surname'])} and the {plural(b['surname'])} have always tried to outdo each other."
    if l["kind"] == "church friends": return f"The {plural(a['surname'])} and the {plural(b['surname'])} sit together at church and trade suppers."
    if l["kind"] == "neighbors who help each other": return f"The {plural(a['surname'])} and the {plural(b['surname'])} lend each other tools and a hand when it's needed."
    return f"The {plural(a['surname'])} and the {plural(b['surname'])} were once business partners; it ended quietly and nobody talks about it."
