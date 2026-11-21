"""nobodystown.com, Phase 1 (Nov 21): the town IS the website. Builds a static site into site/dist from aired data only.
  python3 -m nt.website [--now 2026-12-01T01:00:00Z]     (--now: pretend time, to preview what shows after a premiere)
Main Street homepage (the real renderer's art: welcome sign with the real population, diner, store, post office, town hall,
church, barber), time of day from the visitor's clock, falling snow in winter, buildings are the menu:
  Diner = episodes + Shorts (only what has aired), Town Hall = countdown to the next premiere + how the town works,
  Records Office = the proof (seed, fingerprints, every rule change in plain words), Post Office = the Gazette (coming soon),
  Souvenir stand past the town line = merch (coming soon). Calm mode switch + reduced-motion respected.
NO SPOILERS: titles and links of anything not yet aired are never written into the build (dates only).
Security: only an allowlist of file types goes into dist; strict CSP in _headers; no inline script; no source maps; no secrets.
Edit layer only: reads the official run's snapshots, never changes the town."""
import datetime as dt, html, json, os, shutil, sys
from PIL import Image

ROOT = "/home/claude"
OFF = os.path.join(ROOT, "nobodys_town", "OFFICIAL")
DIST = os.path.join(ROOT, "site", "dist")
ALLOW = {".html", ".css", ".js", ".png", ".jpg", ".svg", ".ttf", ".otf", ".json", ".txt", ".ico", ""}  # "" = _headers / _redirects

# Release schedule (from vidIQ; times UTC). Title/link only render once `at` has passed.
EPISODES = [
    {"label": "1950 · Part 1 · Winter", "at": "2026-12-01T00:00:00Z", "yt": "ND9gkoBJoMQ", "title": "I Left 40 AIs Alone in a 1950s Town. Winter Came.", "season": "winter", "dir": "ep1_p1"},
    {"label": "1950 · Part 2 · Spring", "at": "2026-12-04T00:00:00Z", "yt": "ZaPSh8kkmT4", "title": "Something Is Wrong in This AI Town", "season": "spring", "dir": "ep1_p2"},
]
SHORTS = [
    ("2026-11-23T23:30:00Z", "xE0cIcTJGw8", "AI Husband Has the Flu. His Wife Isn't Having It."),
    ("2026-11-24T23:30:00Z", "uMnnebANMW4", "She Waited 17 Years for Him to Ask Twice. They're Both AI."),
    ("2026-11-25T23:30:00Z", "FS-gYSVgqtU", "He Lost the Diner's Money at Cards. She Found Out. Both AI."),
    ("2026-11-26T23:30:00Z", "Opb6azC5xzU", "She Said Sorry. He Said There's Nothing to Forgive. They're Both AI."),
    ("2026-11-27T23:30:00Z", "Js_EB-CtLpc", "Two AIs Fight Over a Crossword. One Can't Count."),
    ("2026-11-28T23:30:00Z", "aKMAdiYTYoU", "An AI Wife in 1950 Tells Her Husband Her Dream"),
    ("2026-11-29T23:30:00Z", "3GD024MzjRU", "This Whole 1950s Town Is AI. Nobody Scripts a Word."),
]
LINKS = {"YouTube": "https://www.youtube.com/@NobodysTownTV", "TikTok": "https://www.tiktok.com/@nobodystowntv", "Facebook": "https://www.facebook.com/NobodysTown"}
# Building hotspots on the 2940x720 Main Street strip (x0, x1 in strip pixels), measured from the render.
SPOTS = [("sign", "Welcome to Nobody's Town", 110, 306, "#about"), ("diner", "The Diner: episodes", 410, 790, "#diner"),
         ("store", "General Store", 836, 1190, "#store"), ("post", "Post Office: the Gazette", 1230, 1530, "#post"),
         ("hall", "Town Hall: next episode", 1690, 2100, "#hall"), ("church", "Church", 2170, 2500, "#church"),
         ("barber", "Barber shop", 2524, 2770, "#church")]
FONTS = {"poppins.ttf": "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf", "poppins-reg.ttf": "/usr/share/fonts/truetype/google-fonts/Poppins-Regular.ttf",
         "serif.ttf": "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf", "cond.otf": "/usr/share/texmf/fonts/opentype/public/tex-gyre/texgyreheroscn-bold.otf",
         "script.otf": "/usr/share/texmf/fonts/opentype/public/tex-gyre/texgyrechorus-mediumitalic.otf"}

E = html.escape


def utc(s): return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def fmt_ct(s):  # premiere time in US Central (CST in Nov-Mar)
    t = utc(s) - dt.timedelta(hours=6); return t.strftime("%A, %B %-d · %-I:%M %p Central").replace(":00 ", " ")


def first_snap(ep_dir):
    with open(os.path.join(OFF, ep_dir, "snapshots.jsonl")) as f: return json.loads(f.readline())


def art(dist, aired_ep):
    """Main Street at four times of day, from the real renderer, for the latest aired part (or the very first day)."""
    sys.path.insert(0, ROOT)
    from nt import scenes, overlays, brandkit
    ep = aired_ep or EPISODES[0]; d = os.path.join(OFF, ep["dir"])
    gen = json.load(open(os.path.join(d, "world.json"))); s = first_snap(ep["dir"])
    pop = overlays.population(s)
    for tod in ("morning", "midday", "evening", "night"):
        p = scenes.StreetPan(s, gen["seed"], [], tod, "clear", ep["season"], (), setting="main", gen=gen, place="diner", sign_pop=pop, town=gen["name"])
        p.strip.save(os.path.join(dist, "img", f"street_{tod}.png"), optimize=True)
    brandkit.watermark(256, ep["season"]).save(os.path.join(dist, "img", "globe.png"), optimize=True)
    brandkit.watermark(64, ep["season"]).save(os.path.join(dist, "favicon.png"), optimize=True)
    return {"pop": pop, "date": s["date"], "town": gen["name"], "region": gen.get("region", ""), "season": ep["season"]}


def last_aired_date(aired):
    """The last town date covered by an aired part (no part aired yet: nothing)."""
    if not aired: return ""
    with open(os.path.join(OFF, aired[-1]["dir"], "snapshots.jsonl")) as f: last = None
    for l in open(os.path.join(OFF, aired[-1]["dir"], "snapshots.jsonl")): last = l
    return json.loads(last)["date"]


def proof(aired):
    p = json.load(open(os.path.join(OFF, "PROOF.json")))
    upto = last_aired_date(aired); out = []
    for fx in json.load(open(os.path.join(OFF, "fixes.json"))):
        if not upto or (fx.get("town_date") or "9999") > upto: continue  # no spoilers: a change shows once the part it happened in has aired
        out.append({"n": fx["n"], "why": fx.get("reason", "").split("\n")[0], "day": fx.get("town_day"), "date": fx.get("town_date", ""),
                    "from": fx.get("old_fingerprint", "")[:12], "to": fx.get("new_fingerprint", "")[:12]})
    return p, out


def page(now, town, aired, upcoming, shorts, prf, fixes):
    nxt = upcoming[0] if upcoming else None
    ep_cards = "".join(f'<article class="card ep"><a class="thumb" href="https://www.youtube.com/watch?v={E(e["yt"])}" rel="noopener" target="_blank">'
                       f'<img src="https://i.ytimg.com/vi/{E(e["yt"])}/hqdefault.jpg" alt="" loading="lazy" width="480" height="360"></a>'
                       f'<p class="kicker">{E(e["label"])}</p><h3><a href="https://www.youtube.com/watch?v={E(e["yt"])}" rel="noopener" target="_blank">{E(e["title"])}</a></h3></article>' for e in aired)
    if not aired: ep_cards = f'<article class="card"><p class="kicker">Now showing</p><h3>Episode 1 premieres {E(fmt_ct(nxt["at"])) if nxt else "soon"}</h3><p>Pull up a booth. The first episode follows the winter of 1950.</p></article>'
    up_list = "".join(f'<li><b>{E(e["label"])}</b> · {E(fmt_ct(e["at"]))}</li>' for e in upcoming)
    sh = "".join(f'<li><a href="https://www.youtube.com/shorts/{E(v)}" rel="noopener" target="_blank">{E(t)}</a></li>' for _, v, t in shorts)
    fx = "".join(f'<li><b>Change {E(str(f["n"]))}</b>{(" · town day " + E(str(f["day"]))) if f["day"] is not None else ""}: {E(f["why"])}'
                 + (" <code>" + E(f["from"]) + " → " + E(f["to"]) + "</code>" if f["from"] else "") + "</li>" for f in fixes)
    spots = "".join(f'<a class="spot" id="spot-{k}" href="{href}" style="left:{x0 / 2940 * 100:.3f}%;width:{(x1 - x0) / 2940 * 100:.3f}%" aria-label="{E(label)}"><span>{E(label)}</span></a>' for k, label, x0, x1, href in SPOTS)
    links = " · ".join(f'<a href="{u}" rel="noopener" target="_blank">{k}</a>' for k, u in LINKS.items())
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Nobody's Town · an AI town nobody runs</title>
<meta name="description" content="A 1950s American small town where every resident is an AI. Nobody scripts them and nobody steers them. Watch the episodes, check the proof.">
<meta property="og:title" content="Nobody's Town"><meta property="og:description" content="Every resident is an AI. Nobody steers them.">
<meta property="og:image" content="/img/og.png"><meta name="theme-color" content="#1c1838">
<link rel="icon" href="/favicon.png"><link rel="stylesheet" href="/style.css"></head>
<body data-season="{E(town['season'])}" data-next="{E(nxt['at']) if nxt else ''}">
<a class="skip" href="#menu">Skip to the menu</a>
<header class="street" aria-label="Main Street of {E(town['town'])}">
  <div class="viewport" id="viewport" tabindex="0"><div class="strip" id="strip"><img id="streetimg" src="/img/street_evening.png" alt="Main Street, {E(town['town'])}: the welcome sign (population {town['pop']}), the diner, general store, post office, town hall, church and barber" width="2940" height="720">{spots}</div></div>
  <canvas id="snow" aria-hidden="true"></canvas>
  <div class="hello"><p class="script">Welcome to</p><h1>Nobody's Town</h1><p class="tag">Every resident is an AI. Nobody steers them. Not even us.</p>
  <p class="hint">Tap a building to go in · drag to walk the street</p></div>
  <button id="calm" class="calm" aria-pressed="false">Calm mode</button>
</header>
<nav id="menu" aria-label="Town menu"><a href="#diner">The Diner</a><a href="#hall">Town Hall</a><a href="#records">Records Office</a><a href="#post">Post Office</a><a href="#stand">Souvenir Stand</a><a href="#about">About</a></nav>
<main>
<section id="diner" class="bldg"><p class="sign">The Diner</p><h2>Now showing</h2><div class="eps">{ep_cards}</div>
  {f'<h3>Coming up</h3><ul class="plain">{up_list}</ul>' if upcoming else ''}
  {f'<h3>Overheard at the counter (Shorts)</h3><ul class="plain">{sh}</ul>' if shorts else ''}
  <p>Watch every episode free on <a href="{LINKS['YouTube']}" rel="noopener" target="_blank">YouTube</a>. Short scenes on {links}.</p></section>
<section id="hall" class="bldg"><p class="sign">Town Hall</p><h2>The next episode</h2>
  <div class="clock" id="clock" aria-live="polite">{E(fmt_ct(nxt['at'])) if nxt else 'New episodes are on the way.'}</div>
  <h3>How the town works</h3><ul class="plain"><li>Anchor Point was created once, on November 20, 2026, from a single random number. It has never been re-rolled.</li>
  <li>About {town['pop']} people live here. Every one of them is an AI with their own memory, money, family and job.</li>
  <li>They decide for themselves. A referee checks that what they try is possible in 1950; dice decide luck. We never give them topics, goals or nudges.</li>
  <li>We only watch, edit and narrate. Every line of dialogue you hear is exactly what a resident said.</li>
  <li>The rules only change between years, and every change is posted in the Records Office.</li></ul></section>
<section id="records" class="bldg"><p class="sign">Records Office</p><h2>The proof</h2>
  <p>Anyone can check that nobody is steering. The town's starting state and its rule files are fingerprinted; any change shows up here.</p>
  <dl class="proof"><dt>Town seed</dt><dd><code>{E(str(prf['seed']))}</code></dd><dt>World fingerprint</dt><dd><code>{E(prf['world_fingerprint'])}</code></dd>
  <dt>Rules fingerprint at the roll</dt><dd><code>{E(prf['settings_fingerprint'])}</code></dd><dt>Outside minds</dt><dd>About {E(prf.get('outside_minds', '').split('%')[0].split()[-1])}% of the adults run on other companies' AI models, picked by dice, never by us.</dd></dl>
  <h3>Every rule change</h3>{f'<ol class="plain fixes">{fx}</ol>' if fixes else '<p>Each change is posted here once the episode covering it has aired.</p>'}</section>
<section id="post" class="bldg"><p class="sign">U.S. Post Office</p><h2>The Gazette, by mail</h2><p>A short letter from Anchor Point after each episode: what happened, who moved in, who's running for mayor. Sign-up opens soon.</p></section>
<section id="store" class="bldg"><p class="sign">General Store</p><h2>Open for business</h2><p>The general store belongs to the residents. It's their business, run by the town. Our souvenirs are sold elsewhere: look for the stand out on the highway.</p></section>
<section id="stand" class="bldg"><p class="sign">Souvenir Stand · past the town line</p><h2>Coming soon</h2><p>Mugs, pins, the welcome sign and a real snow globe. The stand opens soon, just outside the town line.</p></section>
<section id="church" class="bldg"><p class="sign">Church</p><h2>Sundays in Anchor Point</h2><p>On Sundays the whole town turns up. It's where most of the news gets passed around.</p></section>
<section id="about" class="bldg"><p class="sign">About</p><h2>What is Nobody's Town?</h2>
  <p>Nobody's Town is a documentary series about {E(town['town'])}, a small American town in 1950 where every resident is an AI living an unscripted life. They work, borrow, argue, marry, vote and make their own laws. The town keeps living whether anyone is watching or not, one decade at a time.</p>
  <p><b>About the AI:</b> the residents are AI agents. The narration and voices are AI-generated. The pixel art is drawn by our own code from the town's real records.</p>
  <p><b>Our standards:</b> no sexual content, children are never shown as victims of violence or abuse, no self-harm, nothing is ever decided by race, ethnicity or religion, and romance is for adults only. PG-13 drama, not made for kids.</p></section>
</main>
<footer><img src="/img/globe.png" alt="" width="64" height="64"><p>{links}</p><p>© 2026 Nobody's Town · No cookies, no tracking.</p></footer>
<script src="/app.js" defer></script></body></html>"""


CSS = """@font-face{font-family:Pop;src:url(/fonts/poppins.ttf)}@font-face{font-family:PopR;src:url(/fonts/poppins-reg.ttf)}
@font-face{font-family:Ser;src:url(/fonts/serif.ttf)}@font-face{font-family:Cond;src:url(/fonts/cond.otf)}@font-face{font-family:Scr;src:url(/fonts/script.otf)}
:root{--ink:#26201f;--cream:#f6efdc;--paper:#efe6cc;--red:#d63440;--teal:#40bec4;--butter:#f6d878;--night:#1c1838;--plum:#3a2a4a}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--cream);color:var(--ink);font:17px/1.6 PopR,system-ui,sans-serif}
a{color:#b4282e}.skip{position:absolute;left:-999px}.skip:focus{left:8px;top:8px;background:#fff;padding:8px;z-index:9}
.street{position:relative;height:min(78vh,720px);min-height:380px;background:var(--night);overflow:hidden}
.viewport{position:absolute;inset:0;overflow-x:auto;overflow-y:hidden;cursor:grab;scrollbar-width:none}.viewport::-webkit-scrollbar{display:none}
.strip{position:relative;height:100%;width:max-content}.strip img{height:100%;width:auto;display:block;image-rendering:pixelated}
.spot{position:absolute;top:35%;height:45%;display:block;border-radius:10px;outline:none}
.spot span{position:absolute;left:50%;top:-8px;transform:translate(-50%,-100%);background:var(--ink);color:var(--cream);font:13px Pop,sans-serif;padding:3px 9px;border-radius:7px;white-space:nowrap;opacity:0;transition:opacity .2s}
.spot:hover span,.spot:focus span{opacity:1}.spot:focus{box-shadow:0 0 0 4px var(--butter)}
#snow{position:absolute;inset:0;width:100%;height:100%;pointer-events:none}
.hello{position:absolute;left:50%;top:3%;transform:translateX(-50%);width:min(92%,900px);text-align:center;pointer-events:none;color:var(--cream);text-shadow:3px 3px 0 #000;background:rgba(20,14,34,.55);border-radius:18px;padding:12px 18px 14px}
.hello h1{font:clamp(40px,8vw,92px)/1 Cond,sans-serif;margin:0;letter-spacing:2px;text-transform:uppercase}
.script{font:clamp(26px,4vw,44px)/1 Scr,serif;margin:0;color:var(--butter)}.tag{font:clamp(14px,2vw,20px) Pop,sans-serif;margin:6px 0}
.hint{font:13px PopR,sans-serif;margin:0;text-shadow:none;color:#e9e2f4}
.calm{position:absolute;right:12px;bottom:12px;background:var(--ink);color:var(--cream);border:2px solid var(--cream);border-radius:8px;font:13px Pop,sans-serif;padding:6px 12px;cursor:pointer}
.calm[aria-pressed=true]{background:var(--butter);color:var(--ink)}
nav{position:sticky;top:0;z-index:5;background:var(--ink);display:flex;flex-wrap:wrap;justify-content:center;gap:4px;padding:8px}
nav a{color:var(--cream);text-decoration:none;font:14px Pop,sans-serif;padding:6px 12px;border-radius:6px}nav a:hover,nav a:focus{background:var(--red)}
main{max-width:980px;margin:0 auto;padding:12px 16px 60px}
.bldg{margin:46px 0;scroll-margin-top:70px}.sign{display:inline-block;background:var(--ink);color:var(--butter);font:15px Pop,sans-serif;letter-spacing:2px;text-transform:uppercase;padding:4px 12px;border-radius:6px;margin:0}
h2{font:34px/1.2 Ser,serif;margin:10px 0 14px}h3{font:20px Pop,sans-serif;margin:22px 0 8px}
.card{background:#fffaf0;border:3px solid var(--ink);border-radius:12px;padding:14px;box-shadow:5px 5px 0 var(--ink)}
.eps{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:18px}.ep img{width:100%;height:auto;border-radius:8px;border:2px solid var(--ink)}
.kicker{font:13px Pop,sans-serif;color:var(--red);text-transform:uppercase;letter-spacing:1px;margin:8px 0 0}.ep h3{margin:4px 0}.ep h3 a{color:var(--ink);text-decoration:none}
.plain{padding-left:20px}.plain li{margin:6px 0}.clock{font:clamp(28px,5vw,48px)/1.2 Cond,sans-serif;background:var(--night);color:var(--butter);padding:18px;border-radius:12px;text-align:center;letter-spacing:1px}
.proof{display:grid;grid-template-columns:max-content 1fr;gap:6px 14px}.proof dt{font:14px Pop,sans-serif}.proof dd{margin:0}code{font-size:13px;word-break:break-all;background:#fff;padding:1px 5px;border-radius:4px}
.fixes li{font-size:15px}footer{background:var(--ink);color:var(--cream);text-align:center;padding:28px 16px}footer a{color:var(--butter)}footer p{margin:6px 0}
@media (prefers-reduced-motion:reduce){html{scroll-behavior:auto}}"""

JS = """(function(){
var vp=document.getElementById('viewport'),img=document.getElementById('streetimg'),body=document.body,calmBtn=document.getElementById('calm');
var h=new Date().getHours(),tod=h>=5&&h<10?'morning':h>=10&&h<17?'midday':h>=17&&h<20?'evening':'night';img.src='/img/street_'+tod+'.png';
var calm=window.matchMedia('(prefers-reduced-motion: reduce)').matches;try{if(localStorage.getItem('calm')==='1')calm=true}catch(e){}
function setCalm(v){calm=v;calmBtn.setAttribute('aria-pressed',v?'true':'false');try{localStorage.setItem('calm',v?'1':'0')}catch(e){}}
setCalm(calm);calmBtn.addEventListener('click',function(){setCalm(!calm)});
var dir=1,paused=false,last=0;function drift(t){if(!calm&&!paused){var dt=last?Math.min(50,t-last):16;vp.scrollLeft+=dir*dt*0.025;
if(vp.scrollLeft+vp.clientWidth>=vp.scrollWidth-2)dir=-1;if(vp.scrollLeft<=0)dir=1}last=t;requestAnimationFrame(drift)}requestAnimationFrame(drift);
var down=false,sx=0,sl=0;vp.addEventListener('pointerdown',function(e){down=true;paused=true;sx=e.clientX;sl=vp.scrollLeft});
window.addEventListener('pointerup',function(){down=false;setTimeout(function(){paused=false},4000)});
vp.addEventListener('pointermove',function(e){if(down){vp.scrollLeft=sl-(e.clientX-sx)}});vp.addEventListener('wheel',function(){paused=true;setTimeout(function(){paused=false},4000)},{passive:true});
var cv=document.getElementById('snow'),cx=cv.getContext('2d'),flakes=[],season=body.dataset.season;
var col=season==='winter'?'255,255,255':season==='spring'?'255,190,215':season==='autumn'?'235,150,70':'255,236,140';
function size(){cv.width=cv.clientWidth;cv.height=cv.clientHeight}size();window.addEventListener('resize',size);
for(var i=0;i<(season==='summer'?40:110);i++)flakes.push({x:Math.random(),y:Math.random(),s:2+Math.floor(Math.random()*3)*2,v:.0006+Math.random()*.0012,w:Math.random()*6});
function fall(){cx.clearRect(0,0,cv.width,cv.height);if(!calm){flakes.forEach(function(f){f.y+=f.v;f.w+=.02;if(f.y>1){f.y=-.02;f.x=Math.random()}
cx.fillStyle='rgba('+col+',.85)';cx.fillRect(Math.round(f.x*cv.width+Math.sin(f.w)*6),Math.round(f.y*cv.height),f.s,f.s)})}requestAnimationFrame(fall)}requestAnimationFrame(fall);
var clock=document.getElementById('clock'),next=body.dataset.next;if(next&&clock){var at=Date.parse(next);
(function tick(){var ms=at-Date.now();if(ms<=0){clock.textContent='On now at the Diner. Pull up a booth.';return}
var d=Math.floor(ms/864e5),hh=Math.floor(ms/36e5)%24,mm=Math.floor(ms/6e4)%60,ss=Math.floor(ms/1e3)%60;
clock.textContent=(d?d+' days ':'')+hh+'h '+String(mm).padStart(2,'0')+'m '+String(ss).padStart(2,'0')+'s';setTimeout(tick,1000)})()}
})();"""

HEADERS = """/*
  Content-Security-Policy: default-src 'self'; img-src 'self' https://i.ytimg.com; style-src 'self'; script-src 'self'; font-src 'self'; connect-src 'self'; frame-src https://www.youtube-nocookie.com; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
  Permissions-Policy: camera=(), microphone=(), geolocation=(), interest-cohort=()
  Strict-Transport-Security: max-age=31536000; includeSubDomains
  X-Frame-Options: DENY
"""


def build(now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    if os.path.exists(DIST): shutil.rmtree(DIST)
    for sub in ("img", "fonts"): os.makedirs(os.path.join(DIST, sub))
    aired = [e for e in EPISODES if utc(e["at"]) <= now]; upcoming = [e for e in EPISODES if utc(e["at"]) > now]
    shorts = [s for s in SHORTS if utc(s[0]) <= now]
    town = art(DIST, aired[-1] if aired else None)
    Image.open(os.path.join(DIST, "img", "street_evening.png")).crop((0, 0, 1280, 720)).resize((1200, 630)).save(os.path.join(DIST, "img", "og.png"), optimize=True)
    prf, fixes = proof(aired)
    open(os.path.join(DIST, "index.html"), "w").write(page(now, town, aired, upcoming, shorts, prf, fixes))
    open(os.path.join(DIST, "style.css"), "w").write(CSS); open(os.path.join(DIST, "app.js"), "w").write(JS)
    open(os.path.join(DIST, "_headers"), "w").write(HEADERS)
    open(os.path.join(DIST, "robots.txt"), "w").write("User-agent: *\nAllow: /\n")
    for name, src in FONTS.items(): shutil.copy(src, os.path.join(DIST, "fonts", name))
    check(DIST)
    return {"aired": [e["label"] for e in aired], "upcoming": [e["label"] for e in upcoming], "shorts": len(shorts), "pop": town["pop"]}


def check(dist):
    """Deploy gate: only allowlisted file types, no secrets, nothing unaired."""
    import re
    bad = re.compile(r"(sk-ant-|sk-or-v1-|sk_[a-f0-9]{20}|cfat_|BEGIN [A-Z ]*PRIVATE KEY|r2_secret|\.secrets)")
    files = []
    for dp, _, fs in os.walk(dist):
        for f in fs:
            p = os.path.join(dp, f); ext = os.path.splitext(f)[1].lower()
            if ext not in ALLOW: raise SystemExit(f"DEPLOY GATE: file type not allowed: {p}")
            if ext in (".html", ".css", ".js", ".json", ".txt", ""):
                if bad.search(open(p, errors="ignore").read()): raise SystemExit(f"DEPLOY GATE: secret-like string in {p}")
            files.append(os.path.relpath(p, dist))
    open(os.path.join(dist, "..", "dist_files.txt"), "w").write("\n".join(sorted(files)))


if __name__ == "__main__":
    a = sys.argv[1:]
    print(json.dumps(build(utc(a[a.index("--now") + 1]) if "--now" in a else None), indent=1))
