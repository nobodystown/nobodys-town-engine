"""Nobody's Town: world generator.
Rolls a complete starting town from one seed. Our only input is the pools and odds below.
Run once, publish the output and the fingerprint (sha256 of this file + seed)."""
import json, hashlib, random, sys, math

VERSION = "gen-0.7"
# Decided Nov 18 (Aaron): every town starts on January 1, 1950. One episode = one calendar year; one season = one decade
# (Season 1 = 1950-1959). The start is a format choice, like the 1950s themselves; everything about the town is still rolled.
START_YEAR = 1950

# ---------------------------------------------------------------- pools & odds (the only things we author)
GEOGRAPHY = {  # weight, US regions it can sit in, landmark pool, industries (weight)
    "plains":    (16, ["the Great Plains", "the High Plains", "the prairie Midwest"], ["grain elevator", "water tower", "creek", "windbreak of cottonwoods", "rail siding"],
                  {"grain mill": 4, "farm equipment dealer": 3, "cattle feedlot": 2, "oil drilling outfit": 1}),
    "coast":     (13, ["the Gulf Coast", "the New England coast", "the Pacific Northwest coast", "the Carolina coast"], ["harbor", "lighthouse", "fish market pier", "dunes", "seawall"],
                  {"fish cannery": 4, "boatyard": 3, "shrimp fleet": 2, "salt works": 1}),
    "island":    (8, ["an island off the Atlantic coast", "an island in the Gulf of Mexico", "an island in Puget Sound", "an island in the Great Lakes"],
                  ["ferry landing", "lighthouse", "rocky point", "tide flats", "old fort ruins"], {"fish cannery": 4, "ferry company": 3, "oyster beds": 2, "summer hotel": 1}),
    "mountains": (12, ["the Rocky Mountains", "the Appalachians", "the Sierra foothills", "the Ozarks"], ["mine entrance", "river gorge", "switchback road", "fire lookout", "railroad trestle"],
                  {"coal mine": 3, "silver mine": 2, "lumber mill": 3, "quarry": 2}),
    "desert":    (9, ["the Southwest desert", "the Great Basin", "the high desert of the West"], ["mesa", "dry wash", "railroad water stop", "windmill", "abandoned mine"],
                  {"copper mine": 3, "cattle ranch supply": 3, "railroad depot": 2, "tourist motor court": 2}),
    "lakeside":  (12, ["the Great Lakes shore", "the Minnesota lake country", "a lake in the Adirondacks", "a reservoir in the Tennessee Valley"],
                  ["boat docks", "lake beach", "dam", "island in the lake", "pavilion"], {"boat works": 3, "resort lodge": 3, "ice house": 1, "commercial fishery": 2}),
    "swamp":     (7, ["the Louisiana bayou", "the Florida wetlands", "the Carolina lowcountry"], ["bayou landing", "cypress grove", "levee", "old plantation ruins", "fishing camp"],
                  {"timber company": 3, "shrimp and crawfish dock": 3, "sugar mill": 2}),
    "forest":    (13, ["the North Woods", "the Pacific Northwest timberlands", "the Piney Woods of the South", "the Upper Peninsula"],
                  ["sawmill pond", "logging road", "ranger station", "old-growth stand", "river"], {"lumber mill": 5, "paper mill": 2, "turpentine works": 1}),
}
NAME_A = {"plains": ["Prairie", "Wheat", "Cotton", "Dry", "Red", "Elm", "Buffalo", "Wichita", "Sand", "Long"],
          "coast": ["Salt", "Gull", "Harbor", "Cape", "Driftwood", "Anchor", "Brine", "Tide", "Port", "Shell"],
          "island": ["Gull", "Lantern", "Cutter's", "Fog", "Driftwood", "Heron", "Seal", "Wreck", "Little", "Lone"],
          "mountains": ["Iron", "Pine", "Granite", "Hollow", "Cold", "Silver", "Eagle", "Copper", "High", "Shale"],
          "desert": ["Dust", "Sage", "Mesa", "Dry", "Sun", "Coyote", "Painted", "Juniper", "Alkali", "Rattle"],
          "lakeside": ["Loon", "Clear", "Cedar", "Still", "Birch", "Mirror", "Pike", "Willow", "Blue", "North"],
          "swamp": ["Cypress", "Bayou", "Heron", "Moss", "Black", "Gator", "Cane", "Low", "Mud", "Willow"],
          "forest": ["Timber", "Pine", "Cedar", "Hemlock", "Fern", "Bear", "Spruce", "Elk", "Shadow", "Oak"]}
NAME_B = {"plains": ["Springs", "Crossing", "Junction", "Flats", "Creek", "City", "Bend", "Prairie"],
          "coast": ["Harbor", "Cove", "Landing", "Point", "Haven", "Bay", "Neck"],
          "island": ["Island", "Landing", "Harbor", "Rock", "Cove", "Key"],
          "mountains": ["Gap", "Ridge", "Hollow", "Falls", "Gulch", "Summit", "Run"],
          "desert": ["Wells", "Springs", "Flats", "Junction", "Mesa", "Wash"],
          "lakeside": ["Lake", "Shores", "Point", "Harbor", "Falls", "Narrows"],
          "swamp": ["Landing", "Parish", "Bayou", "Ferry", "Bottom", "Bend"],
          "forest": ["Falls", "Mill", "Hollow", "Grove", "Camp", "Ridge"]}
SURNAMES = ["Abbott", "Alvarez", "Baker", "Banks", "Becker", "Bishop", "Brannigan", "Brooks", "Castillo", "Chen", "Coleman", "Delacroix", "Dunn", "Ellison",
            "Fischer", "Flores", "Fontaine", "Garrison", "Greer", "Halverson", "Hargrove", "Hayes", "Ito", "Jansen", "Jefferson", "Kowalski", "Larkin", "Lindqvist",
            "Lowry", "Maddox", "Moss", "Novak", "O'Brien", "Okafor", "Ortega", "Pace", "Pruitt", "Quinlan", "Reyes", "Romano", "Russo", "Sato", "Schultz", "Sinclair",
            "Stroud", "Tate", "Thibodeaux", "Vance", "Varga", "Walsh", "Whitaker", "Wolfe", "Yates", "Zielinski", "Duval", "Mercer", "Kincaid", "Petrov"]
FIRST = {  # by birth decade, (male, female)
    1870: (["William", "John", "George", "Henry", "Charles", "Frank"], ["Mary", "Anna", "Emma", "Ida", "Minnie", "Clara"]),
    1880: (["James", "Joseph", "Edward", "Walter", "Harry", "Fred"], ["Margaret", "Bertha", "Florence", "Ethel", "Lillian", "Edna"]),
    1890: (["Earl", "Arthur", "Clarence", "Roy", "Ernest", "Herman"], ["Helen", "Ruth", "Mildred", "Hazel", "Gladys", "Pearl"]),
    1900: (["Robert", "Raymond", "Harold", "Leonard", "Floyd", "Howard"], ["Dorothy", "Mabel", "Irene", "Evelyn", "Thelma", "Opal"]),
    1910: (["Walter", "Paul", "Ralph", "Kenneth", "Eugene", "Lloyd"], ["Frances", "Virginia", "Lucille", "Marjorie", "Doris", "Edith"]),
    1920: (["Richard", "Donald", "Jack", "Norman", "Wayne", "Hank"], ["Betty", "Dottie", "Jean", "Shirley", "Peggy", "June"]),
    1930: (["Bobby", "Ronald", "Larry", "Jerry", "Gene", "Billy"], ["Barbara", "Joan", "Patricia", "Carol", "Nancy", "Judy"]),
    1940: (["Michael", "David", "Gary", "Dennis", "Tommy", "Ricky"], ["Linda", "Susan", "Sandra", "Karen", "Donna", "Sharon"]),
    1950: (["Steven", "Mark", "Danny", "Timothy", "Jimmy", "Kevin"], ["Debbie", "Cindy", "Pamela", "Kathy", "Teresa", "Brenda"]),
}
HOUSEHOLD_TYPES = {"married couple with kids": 38, "married couple, kids grown or none": 18, "widow living alone": 9, "widower living alone": 5,
                   "single man": 8, "single woman": 5, "three generations under one roof": 8, "single parent with kids": 5, "boarders / roommates": 4}
TOWN_JOBS = ["diner cook", "store clerk", "schoolteacher", "mechanic", "carpenter", "postmaster", "telephone operator", "barber", "seamstress",
             "town doctor", "nurse", "farmer", "fisherman", "trucker", "bookkeeper", "newspaper editor", "handyman", "preacher's assistant", "salesman"]
EDUCATION = {"grade school": 30, "some high school": 22, "high school": 30, "some college": 10, "college degree": 8}
ADULT_ONLY = {"gambler", "heavy drinker", "teetotaler", "flirt", "hoarder"}
QUIRKS = ["gossip", "penny-pincher", "gambler", "green thumb", "short temper", "dreamer", "teetotaler", "heavy drinker", "storyteller", "show-off",
          "night owl", "hoarder", "know-it-all", "busybody", "practical joker", "worrier", "flirt", "loner", "joiner", "handy with tools",
          "sweet tooth", "liar", "collector of junk", "animal lover", "holds grudges", "forgives easily", "superstitious", "ambitious", "lazy", "nosy"]
SECRETS = ["once wanted to be a singer and never told anyone", "was married once before, briefly, in another state", "is afraid of the water",
           "writes poems nobody has seen", "applied for a job in the city and is waiting to hear back", "is the one who broke the church window years ago",
           "still keeps letters from an old sweetheart", "can't swim", "has been saving for a trip to see the ocean", "fell out with their own brother and never made up",
           "owes money to someone in town", "was engaged to someone else in town long ago", "is not who they say they are (changed their name)",
           "has a child living in another state", "cheated a neighbor in a land deal years ago", "hid money from the bank",
           "secretly can't read well", "was fired from their last job in another town", "is quietly in love with a married neighbor",
           "knows something about the company's founding that would embarrass the owner", "lost everything gambling once",
           "served time in prison before moving here", "lied about their war record", "is planning to leave town", "has a hidden stash of valuables"]
# what people do with their time (period-accurate, rolled; the main source of everyday variety)
INTERESTS_ADULT = ["fishing", "hunting", "baseball on the radio", "the radio dramas", "church choir", "gardening", "tinkering with the truck", "woodworking",
                   "card nights", "checkers at the store", "bowling in the county seat", "dancing", "reading westerns", "reading the paper front to back",
                   "quilting circle", "canning and preserves", "baking for church socials", "sewing", "letter writing", "bird watching", "horseshoes",
                   "the picture show in the county seat", "playing the piano", "the harmonica", "photography", "crossword puzzles", "raising chickens",
                   "fixing radios", "the volunteer fire company", "the Grange meetings", "the VFW post", "the women's club", "Bible study", "trapping",
                   "whittling", "playing guitar", "following the boxing matches", "stamp collecting", "a small vegetable stand", "dogs"]
INTERESTS_YOUTH = ["sandlot baseball", "comic books", "marbles", "fishing at the creek", "jump rope", "radio adventure serials", "bicycles", "the picture show",
                   "Scouts", "collecting baseball cards", "climbing trees", "drawing", "the school play", "catching frogs", "kites", "rock collecting",
                   "a crush nobody knows about", "jacks", "playing cowboys", "the 4-H club", "dancing to records", "hot rods", "football"]
FAITH = {"goes to church every Sunday": 45, "goes to church most Sundays": 20, "goes to church at Christmas and Easter": 18, "doesn't go to church": 12, "keeps a quiet private faith": 5}
GRUDGES = ["a property-line dispute", "an unpaid loan", "a business deal gone bad", "an old insult at a town dance", "a stolen sweetheart",
           "a dog that killed chickens", "a lost election years ago", "an inheritance fight"]


def wchoice(r, d): ks = list(d); return r.choices(ks, [d[k] if not isinstance(d[k], tuple) else d[k][0] for k in ks])[0]


SURNAME_SET = set(SURNAMES)


def first_name(r, birth_year, male, taken=None):
    """Era-appropriate first name that nobody else in town has (and that is never a surname). Falls back to the nearest decades."""
    taken = taken if taken is not None else set()
    dec = max(1870, min(1950, birth_year // 10 * 10))
    for off in (0, -10, 10, -20, 20, -30, 30, -40, 40, -50, 50, -60, 60, -70, 70, -80, 80):
        pool = [n for n in FIRST.get(dec + off, ([], []))[0 if male else 1] if n not in taken and n not in SURNAME_SET]
        if pool: n = r.choice(pool); taken.add(n); return n
    raise RuntimeError("ran out of unique first names")


def traits(r):  # Big Five, realistic spread (normal, mean 50)
    t = {k: max(1, min(99, int(r.gauss(50, 18)))) for k in ["openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"]}
    return t


def person(r, surname, age, male, start_year, role="", taken=None):
    by = start_year - age
    p = {"name": f"{first_name(r, by, male, taken)} {surname}", "age": age, "sex": "male" if male else "female", "born": by, "role": role,
         "traits": traits(r), "quirks": r.sample([q for q in QUIRKS if age >= 16 or q not in ADULT_ONLY], 2 if r.random() < 0.7 else 3),
         "education": wchoice(r, EDUCATION) if age >= 19 else ("in school" if age >= 6 and (age < 16 or r.random() < 0.7) else "dropped out" if age >= 6 else "too young"),
         "health": r.choices(["good", "fair", "frail", "bad back", "weak heart", "poor eyesight"], [55, 20, 6, 8, 5, 6])[0] if age > 40 else
                   r.choices(["good", "fair", "asthma"], [80, 15, 5])[0],
         "veteran": (male and 1895 <= by <= 1927 and r.random() < 0.6), "job": None, "secret": None, "money_personal": 0,
         "interests": r.sample(INTERESTS_ADULT if age >= 18 else INTERESTS_YOUTH, r.choice([2, 2, 3])), "faith": wchoice(r, FAITH)}
    if any(k in i for i in p["interests"] for k in ("church", "Bible")): p["faith"] = "goes to church every Sunday"  # consistency
    if p["age"] >= 65: p["health"] = r.choices(["good", "fair", "frail", "weak heart", "bad back"], [25, 30, 25, 10, 10])[0]
    return p


def add_kids(r, m, sn, n, max_age, start_year, taken):
    ages = []
    for _ in range(n):
        if ages and r.random() < 0.03: ag = ages[-1]  # twins, rare
        else:
            ag = r.randint(0, max(0, max_age))
            tries = 0
            while any(abs(ag - x) < 1 for x in ages) and tries < 20: ag = r.randint(0, max(0, max_age)); tries += 1
        ages.append(ag)
    for ag in sorted(ages, reverse=True):
        m.append(person(r, sn, ag, r.random() < 0.5, start_year, "child", taken))


# 1950 census, women 15+: about 66% married, 20% never married, 12% widowed, 2% divorced. With only 6-10 households the dice
# can roll a town of nothing but couples (Copper Ridge did: 7 of 7). So the household mix is re-rolled until the share of adults
# who are NOT married lands in a realistic band (22-42%). Still pure dice inside the band; no household is placed by hand.
UNMARRIED = {"married couple with kids": (0, 2), "married couple, kids grown or none": (0, 2), "widow living alone": (1, 1), "widower living alone": (1, 1),
             "single man": (1, 1), "single woman": (1, 1), "three generations under one roof": (1, 3), "single parent with kids": (1, 1), "boarders / roommates": (2.5, 2.5)}


def roll_kinds(r, n):
    for _ in range(500):
        ks = [wchoice(r, HOUSEHOLD_TYPES) for _ in range(n)]
        un = sum(UNMARRIED[k][0] for k in ks); ad = sum(UNMARRIED[k][1] for k in ks)
        if 0.22 <= un / ad <= 0.42: return ks
    return ks


def generate(seed):
    r = random.Random(seed)
    geo = wchoice(r, GEOGRAPHY); wt, regions, lmk, inds = GEOGRAPHY[geo]
    r.randint(1950, 1954)  # (the old rolled start year: still drawn so every seed rolls the same town as before)
    start_year = START_YEAR
    region = r.choice(regions); name = f"{r.choice(NAME_A[geo])} {r.choice(NAME_B[geo])}"; r.choice(["spring", "summer", "autumn", "winter"])  # old rolled start season, kept for the same reason
    town = {"seed": seed, "version": VERSION, "geography": geo, "region": region,
            "name": name, "start": {"year": start_year, "season": "winter", "date": f"{start_year}-01-01"},
            "landmarks": r.sample(lmk, 3)}
    used = set(); households = []; taken = set()  # taken: every first name in town
    kinds = roll_kinds(r, r.randint(13, 18))  # 40-60 people (Nov 18: bigger towns, so real-rate life is not too thin)
    for h, kind in enumerate(kinds):
        sn = r.choice([s for s in SURNAMES if s not in used]); used.add(sn)
        m = []
        if kind == "married couple with kids":
            a = r.randint(26, 50); m += [person(r, sn, a, True, start_year, "husband", taken), person(r, sn, max(20, a + r.randint(-6, 3)), False, start_year, "wife", taken)]
            add_kids(r, m, sn, r.choices([1, 2, 3, 4, 5], [25, 35, 22, 12, 6])[0], min(17, a - 20), start_year, taken)
        elif kind == "married couple, kids grown or none":
            a = r.randint(24, 72); m += [person(r, sn, a, True, start_year, "husband", taken), person(r, sn, max(20, a + r.randint(-6, 3)), False, start_year, "wife", taken)]
        elif kind in ("widow living alone", "widower living alone"):
            m.append(person(r, sn, r.randint(55, 84), kind.startswith("widower"), start_year, "widower" if kind.startswith("widower") else "widow", taken))
        elif kind in ("single man", "single woman"):
            m.append(person(r, sn, r.randint(19, 60), kind == "single man", start_year, "single", taken))
        elif kind == "three generations under one roof":
            g = r.randint(66, 85); a = r.randint(32, 48)
            m += [person(r, sn, g, r.random() < 0.4, start_year, "grandparent", taken), person(r, sn, a, True, start_year, "husband", taken),
                  person(r, sn, max(20, a + r.randint(-5, 2)), False, start_year, "wife", taken)]
            add_kids(r, m, sn, r.randint(1, 4), min(16, a - 20), start_year, taken)
        elif kind == "single parent with kids":
            a = r.randint(24, 45); m.append(person(r, sn, a, r.random() < 0.25, start_year, "parent", taken))
            add_kids(r, m, sn, r.randint(1, 3), min(17, a - 18), start_year, taken)
        else:
            for _ in range(r.randint(2, 3)):
                s2 = r.choice([s for s in SURNAMES if s not in used]); used.add(s2); m.append(person(r, s2, r.randint(18, 40), r.random() < 0.6, start_year, "boarder", taken))
        wealth = int(math.exp(r.gauss(math.log(900), 1.0)))  # lognormal: most modest, a few rich, a few broke
        households.append({"id": h + 1, "surname": sn, "kind": kind, "members": m, "savings": wealth, "debt": int(r.random() < 0.35) * r.randint(50, 3000),
                           "home": r.choice(["owned outright", "mortgaged", "mortgaged", "rented"])})
    # the company: industry by geography, owner = a random household weighted by wealth
    ind = wchoice(r, inds)
    owner = r.choices(households, [math.sqrt(h["savings"]) for h in households])[0]
    owner["savings"] = int(owner["savings"] * r.uniform(3, 8)); owner["home"] = r.choice(["owned outright", "owned outright", "mortgaged"])
    town["company"] = {"name": f"{owner['surname']} {ind.title()}", "industry": ind, "owner_household": owner["id"],
                       "cash": r.randint(2000, 15000), "employees_needed": r.randint(5, 14)}
    # who owns the diner and the store
    # only a household with a working-age adult who can actually run it (Nov 18 fix: Cane Ferry's store went to an 80-year-old widower,
    # so nobody ran it and residents invented a storekeeper)
    others = [h for h in households if h is not owner]
    can = lambda h, roles: any(18 <= p["age"] < 70 and p["role"] in roles for p in h["members"])
    d_pool = [h for h in others if can(h, ("wife", "husband", "widow", "single", "parent"))] or others
    diner = r.choice(d_pool)
    s_pool = [h for h in others if h is not diner and can(h, ("husband", "single", "widower", "parent"))] or [h for h in others if h is not diner] or others
    store = r.choice(s_pool)
    town["diner_owner_household"], town["store_owner_household"] = diner["id"], store["id"]
    # jobs for working-age adults
    adults = [p for h in households for p in h["members"] if 18 <= p["age"] < 70]
    for h in households:
        for p in h["members"]:
            if not (18 <= p["age"] < 70): continue
            if h is owner and p["role"] in ("husband", "parent", "single", "widower", "widow"): p["job"] = f"owner, {town['company']['name']}"; continue
            if h is diner and p["role"] in ("wife", "husband", "widow", "single", "parent") and not any(q["job"] and "diner" in q["job"] for q in h["members"]): p["job"] = "runs the diner"; continue
            if h is store and p["role"] in ("husband", "single", "widower", "parent") and not any(q["job"] and "store" in q["job"] for q in h["members"]): p["job"] = "runs the general store"; continue
            roll = r.random()
            if p["age"] >= 63 and r.random() < 0.6: p["job"] = "retired"; continue
            if p["sex"] == "female" and p["role"] == "wife" and (roll < 0.62 or h is owner): p["job"] = "homemaker"
            elif roll < 0.62: p["job"] = f"works at {town['company']['name']}"
            elif roll < 0.9:
                if p["sex"] == "female" and r.random() < 0.75: p["job"] = r.choice(["schoolteacher", "nurse", "telephone operator", "seamstress", "store clerk", "bookkeeper", "diner cook", "postmaster"])
                else: p["job"] = r.choice(TOWN_JOBS)
            else: p["job"] = "homemaker" if p["role"] == "wife" else "out of work"
    # the law: in a small 1950s town, a part-time town marshal (or a county deputy who lives in town). Dice picks who, from able-bodied
    # adults not running the mine, diner or store; it's a real resident with a mind like anyone else.
    cands = [p for h in households if h not in (owner, diner, store) for p in h["members"] if 24 <= p["age"] <= 62 and p["role"] not in ("boarder",)]
    cands = [p for p in cands if p["sex"] == "male"] or cands  # period-accurate: almost always a man
    if cands:
        law = r.choice(cands); law["job"] = r.choice(["town marshal", "town marshal", "deputy sheriff"])
    # hidden histories: secrets, grudges, debts between families, old romances
    everyone = [p for h in households for p in h["members"] if p["age"] >= 18]
    for p in r.sample(everyone, min(len(everyone), r.randint(4, 8))): p["secret"] = r.choice(SECRETS)
    links = []
    for _ in range(r.randint(4, 7)):
        a, b = r.sample(households, 2)
        kind = wchoice(r, {"friendship": 26, "neighbors who help each other": 14, "church friends": 10, "old romance": 12, "rivalry": 12, "grudge": 12, "business partnership gone quiet": 7, "debt": 7})
        link = {"between": [a["id"], b["id"]], "kind": kind}
        if kind == "grudge": link["over"] = r.choice(GRUDGES); link["years"] = r.randint(1, 30)
        if kind == "debt": link["amount"] = r.randint(40, 2500); link["owed_by"] = a["id"]
        links.append(link)
    # the sitting government: the town existed before we arrived, so it already has a mayor and council (rolled),
    # elected some time in the last two years. One officeholder per household. Odds lean toward older, outgoing,
    # dependable people and (period-accurate for 1950s small towns) toward men, but anyone 25+ can hold a seat.
    elig = [(hi, mi) for hi, h in enumerate(households) for mi, p in enumerate(h["members"]) if p["age"] >= 25]
    def office_odds(x):
        p = households[x[0]]["members"][x[1]]
        return (1 + (p["traits"]["extraversion"] + p["traits"]["conscientiousness"]) / 60 + (0.6 if p["age"] >= 40 else 0)) * (2.5 if p["sex"] == "male" else 1)
    picks, pool = [], list(elig)
    while len(picks) < 4 and pool:
        c = r.choices(pool, [office_odds(x) for x in pool])[0]; picks.append(c); pool = [x for x in pool if x[0] != c[0]]
    ref = lambda x: [households[x[0]]["id"], x[1]]
    town["government"] = {"mayor": ref(picks[0]) if picks else None, "council": [ref(x) for x in picks[1:]], "elected_days_ago": r.randint(1, 729)}
    pop = sum(len(h["members"]) for h in households)
    town["treasury"] = int(pop * math.exp(r.gauss(math.log(80), 0.45)))  # a working small-town treasury, not a crisis
    town["households"] = households; town["history_links"] = links
    town["population"] = sum(len(h["members"]) for h in households)
    return town


def fingerprint(seed):
    src = open(__file__, "rb").read()
    return hashlib.sha256(src + str(seed).encode()).hexdigest()


if __name__ == "__main__":
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else random.SystemRandom().randrange(10 ** 12)
    t = generate(seed); t["fingerprint"] = fingerprint(seed)
    json.dump(t, open(f"/home/claude/town/world_{seed}.json", "w"), indent=1)
    print(f"{t['name']} — {t['geography']}, {t['region']} — {t['start']['season']} {t['start']['year']} — pop {t['population']} — seed {seed}")
    print("company:", t["company"]["name"], "| landmarks:", ", ".join(t["landmarks"]))
    for h in t["households"]:
        print(f"  #{h['id']} {h['surname']} ({h['kind']}), ${h['savings']} saved, ${h['debt']} debt, home {h['home']}")
        for p in h["members"]:
            print(f"     {p['name']}, {p['age']}, {p['role']}, {p['job'] or '-'}, {p['education']}, {'/'.join(p['quirks'])}" + (f"  SECRET: {p['secret']}" if p['secret'] else "") + ("  [vet]" if p['veteran'] else ""))
    for l in t["history_links"]: print("  link:", l)
    print("fingerprint", t["fingerprint"])
