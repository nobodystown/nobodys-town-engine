"""Static fan website for Nobody's Town, generated from sim data up to the latest PUBLISHED episode (never ahead).
usage: python3 -m nt.site <run_dir> <world.json> <out_dir> --published-day N [--plan episode_N_plan.json] [--poll-url URL]
The Family Board and the prediction poll come from the latest episode plan. The poll needs an outside form service
(the site is static); until one is set with --poll-url, the section shows the question and the families without a vote button."""
import html, json, os, sys, datetime as dt
from .art import appearance, portrait
from . import scenes

CSS = """
:root{--ink:#26201f;--cream:#f6efdc;--paper:#efe6cc;--red:#d63440;--teal:#40bec4;--butter:#f6d878;--mint:#a0dec4;--plum:#2a1f3a}
*{box-sizing:border-box}body{margin:0;background:var(--cream);color:var(--ink);font-family:Georgia,'Times New Roman',serif;line-height:1.5}
header{background:linear-gradient(#1c1838,#5a3250);color:var(--cream);padding:48px 20px 36px;text-align:center;border-bottom:6px solid var(--red)}
header h1{font-size:clamp(40px,8vw,84px);margin:0;letter-spacing:2px;text-shadow:4px 4px 0 #000}
header p{margin:8px 0 0;color:var(--butter);font-family:system-ui,sans-serif;font-weight:700;letter-spacing:3px}
nav{position:sticky;top:0;background:var(--ink);display:flex;gap:4px;justify-content:center;flex-wrap:wrap;padding:8px;z-index:5}
nav a{color:var(--cream);text-decoration:none;font-family:system-ui,sans-serif;font-weight:700;padding:6px 12px;border-radius:6px;font-size:14px}
nav a:hover{background:var(--red)}
main{max-width:1100px;margin:0 auto;padding:24px 16px 80px}
section{margin:40px 0}h2{font-size:34px;border-bottom:3px double var(--ink);padding-bottom:6px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:16px}
.card{background:#fffaf0;border:3px solid var(--ink);border-radius:10px;padding:14px;box-shadow:4px 4px 0 var(--ink)}
.stat .label{font-family:system-ui,sans-serif;font-size:12px;letter-spacing:1px;color:#6e605a;text-transform:uppercase}
.stat .val{font-size:30px;font-weight:700}.up{color:#287846}.down{color:#b4282e}
.res{display:flex;gap:12px;align-items:center}.res img{width:72px;height:72px;image-rendering:pixelated;border:3px solid var(--ink);border-radius:6px}
.res .n{font-weight:700}.res .m{font-family:system-ui,sans-serif;font-size:13px;color:#5a4e4a}
.gone{opacity:.55}.tag{display:inline-block;font-family:system-ui,sans-serif;font-size:11px;font-weight:700;padding:1px 7px;border-radius:9px;background:var(--mint);margin-right:4px}
.tl{border-left:4px solid var(--red);padding-left:16px}.tl div{margin:10px 0}.tl b{font-family:system-ui,sans-serif;font-size:13px;color:var(--red)}
.papers img{width:100%;border:3px solid var(--ink);border-radius:6px}
.proof{font-family:ui-monospace,monospace;font-size:13px;word-break:break-all;background:#fff;border:2px dashed var(--ink);padding:12px;border-radius:8px}
.ep{display:flex;gap:16px;flex-wrap:wrap}.ep .card{flex:1 1 300px}
table.fb{width:100%;border-collapse:collapse;font-family:system-ui,sans-serif}table.fb th{text-align:left;font-size:12px;color:#6e605a;letter-spacing:1px;border-bottom:3px solid var(--ink);padding:6px}
table.fb td{padding:8px 6px;border-bottom:1px solid #d8ccb0}.q{font-size:26px;color:var(--red);text-align:center;margin:18px 0}
.vote{display:inline-block;background:var(--red);color:var(--cream);font-family:system-ui,sans-serif;font-weight:700;padding:10px 22px;border-radius:8px;text-decoration:none}
footer{text-align:center;font-family:system-ui,sans-serif;font-size:13px;color:#6e605a;padding:30px}
svg{width:100%;height:auto}
"""


def spark_svg(vals, color="#d63440", w=300, h=70):
    if len(vals) < 2: return ""
    lo, hi = min(vals), max(vals); rng = max(hi - lo, 1e-6)
    pts = " ".join(f"{i * w / (len(vals) - 1):.1f},{h - 6 - (v - lo) / rng * (h - 12):.1f}" for i, v in enumerate(vals))
    return f'<svg viewBox="0 0 {w} {h}"><polyline points="{pts}" fill="none" stroke="{color}" stroke-width="3"/></svg>'


def family_section(fb, poll_url=None):
    E = html.escape
    if not fb or not fb.get("rows"): return ""
    rows = "".join(f"<tr><td><b>{r['rank']}</b></td><td>The {E(r['surname'])}s</td><td>${r['savings']:,}</td><td>{r['people']}</td><td>{E(', '.join(r['businesses']) or '-')}</td><td>{E(', '.join(r['seats']) or '-')}</td></tr>" for r in fb["rows"])
    vote = f"<p style='text-align:center'><a class=vote href='{E(poll_url)}'>Cast your prediction</a></p>" if poll_url else "<p style='text-align:center'><i>Prediction voting opens soon.</i></p>"
    return (f"<section id=families><h2>The Family Board · end of {E(fb['year_end'])}</h2><table class=fb><tr><th>#</th><th>FAMILY</th><th>SAVINGS</th><th>AT HOME</th><th>BUSINESSES</th><th>IN OFFICE</th></tr>{rows}</table>"
            f"<p style='font-family:system-ui;font-size:13px;color:#6e605a'>Ranked by {E(fb['formula'])}. The residents never see this board.</p>"
            f"<div class=q>{E(fb['question'])}</div>{vote}</section>")


def build(run, gen, out, published_day, episodes=None, plan=None, poll_url=None):
    os.makedirs(os.path.join(out, "img"), exist_ok=True)
    sn = [json.loads(l) for l in open(os.path.join(run, "snapshots.jsonl"))][: published_day + 1]
    ev = [e for e in (json.loads(l) for l in open(os.path.join(run, "events.jsonl"))) if e["day"] <= published_day]
    last = sn[-1]; seed = gen["seed"]; E = html.escape
    people = []
    for pid, p in last["people"].items():
        q = dict(p); q["id"] = int(pid); a = appearance(q, seed)
        portrait(a, "neutral").resize((144, 144), 0).save(os.path.join(out, "img", f"p{pid}.png"))
        people.append((int(pid), p))
    heads = [e for e in ev if e["kind"] in ("election_result", "death", "wedding", "birth", "fired", "fame", "telegram", "measure_vote", "newcomer", "company_closed")
             or (e["kind"] == "town_event" and e["importance"] >= 7)][-12:]
    for e in heads:
        d = dt.date.fromisoformat(e["date"]).strftime("%A, %B %d, %Y").replace(" 0", " ")
        scenes.newspaper(gen["name"], d, e["text"][:80]).resize((640, 360)).save(os.path.join(out, "img", f"g{e['id']}.png"))
    alive = lambda s: [p for p in s["people"].values() if p["alive"] and not p["offtown"]]
    pop = [len(alive(s)) for s in sn]; tre = [s["town"]["treasury"] for s in sn]; co = [s["companies"]["co1"]["cash"] for s in sn]
    hh = sorted(last["households"].values(), key=lambda h: -h["savings"])
    mayor = last["town"]["offices"]["mayor"]; mayor_name = last["people"][str(mayor)]["name"] if mayor else "Vacant"
    def delta(vals, money=False):
        dlt = vals[-1] - vals[0]; cls = "up" if dlt > 0 else "down" if dlt < 0 else ""
        return f'<span class="{cls}">{"▲" if dlt > 0 else "▼" if dlt < 0 else ""} {"$" if money else ""}{abs(int(dlt)):,}</span>' if dlt else ""
    major = [e for e in ev if e["importance"] >= 7 and e["kind"] not in ("conversation", "eavesdrop", "attempt", "household_broke", "company_broke") and not e.get("sensitive") and e.get("public")]
    eps = episodes or [{"n": 1, "title": "Episode 1", "youtube": "", "day": published_day}]
    H = [f"<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>",
         f"<title>Nobody's Town · {E(gen['name'])}</title><meta name=description content=\"An AI town nobody runs. Real residents, real elections, real consequences.\"><style>{CSS}</style></head><body>",
         f"<header><h1>NOBODY'S TOWN</h1><p>AN AI TOWN. NOBODY RUNS IT.</p><p style='color:#fff;letter-spacing:1px;font-weight:400'>{E(gen['name'])} · {E(gen['region'])} · as of {E(last['date'])}</p></header>",
         "<nav><a href=#ledger>Ledger</a><a href=#families>Families</a><a href=#episodes>Episodes</a><a href=#residents>Residents</a><a href=#gazette>Gazette</a><a href=#timeline>Timeline</a><a href=#proof>Proof</a></nav><main>",
         "<section id=ledger><h2>The Ledger</h2><div class=grid>",
         f"<div class='card stat'><div class=label>Population</div><div class=val>{pop[-1]} {delta(pop)}</div>{spark_svg(pop, '#287846')}</div>",
         f"<div class='card stat'><div class=label>Town treasury</div><div class=val>${int(tre[-1]):,} {delta(tre, True)}</div>{spark_svg(tre)}</div>",
         f"<div class='card stat'><div class=label>{E(last['companies']['co1']['name'])}</div><div class=val>${int(co[-1]):,} {delta(co, True)}</div>{spark_svg(co, '#40bec4')}</div>",
         f"<div class='card stat'><div class=label>Mayor</div><div class=val style='font-size:24px'>{E(mayor_name)}</div><div class=label>Council: {E(', '.join(last['people'][str(c)]['name'] for c in last['town']['offices']['council']) or 'empty')}</div></div>",
         f"<div class='card stat'><div class=label>Richest household</div><div class=val style='font-size:24px'>The {E(hh[0]['surname'])} family</div><div>${hh[0]['savings']:,}</div></div>",
         f"<div class='card stat'><div class=label>Poorest household</div><div class=val style='font-size:24px'>The {E(hh[-1]['surname'])} family</div><div>${hh[-1]['savings']:,}</div></div>",
         "</div></section>", family_section((plan or {}).get("family_board"), poll_url),
         "<section id=episodes><h2>Episodes</h2><div class=ep>"]
    for e_ in eps:
        emb = f"<iframe width=100% height=200 src='https://www.youtube.com/embed/{E(e_['youtube'])}' frameborder=0 allowfullscreen></iframe>" if e_.get("youtube") else "<p><i>Video link goes here when published.</i></p>"
        H.append(f"<div class=card><b>Episode {e_['n']}</b><br>{E(e_['title'])}{emb}</div>")
    H.append("</div></section><section id=residents><h2>The Residents</h2><div class=grid>")
    for pid, p in sorted(people, key=lambda x: (not x[1]["alive"], x[1]["household"], -x[1]["age"])):
        status = "Moved away" if p["offtown"] else "" if p["alive"] else "Deceased"
        surname = last["households"][str(p["household"])]["surname"]
        H.append(f"<div class='card res {'gone' if status else ''}'><img src=img/p{pid}.png alt=''><div><div class=n>{E(p['name'])}</div><div class=m>{p['age']} · {E(p['job'] or '—')}</div>"
                 f"<div class=m>The {E(surname)} household</div>{f'<span class=tag>{status}</span>' if status else ''}</div></div>")
    H.append("</div></section><section id=gazette><h2>The Gazette</h2><div class='grid papers'>")
    for e in reversed(heads): H.append(f"<div><img src=img/g{e['id']}.png alt='{E(e['text'][:80])}'></div>")
    H.append("</div></section><section id=timeline><h2>Timeline</h2><div class=tl>")
    for e in major[-40:]: H.append(f"<div><b>{E(e['date'])}</b><br>{E(e['text'])}</div>")
    H.append(f"</div></section><section id=proof><h2>Proof nothing is staged</h2><p>The town was generated once from a random seed. Its starting settings, and the referee's rules, were fingerprinted at launch. Nobody touches the world after that.</p>"
             f"<div class=proof>Generator: {E(gen['version'])}<br>Fingerprint: {E(gen.get('fingerprint', '(published at launch)'))}<br>Rules fingerprint: {E(gen.get('settings_fingerprint', '(published at launch)'))}</div></section>")
    H.append(f"</main><footer>Nobody's Town · data through {E(last['date'])} · updated after each new episode</footer></body></html>")
    open(os.path.join(out, "index.html"), "w").write("\n".join(H))
    return os.path.join(out, "index.html")


if __name__ == "__main__":
    run, world, out = sys.argv[1], sys.argv[2], sys.argv[3]
    pd = int(sys.argv[sys.argv.index("--published-day") + 1]) if "--published-day" in sys.argv else 10 ** 6
    plan = json.load(open(sys.argv[sys.argv.index("--plan") + 1])) if "--plan" in sys.argv else None
    poll = sys.argv[sys.argv.index("--poll-url") + 1] if "--poll-url" in sys.argv else None
    print(build(run, json.load(open(world)), out, pd, plan=plan, poll_url=poll))
