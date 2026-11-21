"""Baby names by birth year (era-appropriate pools; extends past 1950 as the town ages).
No two people in town ever share a first name, and no first name is ever a surname."""
from .generator import FIRST, SURNAME_SET
LATER = {1960: (["Brian", "Jeffrey", "Scott", "Eric", "Keith", "Todd"], ["Lisa", "Kimberly", "Tammy", "Michelle", "Laura", "Julie"]),
         1970: (["Jason", "Chad", "Shawn", "Travis", "Jeremy", "Ryan"], ["Jennifer", "Amy", "Heather", "Melissa", "Angela", "Stacy"]),
         1980: (["Joshua", "Justin", "Brandon", "Kyle", "Derek", "Adam"], ["Jessica", "Ashley", "Amanda", "Sarah", "Brittany", "Megan"])}
ALL = {**FIRST, **LATER}


def baby_name(rng, year, male, taken=()):
    dec = max(1870, min(1980, year // 10 * 10))
    for off in (0, -10, 10, -20, 20, -30, 30, -40, 40, -50, 50, -60, 60, -70, 70, -80, 80, -90, 90, -100, 100, -110, 110):
        pool = [n for n in ALL.get(dec + off, ([], []))[0 if male else 1] if n not in taken and n not in SURNAME_SET]
        if pool: return rng.choice(pool)
    raise RuntimeError("ran out of unique first names")
