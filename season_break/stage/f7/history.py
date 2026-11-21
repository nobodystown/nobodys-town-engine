"""Real US/world history calendar (background layer). Dates are real; effects are locked rules.
Each entry: (date 'YYYY-MM-DD', headline, effects dict). Effects keys:
  market: {industry_keyword: multiplier}  draft: 'on'/'off'  tv_rate: yearly TV adoption odds  mainland_only: bool"""
EVENTS = [
    ("1950-06-25", "North Korea invades South Korea. President Truman sends American troops.", {"draft": "on"}),
    ("1950-11-26", "Chinese forces enter the war in Korea.", {}),
    ("1951-04-11", "Truman relieves General MacArthur of his command.", {}),
    ("1952-11-04", "Dwight D. Eisenhower is elected President.", {}),
    ("1953-03-05", "Soviet leader Joseph Stalin dies.", {}),
    ("1953-07-27", "Armistice signed. The fighting in Korea ends.", {"draft": "peacetime"}),
    ("1954-02-23", "Mass trials of Dr. Salk's polio vaccine begin with schoolchildren.", {}),
    ("1954-12-02", "The Senate censures Senator Joseph McCarthy.", {}),
    ("1955-04-12", "The Salk polio vaccine is declared safe and effective.", {"polio_vaccine": True}),
    ("1955-07-17", "Disneyland opens in California.", {}),
    ("1956-06-29", "President Eisenhower signs the Federal-Aid Highway Act: 41,000 miles of interstate highways.", {"highway_program": True}),
    ("1956-09-09", "Elvis Presley appears on The Ed Sullivan Show to a record audience.", {}),
    ("1956-11-06", "Eisenhower is re-elected President.", {}),
    ("1957-08-01", "Factory orders fall. Economists warn of a recession.", {"market": {"*": 0.85}}),
    ("1957-10-04", "The Soviet Union launches Sputnik, the first artificial satellite.", {"bomb_shelter_fever": True}),
    ("1958-01-31", "America launches its first satellite, Explorer 1.", {}),
    ("1958-04-15", "The recession bottoms out; factories begin rehiring.", {"market": {"*": 1.0}}),
    ("1959-01-03", "Alaska becomes the 49th state.", {}),
    ("1959-08-21", "Hawaii becomes the 50th state.", {}),
    ("1960-05-01", "An American U-2 spy plane is shot down over the Soviet Union.", {}),
    ("1960-11-08", "John F. Kennedy is elected President.", {}),
    ("1961-04-12", "Soviet cosmonaut Yuri Gagarin becomes the first man in space.", {}),
    ("1962-10-22", "President Kennedy announces Soviet missiles in Cuba. The nation braces.", {"bomb_shelter_fever": True}),
    ("1963-11-22", "President Kennedy is assassinated in Dallas.", {}),
    ("1964-02-09", "The Beatles appear on The Ed Sullivan Show.", {}),
    ("1964-08-07", "Congress passes the Gulf of Tonkin Resolution. The war in Vietnam escalates.", {"draft": "on"}),
    ("1969-07-20", "Apollo 11 lands on the Moon.", {}),
    ("1973-01-27", "Peace accords end American fighting in Vietnam; the draft ends.", {"draft": "off"}),
]
# Everyday news on the radio and in the papers: sports, shows, people, the wider world. Background only (no effects).
CULTURE = [
    ("1950-10-07", "The Yankees sweep the Phillies to win the World Series."),
    ("1951-10-03", "Bobby Thomson's home run wins the pennant for the New York Giants. They're calling it the shot heard round the world."),
    ("1951-10-10", "The Yankees beat the Giants to win the World Series again."),
    ("1951-10-15", "A new comedy called I Love Lucy starts on television."),
    ("1952-01-14", "NBC starts a morning program called Today."),
    ("1952-10-07", "The Yankees beat the Brooklyn Dodgers in seven games to win the World Series."),
    ("1953-01-20", "Dwight Eisenhower is sworn in as President."),
    ("1953-06-02", "Queen Elizabeth is crowned in London, and word comes that two climbers have reached the top of Mount Everest."),
    ("1953-10-05", "The Yankees win the World Series for the fifth year running."),
    ("1954-01-14", "Marilyn Monroe marries Joe DiMaggio in San Francisco."),
    ("1954-05-06", "An Englishman named Roger Bannister runs a mile in under four minutes."),
    ("1954-10-02", "The New York Giants sweep Cleveland in the World Series."),
    ("1954-12-15", "Davy Crockett on the Disneyland show has every child in the country wanting a coonskin cap."),
    ("1955-09-30", "Movie actor James Dean is killed in a car crash in California."),
    ("1955-10-03", "The Mickey Mouse Club starts on television."),
    ("1955-10-04", "The Brooklyn Dodgers finally win the World Series."),
    ("1956-04-19", "Grace Kelly marries Prince Rainier of Monaco."),
    ("1956-10-08", "Don Larsen pitches a perfect game in the World Series."),
    # added Nov 18 (dates checked against Baseball-Reference/SABR and standard references)
    ("1957-10-10", "The Milwaukee Braves beat the Yankees in Game 7 to win the World Series."),
    ("1958-03-24", "Elvis Presley is inducted into the Army."),
    ("1958-10-01", "The new space agency, NASA, opens for business."),
    ("1958-10-09", "The Yankees come back to beat the Braves in seven games and win the World Series."),
    ("1959-02-03", "Buddy Holly, Ritchie Valens and the Big Bopper are killed when their small plane goes down in Iowa."),
    ("1959-03-09", "A new doll called Barbie goes on sale at the toy fair in New York."),
    ("1959-07-24", "Vice President Nixon and Premier Khrushchev argue in a model American kitchen at a fair in Moscow."),
    ("1959-10-08", "The Los Angeles Dodgers win the World Series in their second year out west."),
]

# ---- Seasons are decades (decided Nov 18). Era data is published and fingerprinted before each season starts.
# The town may not run past the last year its era data covers: golive refuses to.
ERA_THROUGH = 1959
# Prices: US Consumer Price Index, all urban consumers, annual average (BLS), as a multiple of 1950 (24.1).
CPI = {1950: 24.1, 1951: 26.0, 1952: 26.5, 1953: 26.7, 1954: 26.9, 1955: 26.8, 1956: 27.2, 1957: 28.1, 1958: 28.9, 1959: 29.1}
# Wages: average hourly earnings of production workers in manufacturing, dollars (BLS), as a multiple of 1950 ($1.44).
WAGES = {1950: 1.44, 1951: 1.56, 1952: 1.65, 1953: 1.74, 1954: 1.78, 1955: 1.86, 1956: 1.95, 1957: 2.05, 1958: 2.11, 1959: 2.19}


def price_index(year):
    """Prices relative to 1950. The engine's base prices (food, rent, a diner meal) are 1950 prices."""
    y = max(min(CPI), min(max(CPI), year)); return CPI[y] / CPI[1950]


def wage_index(year):
    """Wages and what work earns, relative to 1950. Wages rose faster than prices in the 1950s (real pay grew about 2.7% a year)."""
    y = max(min(WAGES), min(max(WAGES), year)); return WAGES[y] / WAGES[1950]
EVENTS = EVENTS + [(d, head, {}) for d, head in CULTURE]

# share of US households with a TV, by year (approximate real adoption curve)
TV_SHARE = {1950: 0.09, 1951: 0.24, 1952: 0.34, 1953: 0.45, 1954: 0.56, 1955: 0.65, 1956: 0.72, 1957: 0.79, 1958: 0.83, 1959: 0.86, 1960: 0.87}
# monthly odds an eligible man (18-26, not married with kids) is drafted
DRAFT_MONTHLY = {"on": 0.012, "peacetime": 0.004, "off": 0.0}
# odds of death per month while serving in an active war (approx: Korea ~1.8M served, ~36K deaths over 37 months)
WAR_DEATH_MONTHLY = 0.0006
WAR_WOUND_MONTHLY = 0.0017
# Real wars active in a date window; service outside these is peacetime.
WARS = [("1950-06-25", "1953-07-27"), ("1964-08-07", "1973-01-27")]


def events_on(date_str): return [e for e in EVENTS if e[0] == date_str]


def draft_state(date_str):
    st = "peacetime" if date_str >= "1948-06-24" else "off"
    for d, _, eff in EVENTS:
        if d <= date_str and "draft" in eff: st = eff["draft"]
    return st


def market_mult(date_str):
    m = 1.0
    for d, _, eff in EVENTS:
        if d <= date_str and "market" in eff: m = eff["market"].get("*", m)
    return m


def at_war(date_str): return any(a <= date_str <= b for a, b in WARS)


# ---- Social Security (Old-Age and Survivors Insurance), 1950s. Era data, published with the season.
# Average monthly benefit in current-payment status, December of each year (SSA Annual Statistical Supplement, table 5.C2).
# 1950 is split: the 1950 amendments raised checks from September 1950 (before that, about $26, the Dec 1949 average).
SS_RETIRED = {1950: 43.86, 1951: 42.14, 1952: 49.25, 1953: 51.10, 1954: 59.14, 1955: 61.90, 1956: 63.09, 1957: 64.58, 1958: 66.35, 1959: 72.78}
SS_RETIRED_EARLY_1950 = 26.00  # Jan-Aug 1950
SS_WIFE = {1950: 23.60, 1951: 22.75, 1952: 26.01, 1953: 27.08, 1954: 31.81, 1955: 33.12, 1956: 33.76, 1957: 34.41, 1958: 35.11, 1959: 38.24}
SS_CHILD = {1950: 17.05, 1951: 13.37, 1952: 14.67, 1953: 15.79, 1954: 18.53, 1955: 20.01, 1956: 20.63, 1957: 21.89, 1958: 22.99, 1959: 27.34}
# Share of people 65+ drawing benefits: 2.1 million of about 12.3 million in mid-1950, 10.5 million of about 16.6 million in mid-1960
# (SSA, Social Security Bulletin v24n1; census). Straight line between them; it was the main reason more of the old had an income.
SS_AGED_SHARE = {y: round(0.17 + (0.63 - 0.17) * (y - 1950) / 10, 3) for y in range(1950, 1961)}
# Share of workers whose job counted toward Social Security: about 60% in 1950; most of the self-employed added in 1951;
# farmers added in 1955 (approximate, from the 1950 and 1954 amendments).
SS_WORKER_COVERED = {1950: 0.60, 1951: 0.75, 1952: 0.75, 1953: 0.75, 1954: 0.75, 1955: 0.90, 1956: 0.90, 1957: 0.90, 1958: 0.90, 1959: 0.90}
# Retirement test: a beneficiary who still works for pay gets no check, until this age (75; 72 from 1955).
def ss_work_exempt_age(year): return 75 if year < 1955 else 72
# Women could draw from 62 starting November 1956 (workers at 80%; widows in full).
SS_WOMEN_62_FROM = "1956-11-01"

# ---- Unemployment insurance (state programs). A laid-off employee of a covered firm draws about half the lost weekly
# wage, up to a state maximum (about $25 a week in 1950, rising with wages), for up to 26 weeks. Quitting disqualifies.
# Covered firms: 8 or more employees, 4 or more from 1956 (Federal Unemployment Tax Act). Farm work and the self-employed are not covered.
UI_WEEKS = 26
UI_MAX_1950 = 25.0
def ui_min_firm(year): return 8 if year < 1956 else 4


def ss_amount(kind, year, month=12):
    """Monthly check for one person, in that year's dollars. kind: retired_man, retired_woman, wife, widow, child, mother."""
    y = max(min(SS_RETIRED), min(max(SS_RETIRED), year))
    base = SS_RETIRED_EARLY_1950 if (year == 1950 and month < 9) else SS_RETIRED[y]
    scale = base / SS_RETIRED[y]
    return round({"retired_man": base * 1.04, "retired_woman": base * 0.80, "wife": SS_WIFE[y] * scale, "widow": base * 0.75,
                  "mother": base * 0.75, "child": SS_CHILD[y] * scale}[kind], 2)
