"""Everyday doings that need no judge (approved by Aaron, Nov 18 11:29pm: "the ref needs a smaller role").

In the Hollow Summit test most referee calls were ordinary life: writing a letter, going to the revival tent, sitting in on the
council, Sunday church, walking over to look at a neighbor's place, selling a few notions, checking traps, a quiet evening.
Each call was a chance for the model to invent a fact. These are now plain rules, using only what the town really holds:
the referee is left for what is genuinely new or uncertain. Anything that doesn't clearly match goes to the referee as before.

Also here: the town FACT SHEET the referee and the world step see on every call (offices and when the council meets, who runs
and works at each business, the lawman, the church), so they have nothing to guess at.
"""
import re
from . import history, econ

HARD = re.compile(r"\b(steal|break|burn|threaten|fight|hit|bribe|hide|search|follow|spy|sneak|forge|poison)\b", re.I)
WORK_VERBS = re.compile(r"\b(fix|repair|patch|build|nail|shingle|tear|dig|plow|shovel|chop|haul|carry|steal|take|borrow|break|burn|confront|accuse|threaten|fight|hit|kiss|propose|court|hire|fire|buy|bribe|hide|search|follow|spy)\b", re.I)
SERIOUS_LETTER = re.compile(r"sheriff|police|newspaper|editor|governor|senator|congress|company|bank|lawyer|attorney|court|accus|threat|anonymous|complain|apply|application|order|catalog|insurance|government|draft board|recruit|blackmail|confess", re.I)
SMALL_GOODS = re.compile(r"spool|notion|thread|button|egg|pie|cake|bread|vegetable|preserve|jam|jelly|canned|firewood|kindling|fish|pelt|fur|quilt|household goods|sample case|needle|pins|ribbon|seed|honey|butter|milk|cream|apples|berries|sewing", re.I)
LEISURE = re.compile(r"\b(read|reading|play (a few tunes|tunes|the piano|piano|guitar|the guitar|harmonica|cards|checkers|solitaire)|listen(ing)? to the radio|knit|knitting|crochet|whittl|rest by|sit by the (stove|fire)|crossword|write in (my|a) (diary|journal))", re.I)
STOP = {"the", "near", "over", "with", "from", "into", "evening", "service", "free", "town", "walk", "look", "some", "little", "bit", "about"}


def _first(w, d):
    return [q for q in w.living() if q["name"].lower() in d or (len(q["name"].split()[0]) > 3 and re.search(r"\b" + re.escape(q["name"].split()[0].lower()) + r"\b", d))]


def _event_place(w, d):
    for k, pl in w.places.items():
        if pl.get("kind") != "event": continue
        words = {x for x in re.findall(r"[a-z]{4,}", pl["name"].lower()) if x not in STOP}
        if words and any(re.search(r"\b" + x + r"\b", d) for x in words): return k
    return None


def _home_of(w, d):
    for h in w.households.values():
        sn = h["surname"].lower()
        if re.search(r"\bthe " + re.escape(sn) + r"(s|es)?('s?)? (place|house|home|farm|cabin|porch|yard)\b", d) and h.get("place") in w.places: return h
    return None


def _landmark(w, d):
    for k, pl in w.places.items():
        if not k.startswith("lm_"): continue
        words = {x for x in re.findall(r"[a-z]{4,}", pl["name"].lower()) if x not in STOP | {"outside", "open", "country"}}
        if words and all(re.search(r"\b" + x + r"\b", d) for x in words): return k
    return None


def match(w, p, do, detail):
    """Which everyday rule handles this, or None (then the referee rules on it). Pure: changes nothing."""
    d = (detail or "").lower(); do = (do or "").lower()
    if not d: return None
    if do == "write_letter" or re.search(r"\b(write|writes|writing|finish|post|mail|seal)\b[^.]*\bletters?\b", d):
        return None if SERIOUS_LETTER.search(d) or HARD.search(d) else "letter"
    if do == "sell" or d.startswith("sell "):
        return "sell_small" if SMALL_GOODS.search(d) and not _first(w, d) else None
    if re.search(r"council (meeting|session)|town meeting|meeting at the town hall|the council meeting", d) and not HARD.search(d): return "council"
    if not HARD.search(d) and not re.search(r"\b(climb|ladder|hammer|nail|carry|haul)\b", d) and re.search(r"\b(ask|asks|tell|talk (to|with|over)|speak (to|with)|have a word|press|sit down with|visit with|go see|see what)\b", d) \
            and len([q for q in _first(w, d) if q["id"] != p["id"]]) == 1:
        return "talk"  # mostly a conversation with one neighbor: it becomes a real conversation, not a ruling
    if WORK_VERBS.search(d): return None
    if _event_place(w, d) and re.search(r"\b(go|goes|walk|attend|look in|stop|head|sit|slip|visit|hear|listen)\b", d): return "event"
    if re.search(r"\b(church|sunday service|morning service|worship|prayer meeting|hear the sermon)\b", d) and not _event_place(w, d): return "church"
    if re.search(r"\b(trap|traps|trapline|snares?)\b", d): return "traps"
    if _home_of(w, d) and re.search(r"\b(walk|go|head|stop|drive|look|check|see|visit|call on)\b", d) and not _first(w, d.replace(_home_of(w, d)["surname"].lower(), "")):
        return "visit_home"
    if _landmark(w, d) and re.search(r"\b(walk|go|head|hike|climb up|stroll|look|sit|watch)\b", d) and not _first(w, d): return "walk"
    if LEISURE.search(d) and not _first(w, d): return "leisure"
    return None


def run(e, p, do, detail, amt, kind):
    """Carry out an everyday rule. Returns a short 'what I did' line."""
    w = e.w; d = (detail or "").lower(); h = w.households[p["household"]]; mem = w.minds_memory[p["id"]]
    if kind == "talk":
        q = [x for x in _first(w, d) if x["id"] != p["id"]][0]
        if q["offtown"] or not q["alive"]: mem.add(w.day, w.slot, f"I wanted to talk to {q['name']} but they're not around."); return None
        if w.slot == 3 and q["location"] != w.households[q["household"]]["place"]: return None
        p["location"] = q["location"]
        return ("talk", q)
    if kind == "letter":
        to = [q for q in _first(w, d) if q["id"] != p["id"]]
        stamp = round(0.03 * history.price_index(w.date.year), 2); h["savings"] -= stamp  # first-class postage was 3 cents
        if to:
            q = to[0]; w.minds_memory[q["id"]].add(w.day, w.slot, f"A letter came from {p['name']}: {detail[:200]}")
            mem.add(w.day, w.slot, f"I wrote a letter to {q['name']} and sent it."); e.ev("letter", actors=[p["id"], q["id"]], text=f"{p['name']} writes to {q['name']}.", importance=3)
            return f"wrote a letter to {q['name']}"
        mem.add(w.day, w.slot, f"I wrote a letter and put it in the mail: {detail[:160]}"); return "wrote a letter"
    if kind == "council":
        t = w.town; off = t["offices"]; meets = w.date.weekday() == t["charter"].get("meeting_weekday", 1) and w.slot >= 2
        day = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][t["charter"].get("meeting_weekday", 1)]
        if not meets:
            mem.add(w.day, w.slot, f"There's no council meeting now; the council meets {day} evenings at the town hall."); return "went to the town hall; no meeting"
        p["location"] = "town_hall"
        for pid in [off["mayor"]] + off["council"]:
            if pid and pid != p["id"] and w.people[pid]["alive"]: w.minds_memory[pid].add(w.day, w.slot, f"At the council meeting, {p['name']} spoke up: {detail[:220]}")
        mem.add(w.day, w.slot, "I spoke at the council meeting. Nothing is voted on unless someone proposes a measure.")
        e.ev("public_comment", actors=[p["id"]], text=f"{p['name']} speaks at the council meeting: {detail[:160]}", importance=4, place="town_hall")
        return "spoke at the council meeting"
    if kind == "event":
        k = _event_place(w, d); pl = w.places[k]; p["location"] = k
        if p.get("went_to") != k + str(w.day):
            p["went_to"] = k + str(w.day); price = float(pl.get("price") or 0)
            if price and econ.cash(h) >= price: econ.draw(w, h, price)
        mem.add(w.day, w.slot, f"I went to {pl['name']}."); return f"went to {pl['name']}"
    if kind == "church":
        if w.date.weekday() != 6:
            mem.add(w.day, w.slot, "There's no church service today; services are on Sunday."); return "found no service today"
        if w.slot >= 2: mem.add(w.day, w.slot, "The Sunday service was in the morning."); return "missed the Sunday service"
        p["location"] = "church"; mem.add(w.day, w.slot, "I went to the Sunday service at the church."); return "went to church"
    if kind == "sell_small":
        here = p["location"]; luck = e.r.random()
        pay = 0.0 if luck < 0.2 else round(e.r.uniform(0.25, 3.5) * history.wage_index(w.date.year), 2)
        h["savings"] += pay; w.earned(h, pay)
        mem.add(w.day, w.slot, f"I tried selling {detail[5:90] if d.startswith('sell ') else detail[:90]}" + (f" and took in ${pay:.2f}." if pay else ", but nobody bought anything."))
        if here == "store":
            for q in econ.shop_runners(w, "store"):
                if q["id"] != p["id"] and q["location"] == "store": w.minds_memory[q["id"]].add(w.day, w.slot, f"I saw {p['name']} selling things to customers in my store.")
        return f"sold a little (${pay:.2f})" if pay else "tried to sell a little; no sales"
    if kind == "traps":
        s = w.season; pay = 0.0
        if s in ("winter", "autumn") and e.r.random() < 0.45: pay = round(e.r.uniform(0.75, 4.0) * history.price_index(w.date.year), 2)  # a mink or muskrat pelt
        h["savings"] += pay; w.earned(h, pay); p["location"] = "lm_woods"; w.discovery_roll(p, "explore", e.ev)
        mem.add(w.day, w.slot, f"I checked my traps" + (f" and got a pelt worth about ${pay:.2f}." if pay else " and found them empty."))
        return f"checked the traps (${pay:.2f})" if pay else "checked the traps; empty"
    if kind == "visit_home":
        hh = _home_of(w, d); pl = w.places[hh["place"]]; p["location"] = hh["place"]
        seen = []
        if pl.get("burned"): seen.append(f"the {hh['surname']} house has burned down")
        elif hh.get("repairs_needed", 0) > 0: seen.append(f"the {hh['surname']} house is damaged; fixing it would take about ${int(hh['repairs_needed'])}")
        else: seen.append(f"the {hh['surname']} place looks in fair shape")
        home = [w.people[i]["name"] for i in hh["members"] if w.people[i]["alive"] and w.people[i]["location"] == hh["place"] and i != p["id"]]
        mem.add(w.day, w.slot, f"I went over to the {hh['surname']} place: " + "; ".join(seen) + "." + (f" {', '.join(home)} {'was' if len(home) == 1 else 'were'} home." if home else " Nobody was home."))
        return f"went over to the {hh['surname']} place"
    if kind == "walk":
        k = _landmark(w, d); p["location"] = k; p["needs"]["energy"] -= 6; w.discovery_roll(p, "explore", e.ev)
        mem.add(w.day, w.slot, f"I walked out to {w.places[k]['name']}."); return f"walked out to {w.places[k]['name']}"
    if kind == "leisure":
        p["needs"]["energy"] = min(100, p["needs"]["energy"] + 6); p["needs"]["mood"] = min(100, p["needs"]["mood"] + 3)
        mem.add(w.day, w.slot, f"A quiet spell at home: {detail[:120]}"); return "a quiet spell at home"
    return None


def fact_sheet(w):
    """What anyone in town knows as plain fact. Shown to the referee and the world step on every call."""
    t = w.town; off = t["offices"]; nm = lambda i: w.people[i]["name"] if i and i in w.people else None
    day = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][t["charter"].get("meeting_weekday", 1)]
    lines = [f"GOVERNMENT: mayor {nm(off['mayor']) or 'none'}; council: {', '.join(filter(None, (nm(i) for i in off['council']))) or 'none'}. "
             f"The council meets {day} evenings at the town hall; nothing becomes town law unless a measure is proposed and the council votes it through."]
    biz = []
    for k, label in (("store", "the general store"), ("diner", "the diner")):
        run_by = [q["name"] for q in econ.shop_runners(w, k)]
        staff = [w.people[i]["name"] for i in w.shops[k]["staff"] if w.people[i]["alive"]]
        biz.append(f"{label}: run by {', '.join(run_by) or 'nobody right now'}" + (f"; works there: {', '.join(staff)}" if staff else "; no hired help"))
    for c in w.companies.values():
        hands = [w.people[i]["name"] for i in c["employees"] if w.people[i]["alive"]]
        biz.append(f"{c['name']} ({c['status']}): owner {nm(c['owner'])}; {len(hands)} hands" + (f" ({', '.join(hands[:8])})" if hands else ""))
    lines.append("BUSINESSES (nobody else works at them): " + " | ".join(biz))
    law = [q["name"] + f" ({q['job']})" for q in w.living() if any(x in (q.get("job") or "") for x in ("marshal", "sheriff"))]
    lines.append(f"THE LAW: {', '.join(law) or 'none in town; the county sheriff, from the county seat'}.")
    clergy = [q["name"] for q in w.living() if re.search(r"preacher|minister|pastor|priest|reverend", q.get("job") or "", re.I)]
    lines.append("CHURCH: the church holds services Sunday mornings; " + (f"church people in town: {', '.join(clergy)}." if clergy else "no minister lives in town."))
    return "\n".join(lines)
