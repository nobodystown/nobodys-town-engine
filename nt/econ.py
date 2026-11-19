"""Money between people (approved by Aaron, Nov 18 10pm; built Nov 18-19).

The principle: nature and the outside world stay rules (national prices, credit rules, what a 1950s bank asks for, interest
rates). Anything a real person would decide is a resident's decision: what to buy and when, cash or time payments, where to
buy groceries, what a shop charges, what an owner pays, whether to put money in the bank, whether to borrow, and (for a
resident who founds a bank) whom to lend to. Nothing here rewards or punishes ambition; it only makes choices cost what they cost.

Era data below is published with the season, like history.py. Figures marked "estimate" are ours, built around the sourced ones.
"""
import math, random, re
from . import history

# ------------------------------------------------------------------ what things cost (1950 dollars; later years follow CPI)
# key: words that name it, price, credit class, upkeep a month (gas, oil, repairs, power), source
GOODS = {
    "new car": (("new car", "new automobile", "new chevrolet", "new ford", "new plymouth", "new sedan"), 1500, "car", 20,
                "1950 Chevrolet Deluxe $1,529; average new car about $1,500"),
    "pickup truck": (("pickup", "truck"), 1400, "car", 20, "estimate, priced near a new car"),
    "washing machine": (("washing machine", "washer"), 160, "appliance", 0.5, "Norge washer $158 (1957 ad); estimate for 1950"),
    "vacuum cleaner": (("vacuum cleaner", "vacuum"), 70, "appliance", 0.2, "Kenmore tank vacuum $68-80 (1957 ad)"),
    "sewing machine": (("sewing machine",), 90, "appliance", 0.1, "estimate"),
    "record player": (("record player", "phonograph", "hi-fi", "victrola"), 60, "appliance", 0.1, "estimate"),
    "television": (("television", "tv set", "tv"), 220, "appliance", 1.0, "Sears 1950 Silvertone 12.5-inch table set $220 (Television Digest, Jan 1950)"),
    "radio": (("radio",), 35, "appliance", 0.2, "estimate"),
    "refrigerator": (("refrigerator", "icebox", "frigidaire"), 250, "appliance", 1.5, "estimate from 1950 ads ($200-300)"),
    "freezer": (("freezer", "deep freeze"), 250, "appliance", 1.5, "estimate"),
    "electric range": (("electric range", "cookstove", "stove", "range"), 200, "appliance", 1.0, "estimate"),
    "piano": (("piano",), 450, "furniture", 0, "estimate"),
    "furniture": (("furniture", "sofa", "couch", "bedroom suite", "dining set", "dinette", "armchair", "easy chair"), 150, "furniture", 0,
                  "1955 ad: bedroom suite $320, chrome breakfast set $140"),
    "tractor": (("tractor",), 1600, "equipment", 8, "estimate"),
    "boat": (("boat", "skiff", "outboard motor"), 400, "equipment", 3, "estimate"),
    "bicycle": (("bicycle", "bike"), 40, "small", 0, "estimate"),
    "typewriter": (("typewriter",), 90, "small", 0, "estimate"),
    "used car": (("used car", "secondhand car", "car", "automobile", "jalopy", "sedan", "coupe"), 600, "car", 20, "estimate: used cars ran $400-1,000"),
}
HOUSE_1950 = 5000  # estimate: a small-town house; the 1950 census median value of owner-occupied homes was $7,354 nationally
CAR_KEYS = ("new car", "used car", "pickup truck")
# What households already had when we arrived (1950, approximate national shares): radio ~95%, mechanical refrigerator ~80%,
# washing machine ~70%, a car ~59%, television (history.TV_SHARE). Rolled per household, richer families a little likelier.
START_OWN = (("radio", 0.95), ("refrigerator", 0.80), ("washing machine", 0.70), ("car", 0.59))
DURABLES_SHARE = 0.16  # BEA 1950: durable goods were about 16% of personal consumption. No longer spent automatically; families decide.
WHOLESALE = 0.78       # a grocer pays about 78 cents for what sells for a dollar in the county seat (22% margin, as before)
DEALER_COST = 0.85     # a store ordering an appliance from the catalog keeps about 15%
STORE_LEVEL = (0.70, 1.30)   # a store can't charge more than about 30% over the county seat before families simply drive there
MEAL_RANGE = (0.35, 1.20)    # a diner meal, 1950 dollars (county-seat cafes charged about 60 cents)
CREDIT_WORDS = re.compile(r"on time|instal+ment|time payment|on credit|credit|easy terms|monthly payment|payments|financ|on the book|loan|mortgage", re.I)

# Credit for goods. Regulation W (Federal Reserve) ran Sept 18, 1950 - May 7, 1952: cars 1/3 down and 21 months; appliances,
# radios and TVs 15% down and 18 months; furniture 10% down and 18 months (Time, Sept 1950). Outside those dates, dealers' own
# terms: cars 1/3 down, 24 months (36 from 1955, as auto credit loosened); appliances and furniture 10% down, 24 months (estimates).
# Finance charges: add-on 6% a year on cars, 10% on store and appliance credit (estimates; about 11% and 18% a year in true interest).
def credit_terms(kind, date):
    regw = "1950-09-18" <= date < "1952-05-07"
    if kind in ("car", "equipment"): return (1 / 3, 21 if regw else (36 if date >= "1955-01-01" else 24), 0.06)
    if kind == "appliance": return (0.15 if regw else 0.10, 18 if regw else 24, 0.10)
    if kind == "furniture": return (0.10, 18 if regw else 24, 0.10)
    return None  # small things are paid in cash

# Mortgages. FHA top rate 4.25% from April 1950 (NBER), then about 4.5% from May 1953, 5% from Dec 1956, 5.25% from Aug 1957,
# 5.75% from Sept 1959; VA (veterans) about 4% to 1953, 4.5% to 1958, 4.75% after, little or nothing down. Down payment for others
# about 20% (10% after the Housing Act of Aug 1954). Term 25 years. Housing payments held to about a quarter of income.
def mortgage_terms(date, veteran):
    if veteran: return (0.0, 0.04 if date < "1953-05-01" else 0.045 if date < "1958-04-01" else 0.0475, 300)
    rate = 0.0425 if date < "1953-05-01" else 0.045 if date < "1956-12-01" else 0.05 if date < "1957-08-01" else 0.0525 if date < "1959-09-01" else 0.0575
    return (0.20 if date < "1954-08-02" else 0.10, rate, 300)

# County bank loans (estimates for a small-town bank): personal loans to about a quarter of a year's income, 18 months, 6% add-on;
# home repair (FHA Title I) up to $2,500, 36 months, 5% add-on; business loans only against collateral, to half its value, 3 years
# at 5% (5.5% from 1955, 6% from 1957). Payments on all debts held to about 35% of income. A repossession or foreclosure closes
# the door for five years. A newcomer without local references, or a family whose income comes and goes, is a harder sell.
def business_rate(date): return 0.05 if date < "1955-01-01" else 0.055 if date < "1957-01-01" else 0.06
# Passbook savings: commercial banks paid about 1.5% in 1950, rising to about 3% by 1959 (estimate between bank and S&L rates).
PASSBOOK = {1950: 0.015, 1951: 0.015, 1952: 0.017, 1953: 0.019, 1954: 0.02, 1955: 0.022, 1956: 0.025, 1957: 0.028, 1958: 0.03, 1959: 0.03}
FDIC_LIMIT = 10000  # deposit insurance per depositor (1950 Act)
# Federal minimum wage (Fair Labor Standards Act): 75 cents an hour from Jan 1950, $1.00 from March 1956. It covered firms in
# interstate commerce (the main employer); a small local shop was exempt.
def federal_min_day(date): return 8 * (0.75 if date < "1956-03-01" else 1.00)
SHOP_WAGE_1950 = 1900 / 310  # a clerk or waitress, about $1,900 a year (estimate), by the working day


def P(w): return history.price_index(w.date.year)
def W(w): return history.wage_index(w.date.year)
def money(x): return f"${int(round(x)):,}"


def match_good(text):
    t = " " + (text or "").lower() + " "
    for k, (words, *_rest) in GOODS.items():
        if any(re.search(r"\b" + re.escape(x) + r"\b", t) for x in words): return k
    if re.search(r"\b(house|home_\w+|the place we rent)\b", t): return "house"
    return None


def car_value(w, car): return GOODS["new car"][1] * P(w) * 0.78 ** max(0, w.date.year - car["model_year"])


def house_value(w, pl): return HOUSE_1950 * P(w) * max(0.2, (pl or {}).get("condition", 1.0))


# ------------------------------------------------------------------ setup (separate dice, so every seed still rolls the same town)
def setup(w):
    r = random.Random(w.gen["seed"] * 104729 + 17)
    w.loans = []; w.applications = []; w.econ_log = []
    sh, dh = w.places["store"].get("household"), w.places["diner"].get("household")
    w.shops = {"store": {"owner_h": sh, "level": 1.0, "staff": [], "week": 0.0, "week_sales": 0.0, "custom": [], "last_custom": []},
               "diner": {"owner_h": dh, "meal": 0.60, "staff": [], "week": 0.0, "meals": 0}}
    tv = history.TV_SHARE.get(w.date.year, 0.09)
    for h in w.households.values():
        h.setdefault("owns", {}); h.setdefault("deposits", {}); h.setdefault("credit", {"missed": 0, "bad_until": None}); h["groceries_at"] = "store"
        rich = max(0, h["savings"]) / 2000
        for k, share in START_OWN + (("television", tv),):
            if r.random() < min(0.98, share * (0.8 + 0.4 * min(1.0, rich))):
                if k == "car": age = r.choice([0, 1, 2, 3, 4, 6, 8, 10]) if h["savings"] > 1500 else r.choice([3, 5, 6, 8, 10, 12, 14]); own(w, h, "used car", w.date.year - age)
                else: own(w, h, k, w.date.year - r.randint(0, 8))
        # a mortgage the family already had: a real loan with years left on it (the payment they already paid each month)
        if h["home"] == "mortgaged" and h["monthly_housing"] > 0:
            left = r.randint(24, 240); pay = h["monthly_housing"]; h["monthly_housing"] = 0
            w.loans.append({"id": f"N{len(w.loans) + 1}", "lender": "county", "h": h["id"], "who": None, "kind": "mortgage", "payment": pay, "months_left": left,
                            "rate": 0.045, "collateral": {"type": "home"}, "missed": 0, "status": "open", "since": w.date_str})
        # what the family owed when we arrived: a note at the bank, paid off over three years at 6%
        # (paid off at about a tenth of what the family earns, 1 to 10 years, the way a banker would have written the note)
        if h.get("debt", 0) > 0:
            inc = expected_income_m(w, h); n = int(max(12, min(120, math.ceil(h["debt"] / max(1.0, 0.10 * inc))))) if inc > 0 else 120
            pay = round(h["debt"] * (0.06 / 12) / (1 - (1 + 0.06 / 12) ** -n), 2)
            w.loans.append({"id": f"N{len(w.loans) + 1}", "lender": "county", "h": h["id"], "who": None, "kind": "old debt", "payment": pay, "months_left": n,
                            "rate": 0.06, "collateral": {"type": "none"}, "missed": 0, "status": "open", "since": w.date_str})
        refresh_debt(w, h)


def expected_income_m(w, h):
    """What a household's jobs pay in a month (before anything has been earned in the run)."""
    from .world import job_pay
    t = 0.0
    for i in h["members"]:
        q = w.people[i]
        if not q["alive"]: continue
        if q.get("employer") in w.companies: t += w.companies[q["employer"]]["wage_day"] * W(w) * 5.5 * 52 / 12
        elif job_pay(q.get("job")): t += job_pay(q.get("job"))[0] * W(w) / 12
    return t


def ensure(h):
    """Households formed after the start (newcomers, a grown child moving out) get the same books as everyone else."""
    h.setdefault("owns", {}); h.setdefault("deposits", {}); h.setdefault("credit", {"missed": 0, "bad_until": None}); h.setdefault("groceries_at", "store")
    return h


def own(w, h, key, model_year=None):
    y = model_year or w.date.year
    if key in CAR_KEYS:
        h["owns"].pop("used car", None); h["owns"].pop("new car", None); h["owns"].pop("pickup truck", None)
        h["car"] = {"model_year": y, "key": key}
    h["owns"][key] = {"year": y, "since": w.date_str}
    if key == "television": h["has_tv"] = True


def owns_text(w, h):
    out = []
    for k, v in h.get("owns", {}).items():
        if k in CAR_KEYS: out.append(f"a {v['year']} {'pickup truck' if k == 'pickup truck' else 'car'}")
        else: out.append(("a " if not k.startswith(("a", "e", "i", "o", "u")) else "an ") + (k + " set" if k == "television" else k) if k != "furniture" else "some new furniture")
    return ", ".join(out)


def cash(h): return h["savings"] + sum(h.get("deposits", {}).values())


def draw(w, h, amt):
    """Take money from the household: cash on hand first, then the bank (like writing a check)."""
    short = amt - max(0, h["savings"])
    for lid in list(h.get("deposits", {})):
        if short <= 0: break
        take = min(short, h["deposits"][lid])
        if take > 0 and withdraw_from(w, h, lid, take): short -= take
    h["savings"] -= amt


def cover(w, h):
    """A family that has run short of cash writes a check on its own bank account (if it has one)."""
    for lid in list(h.get("deposits", {})):
        if h["savings"] >= 0: break
        withdraw_from(w, h, lid, min(-h["savings"], h["deposits"][lid]))


def withdraw_from(w, h, lid, amt):
    if lid != "county":
        c = w.companies.get(lid)
        if not c or c["status"] != "open" or c["cash"] < amt: return False
        c["cash"] -= amt
    h["deposits"][lid] -= amt; h["savings"] += amt
    if h["deposits"][lid] <= 0.005: h["deposits"].pop(lid)
    return True


def refresh_debt(w, h):
    h["debt"] = round(sum(l["payment"] * l["months_left"] for l in w.loans if l["h"] == h["id"] and l["status"] in ("open", "in collection")), 2)


def loans_text(w, h):
    """What a family knows about its own debts: who holds each one, the payment, how far along, and whether they're behind."""
    out = []
    for l in w.loans:
        if l["h"] != h["id"] or l["status"] not in ("open", "in collection"): continue
        what = (l.get("collateral") or {}).get("item") or {"old debt": "an old note"}.get(l["kind"], l["kind"])
        out.append(f"{what} with {lender_name(w, l['lender'])}, ${int(round(l['payment']))} a month, {l['months_left']} payments left" +
                   (f", {l['missed']} missed in a row" if l["missed"] else "") + (" (turned over to a collection agency)" if l["status"] == "in collection" else ""))
    return "; ".join(out)


def relief(w, p, months, ev):
    """The lender agrees to let missed payments slide (decided by the referee's odds and the dice, like any outside answer)."""
    h = w.households[p["household"]]; months = max(1, min(3, int(months or 1)))
    behind = [l for l in w.loans if l["h"] == h["id"] and l["status"] == "open" and l["missed"]]
    if not behind: return False
    l = max(behind, key=lambda x: x["missed"]); l["months_left"] += min(l["missed"], months); l["missed"] = 0
    refresh_debt(w, h)
    ev("loan_relief", actors=[p["id"]], text=f"{lender_name(w, l['lender']).capitalize()} agrees to carry the {h['surname']} household's missed {l['kind']} payments to the end of the loan.", importance=5)
    return True


def payments(w, h, kinds=None): return sum(l["payment"] for l in w.loans if l["h"] == h["id"] and l["status"] == "open" and (kinds is None or l["kind"] in kinds))


def income_m(h):
    hist = h.get("earn_hist") or []
    return sum(hist[-3:]) / max(1, len(hist[-3:])) if hist else 0


def shop_runners(w, k):
    oh = w.shops[k]["owner_h"]
    if oh not in w.households: return []
    return [w.people[i] for i in w.households[oh]["members"] if w.people[i]["alive"] and w.people[i]["age"] >= 18 and not w.people[i]["offtown"]]


def shop_of(w, p):
    for k, s in w.shops.items():
        if s["owner_h"] == p["household"] and p["age"] >= 18: return k
    return None


def lender_name(w, lid):
    if lid == "county": return "the bank in the county seat"
    if lid in ("dealer", "store"): return "the dealer" if lid == "dealer" else "the general store"
    c = w.companies.get(lid); return c["name"] if c else "the bank"


def local_banks(w): return [c for c in w.companies.values() if c["status"] == "open" and "bank" in (c.get("industry") or "").lower() and c["id"] != "co1"]


def is_closed(w, place):
    """A place closed by town ordinance right now (law.py 'closing')."""
    for l in w.town.get("laws", []):
        for op in l.get("ops") or []:
            if op.get("op") == "closing" and op.get("place") == place:
                when = (op.get("when") or "").lower()
                if when == "always" or (when == "sunday" and w.date.weekday() == 6) or (when == "night" and w.slot == 3): return l
    return None


def law_value(w, op_name, key, default=None):
    v = default
    for l in w.town.get("laws", []):
        for op in l.get("ops") or []:
            if op.get("op") == op_name and (key is None or op.get("place") == key):
                v = op
    return v


def min_wage_day(w, c=None):
    m = 0.0
    op = law_value(w, "min_wage", None)
    if op:
        try: m = float(op.get("per_week") or 0) / 5.5
        except (TypeError, ValueError): m = 0.0
    if c is not None and c.get("id") == "co1": m = max(m, federal_min_day(w.date_str))
    return m


# ------------------------------------------------------------------ daily money flows (called from world.economy_day)
def groceries(w, h, food):
    """Where the family buys its groceries is the family's own choice. The store's price is the owner's choice (within what
    the county seat allows). Returns what the family paid."""
    ensure(h); st = w.shops["store"]; oh = st["owner_h"]
    if h.get("groceries_at", "store") == "store" and oh in w.households and oh != h["id"] and shop_runners(w, "store") and not is_closed(w, "store"):
        lvl = st["level"]; paid = food * lvl; margin = food * (lvl - WHOLESALE)
        o = w.households[oh]; o["savings"] += margin; w.earned(o, margin); st["week"] += margin; st["week_sales"] += paid
        if h["id"] not in st["custom"]: st["custom"].append(h["id"])
    else:
        paid = food
        if w.date.weekday() == 5:  # the weekly trip to the county seat: gas or a ride; a ferry from an island
            paid += (0.5 if h.get("car") else 1.0) * P(w) * (2.0 if w.geo == "island" else 1.0)
    if "refrigerator" in h.get("owns", {}): paid *= 0.96  # less spoiled food
    return paid


def shop_payroll(w, ev):
    """Friday: anyone working at the diner or the store is paid by the family that runs it, at the wage the owner set."""
    for k, s in w.shops.items():
        oh = w.households.get(s["owner_h"])
        for pid in list(s["staff"]):
            q = w.people[pid]
            if not q["alive"] or q.get("shop_job") != k: s["staff"].remove(pid); continue
            if q["offtown"]: continue
            pay = round(max(q.get("wage_day") or SHOP_WAGE_1950 * W(w), min_wage_day(w)) * 5.5, 2)
            if oh: oh["savings"] -= pay
            hh = w.households[q["household"]]; hh["savings"] += pay; w.earned(hh, pay)


def monthly(e, ev):
    """The first of the month: loan payments, interest on deposits, running costs, and each family's own look at the books."""
    w = e.w; y = w.date.year
    for h in w.households.values():
        ensure(h)
        alive = [w.people[i] for i in h["members"] if w.people[i]["alive"]]
        if not alive: continue
        # running costs of what they own (gas and repairs for a car, power for appliances)
        up = sum(GOODS[k][3] for k in h.get("owns", {}) if k in GOODS) * P(w)
        if up: h["savings"] -= up
        # interest on money in the bank
        for lid, amt in list(h.get("deposits", {}).items()):
            rate = PASSBOOK.get(min(max(y, 1950), 1959), 0.03) if lid == "county" else (w.companies.get(lid, {}).get("deposit_rate") or PASSBOOK.get(min(max(y, 1950), 1959), 0.03))
            i = round(amt * rate / 12, 2)
            if i <= 0: continue
            if lid != "county":
                c = w.companies.get(lid)
                if not c or c["status"] != "open": continue
                c["cash"] -= i
            h["deposits"][lid] += i
        # a family short of cash pulls from its own bank account to cover it
        cover(w, h)
    pay_loans(e, ev)
    for b in local_banks(w):
        if b["cash"] < 0: bank_fails(e, b, ev)
    for h in w.households.values():
        refresh_debt(w, h)
        adults = [w.people[i] for i in h["members"] if w.people[i]["alive"] and w.people[i]["age"] >= 18 and not w.people[i]["offtown"]]
        if not adults: continue
        rnd = lambda x: (round(x / 10) * 10 if abs(x) < 1000 else round(x / 50) * 50)
        txt = f"First of the month: the household has about ${rnd(max(0, h['savings'])):,} on hand" if h["savings"] > 0 else "First of the month: there's no money on hand"
        dep = sum(h.get("deposits", {}).values())
        if dep > 1: txt += f" and about ${rnd(dep):,} in the bank"
        pm = payments(w, h)
        if pm > 0: txt += f". We owe about ${rnd(h['debt']):,}: " + loans_text(w, h)
        for a in adults: w.minds_memory[a["id"]].add(w.day, 0, txt + ".")


def pay_loans(e, ev):
    w = e.w
    for l in w.loans:
        if l["status"] not in ("open", "in collection"): continue
        h = w.households.get(l["h"])
        if not h: continue
        alive = [i for i in h["members"] if w.people[i]["alive"]]
        adults = [i for i in alive if w.people[i]["age"] >= 18]
        if not alive: l["status"] = "written off"; continue
        if cash(h) >= l["payment"]:
            draw(w, h, l["payment"]); l["months_left"] -= 1; l["missed"] = 0
            if l["lender"] in w.companies: w.companies[l["lender"]]["cash"] += l["payment"]
            if l["months_left"] <= 0:
                l["status"] = "paid"
                if l["kind"] == "mortgage" and h["home"] == "mortgaged": h["home"] = "owned outright"
                for a in adults: w.minds_memory[a].add(w.day, 0, f"We made the last payment to {lender_name(w, l['lender'])}: the {l['kind'] if l['kind'] != 'old debt' else 'old debt'} is paid off.")
                ev("loan_paid", actors=adults[:2], text=f"The {h['surname']} household pays off its {l['kind']} with {lender_name(w, l['lender'])}.", importance=4)
            continue
        if l["status"] == "in collection": continue  # the collector keeps after them; nothing more to take
        l["missed"] += 1; h["credit"]["missed"] = h["credit"].get("missed", 0) + 1; h["credit"]["last_missed"] = w.date_str
        what = l.get("collateral", {}).get("item") or l["kind"]
        for a in adults: w.minds_memory[a].add(w.day, 0, f"We couldn't make the ${int(l['payment'])} payment to {lender_name(w, l['lender'])} on the {what} ({l['missed']} missed in a row).")
        ev("payment_missed", actors=adults[:2], text=f"The {h['surname']} household misses a ${int(l['payment'])} payment to {lender_name(w, l['lender'])} ({l['missed']} in a row).", importance=5)
        limit = 6 if l["kind"] == "mortgage" else 3 if l["kind"] == "installment" else 4
        if l["missed"] >= limit: default(e, l, h, adults, ev)


def default(e, l, h, adults, ev):
    w = e.w; col = l.get("collateral") or {}; t = col.get("type"); who = lender_name(w, l["lender"])
    h["credit"]["bad_until"] = f"{w.date.year + 5}-{w.date_str[5:]}"
    if t == "home" and h["home"] in ("mortgaged", "owned outright") and not h.get("homeless"):
        l["status"] = "foreclosed"; w.lose_home(h, f"{who} foreclosed after missed mortgage payments", ev)
    elif t == "item" and col.get("item") in h.get("owns", {}):
        k = col["item"]; h["owns"].pop(k, None)
        if k in CAR_KEYS: h.pop("car", None)
        if k == "television": h["has_tv"] = False
        l["status"] = "repossessed"
        ev("repossessed", actors=adults, text=f"{who.capitalize()} repossesses the {plural_s(h['surname'])}' {k}.", importance=7, public=True,
           data={"said": f"They came and took the {plural_s(h['surname'])}' {k} back."})
    elif t == "business" and col.get("company") in w.companies and w.companies[col["company"]]["status"] == "open":
        c = w.companies[col["company"]]; c["status"] = "closed"; laid = list(c["employees"]); c["employees"] = []
        for i in laid: w.people[i]["employer"] = None; w.people[i]["job"] = "out of work"
        owner = w.people[c["owner"]]; owner["job"] = "out of work"
        l["status"] = "seized"; c["cash"] = 0
        ev("business_seized", actors=[c["owner"]] + laid, text=f"{who.capitalize()} takes over what's left of {c['name']} for an unpaid loan; it closes.", importance=9, public=True)
    else:
        l["status"] = "in collection"
        ev("collection", actors=adults[:2], text=f"{who.capitalize()} turns the {h['surname']} household's unpaid loan over to a collection agency.", importance=6)


def plural_s(sn): return sn + ("es" if sn.endswith(("s", "x", "z", "ch", "sh")) else "s")


def bank_fails(e, b, ev):
    """A local bank that can't cover what it owes closes. Federal deposit insurance pays depositors up to the limit."""
    w = e.w; b["status"] = "closed"; hit = []
    for h in w.households.values():
        amt = h.get("deposits", {}).pop(b["id"], 0)
        if amt > 0:
            back = min(amt, FDIC_LIMIT); h["savings"] += back; hit.append(h["surname"])
    for l in w.loans:
        if l["lender"] == b["id"] and l["status"] == "open": l["lender"] = "county"  # the county bank buys up its loans
    ev("bank_failed", actors=[b["owner"]], text=f"{b['name']} fails and closes its doors. Depositors are paid back by the federal insurance up to ${FDIC_LIMIT:,}.",
       importance=10, public=True)


# ------------------------------------------------------------------ buying (a household's own decision)
def buy(e, p, detail, amount, place):
    """Returns (did_text, handled). handled=False means it isn't something sold off a shelf (the referee takes it)."""
    ensure(e.w.households[p['household']])
    w = e.w; h = w.households[p["household"]]; text = (detail or "").lower()
    key = match_good(text)
    if not key: return None, False
    if key == "house": return buy_house(e, p, text, amount), True
    words, base, kind, _up, _src = GOODS[key]
    price = base * P(w)
    if key == "used car":
        price = max(150 * P(w), min(1200 * P(w), amount)) if amount and amount > 0 else price
        model = w.date.year - max(1, min(15, round((1200 * P(w) - price) / (90 * P(w)))))
    else:
        model = w.date.year
        if amount and 0.7 * price <= amount < price and kind != "car": price = amount  # a plainer model
    at_store = place == "store" and kind in ("appliance", "furniture", "small") and w.shops["store"]["owner_h"] in w.households \
        and w.shops["store"]["owner_h"] != h["id"] and shop_runners(w, "store")
    if at_store: price *= w.shops["store"]["level"]
    price = round(price, 2)
    trade = round(car_value(w, h["car"]), 2) if key in CAR_KEYS and h.get("car") else 0
    net = max(0, price - trade)
    seller = "the general store" if at_store else ("a dealer in the county seat" if kind in ("car", "equipment") else "the catalog")
    adults = [i for i in h["members"] if w.people[i]["alive"] and w.people[i]["age"] >= 18]
    name = "pickup truck" if key == "pickup truck" else ("car" if key in CAR_KEYS else key)
    wants_credit = bool(CREDIT_WORDS.search(text)) and price - trade > 0
    if trade and price - trade <= 0:  # the old car is worth more than this one: a swap, and the dealer pays the difference
        back = round(trade - price, 2); h["savings"] += back; own(w, h, key, model)
        ev_buy(e, p, h, adults, f"traded their car for a {model} {name}" + (f" and got {money(back)} back" if back >= 1 else ""), key)
        return f"traded the car for a {model} {name}", True
    terms = credit_terms(kind, w.date_str)
    if not wants_credit:
        if cash(h) >= net:
            draw(w, h, net); _sold(w, at_store, price)
            own(w, h, key, model)
            ev_buy(e, p, h, adults, f"bought {('a ' + str(model) + ' ' if key == 'used car' else 'a new ' if key in CAR_KEYS else 'a ')}{name if key != 'television' else 'television set'} from {seller} for {money(price)}" + (f" (trading in the old car for {money(trade)})" if trade else ""), key)
            return f"bought a {name} for {money(net)} cash", True
        msg = f"We didn't have the {money(net)} for the {name}."
        if terms:
            d, m, r = terms; pay = net * (1 - d) * (1 + r * m / 12) / m
            msg += f" {seller.capitalize()} would sell it on time: {money(net * d)} down and about ${int(round(pay))} a month for {m} months."
        w.minds_memory[p["id"]].add(w.day, w.slot, msg); return f"tried to buy a {name}, couldn't afford it", True
    if not terms:
        w.minds_memory[p["id"]].add(w.day, w.slot, f"Nobody sells a {name} on time; it's cash only."); return f"tried to buy a {name} on time (cash only)", True
    d, m, r = terms; down = round(net * d, 2); fin = net - down
    if cash(h) < down:
        w.minds_memory[p["id"]].add(w.day, w.slot, f"We couldn't make the {money(down)} down payment on the {name}."); return f"couldn't make the down payment on a {name}", True
    ok, why = dealer_check(w, h)
    if not ok:
        w.minds_memory[p["id"]].add(w.day, w.slot, f"{seller.capitalize()} wouldn't sell us the {name} on time: {why}."); return f"turned down for time payments on a {name}", True
    draw(w, h, down); _sold(w, at_store, price)
    pay = round(fin * (1 + r * m / 12) / m, 2)
    w.loans.append({"id": f"N{len(w.loans) + 1}", "lender": "store" if at_store else "dealer", "h": h["id"], "who": p["id"], "kind": "installment", "payment": pay,
                    "months_left": m, "rate": r, "collateral": {"type": "item", "item": key}, "missed": 0, "status": "open", "since": w.date_str})
    refresh_debt(w, h); own(w, h, key, model)
    ev_buy(e, p, h, adults, f"bought {'a new ' if key == 'new car' else 'a ' + str(model) + ' ' if key == 'used car' else 'a '}{name if key != 'television' else 'television set'} from {seller} on time: {money(down)} down, ${int(round(pay))} a month for {m} months", key)
    return f"bought a {name} on time ({money(down)} down, ${int(round(pay))}/month)", True


def _sold(w, at_store, price):
    if not at_store: return
    st = w.shops["store"]; o = w.households[st["owner_h"]]; m = price * (1 - DEALER_COST / st["level"])
    o["savings"] += m; w.earned(o, m); st["week"] += m; st["week_sales"] += price


def ev_buy(e, p, h, adults, what, key):
    big = key in CAR_KEYS or key in ("television", "tractor", "piano", "house")
    e.ev("purchase", actors=[p["id"]], text=f"The {plural_s(h['surname'])} {what}.", importance=6 if big else 4, public=big,
         data={"item": key, "said": f"The {plural_s(h['surname'])} got {('a new ' if key == 'new car' else 'a ')}{'car' if key in CAR_KEYS else 'television set' if key == 'television' else key}."})
    for a in adults:
        if a != p["id"]: e.w.minds_memory[a].add(e.w.day, e.w.slot, f"{p['name']} {what}.")


def dealer_check(w, h):
    hist = h.get("earn_hist") or []
    if h["credit"].get("bad_until") and h["credit"]["bad_until"] > w.date_str: return False, "there's a repossession or foreclosure on our record"
    if any(l["h"] == h["id"] and l["status"] == "open" and l["missed"] >= 2 for l in w.loans): return False, "we're already behind on another payment"
    if len(hist) >= 2 and not all(x > 0 for x in hist[-2:]): return False, "there's no steady money coming in"
    if not hist and not any(w.people[i]["alive"] and (w.people[i].get("employer") or w.people[i].get("shop_job")) for i in h["members"]):
        from .world import job_pay
        if not any(w.people[i]["alive"] and job_pay(w.people[i].get("job")) for i in h["members"]): return False, "there's no steady money coming in"
    return (w.rng.random() < 0.92), "the credit man didn't like the look of it"


# ------------------------------------------------------------------ the bank
def classify(purpose):
    t = (purpose or "").lower()
    if re.search(r"repair|roof|fix|porch|paint|plumbing|wiring|rebuild", t): return "repair"
    if re.search(r"business|store|shop|stock|inventory|equipment|cattle|boat|tractor|farm|land|truck|open|start|expand|tools|machine", t): return "business"
    return "personal"


def collateral_value(w, p, h):
    v = 0.0; parts = []
    pl = w.places.get(h["place"])
    if h["home"] == "owned outright" and pl: hv = house_value(w, pl); v += hv; parts.append(("home", hv))
    if h.get("car"): cv = car_value(w, h["car"]); v += cv * 0.7; parts.append(("car", cv))
    for c in w.companies.values():
        if c["owner"] == p["id"] and c["status"] == "open" and c["id"] != "co1" and c["cash"] > 0: v += c["cash"] * 0.5; parts.append(("business", c["cash"]))
        if c["owner"] == p["id"] and c["id"] == "co1" and c["status"] == "open": v += max(0, c["cash"]) * 0.5 + 6000 * P(w); parts.append(("business", c["cash"]))
    v += max(0, h["savings"]) * 0.5 + sum(h.get("deposits", {}).values())
    return v, parts


def county_bank(e, p, amount, purpose):
    """The bank in the county seat: an outside institution with real 1950s standards. Rules first, then the banker's judgment (dice)."""
    ensure(e.w.households[p['household']])
    w = e.w; h = w.households[p["household"]]; kind = classify(purpose)
    inc = income_m(h); owed = payments(w, h); nm = "the bank in the county seat"
    def no(why):
        w.minds_memory[p["id"]].add(w.day, w.slot, f"I asked {nm} for a loan of {money(amount)} ({purpose[:80]}). They turned me down: {why}.")
        e.ev("loan_refused", actors=[p["id"]], text=f"{nm.capitalize()} turns down {p['name']}'s request for a {money(amount)} loan ({kind}): {why}.", importance=5)
        return f"asked the county bank for {money(amount)}: turned down"
    if not amount or amount <= 0: return no("they need to know how much")
    if p["age"] < 21: return no("you have to be 21 to sign a note")
    if h["credit"].get("bad_until") and h["credit"]["bad_until"] > w.date_str: return no("they know about the repossession or foreclosure on our record")
    if any(l["h"] == h["id"] and l["status"] == "open" and l["missed"] >= 1 for l in w.loans): return no("we're behind on a payment we already owe")
    date = w.date_str
    if kind == "repair": cap, months, rate, addon = 2500 * P(w), 36, 0.05, True
    elif kind == "business": cap, months, rate, addon = 0.5 * collateral_value(w, p, h)[0], 36, business_rate(date), False
    else: cap, months, rate, addon = 0.25 * inc * 12, 18, 0.06, True
    if kind == "business" and cap < 100: return no("there's nothing to put up as security")
    if kind != "business" and inc <= 0: return no("there's no steady income to pay it back from")
    if amount > cap: return no(f"the most they'd lend us for that is about {money(cap)}")
    pay = amount * (1 + rate * months / 12) / months if addon else amount * (rate / 12) / (1 - (1 + rate / 12) ** -months)
    base_inc = max(inc, 1)
    if (owed + pay) > 0.35 * base_inc and not (kind == "business" and cash(h) > amount): return no("the payments would be too much for what comes in")
    odds = 0.88
    newcomer = h.get("kind") in ("newcomer", "moved out") and w.day < 365
    if newcomer: odds -= 0.25
    hist = (h.get("earn_hist") or [])[-6:]
    if hist and min(hist) <= 0: odds -= 0.2
    if h["credit"].get("last_missed") and h["credit"]["last_missed"] >= f"{w.date.year - 1}{date[4:]}": odds -= 0.3
    if (owed + pay) > 0.25 * base_inc: odds -= 0.1
    if w.rng.random() > max(0.05, odds): return no("the banker didn't think it was a good risk")
    col = {"type": "none"}
    if kind == "business":
        _v, parts = collateral_value(w, p, h); top = max(parts, key=lambda x: x[1])[0] if parts else "none"
        col = {"type": top}
        if top == "business": col["company"] = next((c["id"] for c in w.companies.values() if c["owner"] == p["id"] and c["status"] == "open"), None)
        if top == "car": col = {"type": "item", "item": h["car"]["key"]}
    elif kind == "repair" and h["home"] in ("owned outright", "mortgaged"): col = {"type": "home"} if h["home"] == "owned outright" else {"type": "none"}
    make_loan(w, h, p, "county", kind, amount, rate, months, col, addon)
    terms = f"{money(amount)} at {rate * 100:.1f}%{' add-on' if addon else ''}, ${int(round(pay))} a month for {months} months"
    w.minds_memory[p["id"]].add(w.day, w.slot, f"{nm.capitalize()} lent me {terms}" + (f", with our {col['type'] if col['type'] != 'item' else col['item']} as security." if col["type"] != "none" else "."))
    e.ev("loan", actors=[p["id"]], text=f"{nm.capitalize()} lends {p['name']} {terms} ({kind}: {purpose[:80]}).", importance=6)
    return f"borrowed {money(amount)} from the county bank"


def make_loan(w, h, p, lender, kind, amount, rate, months, col, addon=False):
    pay = amount * (1 + rate * months / 12) / months if addon else amount * (rate / 12) / (1 - (1 + rate / 12) ** -months)
    l = {"id": f"N{len(w.loans) + 1}", "lender": lender, "h": h["id"], "who": p["id"], "kind": kind, "payment": round(pay, 2), "months_left": months,
         "rate": rate, "collateral": col, "missed": 0, "status": "open", "since": w.date_str, "principal": round(amount, 2)}
    w.loans.append(l); h["savings"] += amount; refresh_debt(w, h)
    return l


def buy_house(e, p, text, amount):
    ensure(e.w.households[p['household']])
    w = e.w; h = w.households[p["household"]]
    if p["age"] < 21: w.minds_memory[p["id"]].add(w.day, w.slot, "You have to be 21 to buy a house."); return "too young to buy a house"
    vac = next((k for k in re.findall(r"home_\w+", text) if w.places.get(k, {}).get("vacant")), None)
    if not vac and h["home"] == "rented" and re.search(r"(we rent|our house|this house|the house|our place|from the landlord|rent)", text): key = h["place"]
    elif vac: key = vac
    else:
        vacant = [k for k, v in w.places.items() if v.get("vacant")]
        msg = "There's no house for sale that we could buy" + (f" (empty houses: {', '.join(w.places[k]['name'] + ' = ' + k for k in vacant)})" if vacant else "") + "."
        if h["home"] == "owned outright": msg = "We already own our home outright."
        w.minds_memory[p["id"]].add(w.day, w.slot, msg); return "looked into buying a house"
    price = round(house_value(w, w.places[key]), 2); adults = [i for i in h["members"] if w.people[i]["alive"] and w.people[i]["age"] >= 18]
    vet = bool(p.get("veteran"))
    if cash(h) >= price and not CREDIT_WORDS.search(text):
        draw(w, h, price)
        if key == h["place"]: h["home"] = "owned outright"; h["monthly_housing"] = 0
        else: w.set_home(h, key, "own", e.ev)
        ev_buy(e, p, h, adults, f"bought {w.places[key]['name']} outright for {money(price)}", "house"); return f"bought a house for {money(price)}"
    down_pct, rate, months = mortgage_terms(w.date_str, vet); down = round(price * down_pct, 2); loan = price - down
    inc = income_m(h); pay = loan * (rate / 12) / (1 - (1 + rate / 12) ** -months)
    nm = "the bank in the county seat"
    def no(why):
        w.minds_memory[p["id"]].add(w.day, w.slot, f"We asked {nm} for a mortgage on {w.places[key]['name']} ({money(price)}). They turned us down: {why}.")
        e.ev("loan_refused", actors=[p["id"]], text=f"{nm.capitalize()} turns down {p['name']}'s mortgage request ({money(price)}): {why}.", importance=5); return "turned down for a mortgage"
    if h["credit"].get("bad_until") and h["credit"]["bad_until"] > w.date_str: return no("there's a repossession or foreclosure on our record")
    if cash(h) < down: return no(f"we'd need {money(down)} down")
    if inc <= 0: return no("there's no steady income")
    if pay > 0.25 * inc: return no("the payments would come to more than a quarter of what we earn")
    if payments(w, h) + pay > 0.35 * inc: return no("with what we already owe, the payments would be too much")
    odds = 0.9 - (0.25 if h.get("kind") in ("newcomer", "moved out") and w.day < 365 else 0)
    if w.rng.random() > odds: return no("the banker didn't think it was a good risk")
    draw(w, h, down)
    l = make_loan(w, h, p, "county", "mortgage", loan, rate, months, {"type": "home"}); h["savings"] -= loan  # the loan goes to the seller, not the family
    if key == h["place"]: h["home"] = "mortgaged"; h["monthly_housing"] = 0
    else: w.set_home(h, key, "mortgage", e.ev); h["monthly_housing"] = 0
    ev_buy(e, p, h, adults, f"bought {w.places[key]['name']} for {money(price)}: {money(down)} down and a {'VA' if vet else 'FHA'} mortgage of ${int(round(l['payment']))} a month for 25 years", "house")
    return f"bought a house with a mortgage ({money(down)} down)"


def local_bank_apply(e, p, bank, amount, purpose):
    """Asking a bank a resident owns: the owner decides (the banker in the room)."""
    ensure(e.w.households[p['household']])
    w = e.w; h = w.households[p["household"]]
    if bank["owner"] == p["id"]: return None
    w.applications.append({"bank": bank["id"], "who": p["id"], "amount": amount, "purpose": purpose[:200], "day": w.day})
    rec = "behind on a payment now" if any(l["h"] == h["id"] and l["status"] == "open" and l["missed"] for l in w.loans) else \
        "a repossession or foreclosure on their record" if h["credit"].get("bad_until") and h["credit"]["bad_until"] > w.date_str else "nothing against them"
    note = (f"{p['name']} has asked {bank['name']} for a loan of {money(amount or 0)} ({purpose[:120]}). What you know as their banker: the household takes in about "
            f"{money(income_m(h))} a month, already pays {money(payments(w, h))} a month on debts, has about {money(max(0, cash(h)))} put by" +
            (f", owns {owns_text(w, h)}" if h.get("owns") else "") + f"; record: {rec}. The bank has {money(bank['cash'])} on hand. "
            f"You can approve_loan (target {p['name']}, amount, detail: rate and months) or deny_loan.")
    e.pending.setdefault(bank["owner"], []).append(note)
    w.minds_memory[p["id"]].add(w.day, w.slot, f"I asked {bank['name']} for a loan of {money(amount or 0)}; {w.name(bank['owner'])} will decide.")
    e.ev("loan_application", actors=[p["id"], bank["owner"]], text=f"{p['name']} applies to {bank['name']} for a {money(amount or 0)} loan ({purpose[:80]}).", importance=5)
    return f"applied to {bank['name']} for a loan"


def decide_application(e, banker, q, yes, amount, detail):
    w = e.w
    bank = next((b for b in local_banks(w) if b["owner"] == banker["id"]), None)
    if not bank or not q: return None
    app = next((a for a in reversed(w.applications) if a["bank"] == bank["id"] and a["who"] == q["id"]), None)
    if not app: w.minds_memory[banker["id"]].add(w.day, w.slot, f"{q['name']} has no loan application with the bank."); return None
    w.applications.remove(app); h = w.households[q["household"]]
    if not yes:
        w.minds_memory[q["id"]].add(w.day, w.slot, f"{bank['name']} turned down my loan. {banker['name']} said no.")
        e.ev("loan_refused", actors=[banker["id"], q["id"]], text=f"{banker['name']} turns down {q['name']}'s loan at {bank['name']}.", importance=6); return "turned down a loan"
    amt = float(amount or app["amount"] or 0)
    d = (detail or "").lower()
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:%|percent)", d); rate = float(m.group(1)) / 100 if m else 0.06
    m = re.search(r"(\d+)\s*(month|year)", d); months = (int(m.group(1)) * (12 if m.group(2) == "year" else 1)) if m else 24
    rate = max(0.0, min(0.36, rate)); months = max(1, min(360, months))
    if amt <= 0 or bank["cash"] < amt:
        w.minds_memory[banker["id"]].add(w.day, w.slot, f"The bank doesn't have {money(amt)} on hand to lend."); return "couldn't fund a loan"
    bank["cash"] -= amt
    l = make_loan(w, h, q, bank["id"], classify(app["purpose"]), amt, rate, months, {"type": "none"})
    for x in (banker, q): w.minds_memory[x["id"]].add(w.day, w.slot, f"{bank['name']} lends {q['name']} {money(amt)} at {rate * 100:.1f}%, ${int(round(l['payment']))} a month for {months} months.")
    e.ev("loan", actors=[banker["id"], q["id"]], text=f"{banker['name']} approves a {money(amt)} loan to {q['name']} at {bank['name']}.", importance=6)
    return f"approved a {money(amt)} loan to {q['name']}"


def deposit(e, p, amount, target, out=False):
    ensure(e.w.households[p['household']])
    w = e.w; h = w.households[p["household"]]
    banks = local_banks(w); tl = (target or "").lower()
    lid = next((b["id"] for b in banks if b["name"].lower() in tl or w.name(b["owner"]).lower() in tl), None) or ("county" if not out else None)
    if out and lid is None: lid = max(h.get("deposits", {}), key=lambda k: h["deposits"][k], default=None)
    if lid is None: w.minds_memory[p["id"]].add(w.day, w.slot, "We don't have any money in the bank."); return "no money in the bank"
    if not amount or amount <= 0: amount = (h["deposits"].get(lid, 0) if out else max(0, h["savings"]))
    name = lender_name(w, lid)
    if out:
        have = h["deposits"].get(lid, 0); amt = min(amount, have)
        if amt <= 0 or not withdraw_from(w, h, lid, amt):
            if lid != "county" and have > 0: bank_fails(e, w.companies[lid], e.ev)  # it couldn't pay out: a run on the bank
            else: w.minds_memory[p["id"]].add(w.day, w.slot, f"There was nothing to take out of {name}.")
            return "tried to withdraw money"
        w.minds_memory[p["id"]].add(w.day, w.slot, f"I took {money(amt)} out of {name}."); return f"withdrew {money(amt)}"
    amt = min(amount, max(0, h["savings"]))
    if amt <= 0: w.minds_memory[p["id"]].add(w.day, w.slot, "There was no cash on hand to put in the bank."); return "had nothing to deposit"
    h["savings"] -= amt; h["deposits"][lid] = h["deposits"].get(lid, 0) + amt
    if lid != "county": w.companies[lid]["cash"] += amt
    w.minds_memory[p["id"]].add(w.day, w.slot, f"I put {money(amt)} in {name}."); return f"deposited {money(amt)}"


# ------------------------------------------------------------------ owners: prices and wages
def set_price(e, p, place, amount, detail):
    w = e.w; k = shop_of(w, p)
    if place in ("store", "diner") and w.shops[place]["owner_h"] == p["household"]: k = place
    if not k: w.minds_memory[p["id"]].add(w.day, w.slot, "I don't run a shop, so I don't set any prices."); return None
    s = w.shops[k]; t = (detail or "").lower()
    try: a = float(amount) if amount is not None else None
    except (TypeError, ValueError): a = None
    if a is None:
        m = re.search(r"(-?\d+(?:\.\d+)?)", t); a = float(m.group(1)) if m else None
    if a is None: return None
    if k == "store":
        old = s["level"]
        if abs(a) > 60: return None
        # amount = percent above (+) or below (-) county-seat prices; "raise/cut by N" moves from where prices are now
        if re.search(r"\b(raise|up)\b", t) and " by " in f" {t} ": new = old + a / 100
        elif re.search(r"\b(cut|lower|reduce|drop)\b", t) and " by " in f" {t} ": new = old - abs(a) / 100
        else: new = 1.0 + a / 100
        cap = law_value(w, "price_cap", "store")
        hi = STORE_LEVEL[1]
        if cap:
            try: hi = min(hi, 1 + float(cap.get("max") or 30) / 100)
            except (TypeError, ValueError): pass
        new = round(max(STORE_LEVEL[0], min(hi, new)), 3); s["level"] = new
        note = f"Prices at the general store are now about {abs(round((new - 1) * 100))}% {'above' if new >= 1 else 'below'} what the county seat charges (they were {abs(round((old - 1) * 100))}% {'above' if old >= 1 else 'below'})."
        txt = f"{p['name']} changes prices at the general store: now about {round((new - 1) * 100):+d}% against the county seat."
    else:
        old = s["meal"] * P(w); price = a if a < 10 else a / 100  # dollars, or cents
        hi = MEAL_RANGE[1] * P(w)
        cap = law_value(w, "price_cap", "diner")
        if cap:
            try: hi = min(hi, float(cap.get("max")))
            except (TypeError, ValueError): pass
        price = max(MEAL_RANGE[0] * P(w), min(hi, price)); s["meal"] = round(price / P(w), 3)
        note = f"A meal at the diner now costs {int(round(price * 100))} cents (it was {int(round(old * 100))} cents)."
        txt = f"{p['name']} sets the price of a meal at the diner at {int(round(price * 100))} cents."
    w.minds_memory[p["id"]].add(w.day, w.slot, note)
    e.ev("price_change", actors=[p["id"]], text=txt, importance=4, place=k, data={"said": note})
    return note.split(" (")[0]


def set_wage(e, p, q, amount, detail):
    """An owner sets pay, for one worker (target) or everyone. amount = dollars a week."""
    w = e.w
    co = next((c for c in w.companies.values() if c["owner"] == p["id"] and c["status"] == "open"), None); k = shop_of(w, p)
    try: a = float(amount)
    except (TypeError, ValueError):
        m = re.search(r"(\d+(?:\.\d+)?)", detail or ""); a = float(m.group(1)) if m else None
    if not a or a <= 0: return None
    staff = (co["employees"] if co else w.shops[k]["staff"] if k else [])
    if not staff: w.minds_memory[p["id"]].add(w.day, w.slot, "Nobody works for me to set wages for."); return None
    who = [q["id"]] if q and q["id"] in staff else list(staff)
    floor = min_wage_day(w, co) * 5.5
    a = max(a, floor)
    firm = co["name"] if co else ("the diner" if k == "diner" else "the general store")
    for i in who:
        x = w.people[i]; before = (x.get("wage_day") or (co["wage_day"] * W(w) if co else SHOP_WAGE_1950 * W(w))) * 5.5
        x["wage_day"] = round(a / 5.5, 3)
        w.minds_memory[i].add(w.day, w.slot, f"{p['name']} set my pay at {firm} at ${a:.2f} a week (it was ${before:.2f}).")
    if not q and co: co["wage_day"] = round(a / 5.5 / W(w), 3)
    for i in staff:  # word gets around the shop floor
        if i not in who and w.rng.random() < 0.5: w.minds_memory[i].add(w.day, w.slot, f"I heard {p['name']} changed pay at {firm}: " + (f"{w.name(who[0])} now gets" if len(who) == 1 else "everyone now gets") + f" ${a:.2f} a week.")
    e.ev("wage_change", actors=[p["id"]] + who, text=f"{p['name']} sets pay at {firm} at ${a:.2f} a week" + (f" for {w.name(who[0])}" if len(who) == 1 else " for everyone") + ".", importance=5)
    return f"set pay at {firm} at ${a:.2f} a week"


def wage_week(w, p):
    """What this person earns a week, as they'd know it (None if they're not paid a wage)."""
    from .world import job_pay
    if p.get("employer") in w.companies:
        c = w.companies[p["employer"]]; return round(max(p.get("wage_day") or c["wage_day"] * W(w), min_wage_day(w, c)) * 5.5, 2)
    if p.get("shop_job"): return round(max(p.get("wage_day") or SHOP_WAGE_1950 * W(w), min_wage_day(w)) * 5.5, 2)
    jp = job_pay(p.get("job"))
    if jp: return round(jp[0] / 52 * W(w), 2)
    return None


def shop_hire(e, owner, q, k, amount=None):
    w = e.w; s = w.shops[k]
    if q["id"] in s["staff"] or q["household"] == s["owner_h"] or q["age"] < 14: return None
    if q.get("employer") in w.companies and q["id"] in w.companies[q["employer"]]["employees"]: w.companies[q["employer"]]["employees"].remove(q["id"])
    if q.get("shop_job") and q["id"] in w.shops[q["shop_job"]]["staff"]: w.shops[q["shop_job"]]["staff"].remove(q["id"])
    q["employer"] = None; q["shop_job"] = k; s["staff"].append(q["id"])
    try: wk = float(amount) if amount else None
    except (TypeError, ValueError): wk = None
    q["wage_day"] = round((wk / 5.5) if wk and wk > 0 else SHOP_WAGE_1950 * W(w), 3)
    q["wage_day"] = max(q["wage_day"], min_wage_day(w))
    q["job"] = "works at the diner" if k == "diner" else "works at the general store"
    w.minds_memory[q["id"]].add(w.day, w.slot, f"{owner['name']} hired me at {('the diner' if k == 'diner' else 'the general store')} for ${q['wage_day'] * 5.5:.2f} a week.")
    e.ev("hired", actors=[owner["id"], q["id"]], text=f"{owner['name']} hires {q['name']} at {('the diner' if k == 'diner' else 'the general store')}.", importance=6, public=True)
    return f"hired {q['name']}"


def shop_leave(w, q):
    k = q.pop("shop_job", None)
    if k and q["id"] in w.shops[k]["staff"]: w.shops[k]["staff"].remove(q["id"])
    q.pop("wage_day", None)


# ------------------------------------------------------------------ what people notice each week (Sunday)
ADS_FOR = ("television", "refrigerator", "washing machine", "new car", "used car", "vacuum cleaner", "radio", "record player", "freezer", "electric range", "furniture", "sewing machine")


def weekly(e, ev):
    w = e.w
    # owners see their own books
    st = w.shops["store"]
    for p in shop_runners(w, "store"):
        lost = [w.households[i]["surname"] for i in st.get("last_custom", []) if i not in st["custom"] and i in w.households and w.households[i].get("groceries_at") != "store"]
        e.pending.setdefault(p["id"], []).append(f"This past week at the general store: about {money(st['week_sales'])} in sales; after what the goods cost you, about {money(st['week'])} is yours. "
                                                  f"{len(st['custom'])} household{'s' if len(st['custom']) != 1 else ''} bought groceries from you." +
                                                  (f" The {', '.join(plural_s(x) for x in lost)} have been buying their groceries in the county seat instead." if lost else ""))
    st["last_custom"] = list(st["custom"]); st["custom"] = []; st["week"] = 0.0; st["week_sales"] = 0.0
    dn = w.shops["diner"]
    for p in shop_runners(w, "diner"):
        e.pending.setdefault(p["id"], []).append(f"This past week at the diner: {dn['meals']} meals for townsfolk at {int(round(dn['meal'] * P(w) * 100))} cents, plus the usual passing trade.")
    dn["meals"] = 0
    for c in w.companies.values():
        if c["status"] == "open" and w.people[c["owner"]]["alive"]:
            pay = sum(wage_week(w, w.people[i]) or 0 for i in c["employees"])
            e.pending.setdefault(c["owner"], []).append(f"The books at {c['name']}: {money(c['cash'])} on hand; payroll about {money(pay)} a week for {len(c['employees'])} hands.")
    # the Sunday paper and the catalog: what's advertised this week (the outside world)
    k = w.rng.choice(ADS_FOR); g = GOODS[k]; price = g[1] * P(w); terms = credit_terms(g[2], w.date_str)
    ad = f"In the Sunday paper: an advertisement for a {'new car' if k == 'new car' else 'good used car' if k == 'used car' else 'television set' if k == 'television' else k}, {money(price)}" + (f", or {money(price * terms[0])} down on easy terms" if terms else "") + "."
    for p in w.living():
        if p["age"] >= 16 and w.rng.random() < 0.6: w.minds_memory[p["id"]].add(w.day, 0, ad)
    w.applications = [a for a in w.applications if w.day - a["day"] <= 21]
    for pid in list(e.pending):
        e.pending[pid] = e.pending[pid][-8:]


def pay_gossip(e, a, b):
    """Two people who work at the same place may know (or let slip) what the other earns."""
    w = e.w
    same = (a.get("employer") and a.get("employer") == b.get("employer")) or (a.get("shop_job") and a.get("shop_job") == b.get("shop_job"))
    if not same: return
    for x, y in ((a, b), (b, a)):
        if w.rng.random() < 0.3:
            ww = wage_week(w, y)
            if ww: w.minds_memory[x["id"]].add(w.day, w.slot, f"{y['name']} makes about ${ww:.0f} a week.")


def snapshot_bits(w, h):
    return {"car_year": (h.get("car") or {}).get("model_year"), "owns": list(h.get("owns", {})), "deposits": round(sum(h.get("deposits", {}).values())), "groceries_at": h.get("groceries_at")}
