"""Sound beds (approved Nov 18): the town's own sounds under the picture, synthesized in code (no stock clips, nothing to license).
Every bed follows what the record says about the shot on screen: the day's real weather (rain, snow, a storm), the time of day,
the season, the place (a street, Main Street, the works, the open country, a kitchen, the diner, the store) and the geography
(water lapping on an island or the coast). Nothing is added for drama: a quiet day sounds quiet.
Beds sit low (about -26 dBFS) so voices and music go on top. Cards (title, Ledger, Family Board, end screen) get near-silence.
  bed_for_timeline(T, gen) -> float32 stereo array at RATE
  mux(mp4_in, wav, mp4_out)  -> the video with the bed as its audio track"""
import subprocess, wave
import numpy as np
from scipy.signal import butter, lfilter

RATE = 44100
LEVEL = 0.05  # overall bed level (about -26 dBFS RMS once layers are summed)


def _filt(x, lo=None, hi=None, order=2):
    if lo and hi: b, a = butter(order, [lo / (RATE / 2), hi / (RATE / 2)], "band")
    elif hi: b, a = butter(order, hi / (RATE / 2), "low")
    else: b, a = butter(order, lo / (RATE / 2), "high")
    return lfilter(b, a, x)


def _norm(x):
    m = np.sqrt(np.mean(x ** 2)) or 1.0
    return x / m


class Gen:
    """All layers for one shot, seeded so the same shot always sounds the same."""
    def __init__(self, n, seed):
        self.n = n; self.r = np.random.default_rng(seed); self.t = np.arange(n) / RATE

    def noise(self): return self.r.standard_normal(self.n)

    def wind(self, strength=1.0):
        x = _norm(_filt(self.noise(), hi=400)); swell = 0.6 + 0.4 * np.sin(2 * np.pi * self.t / (5 + self.r.random() * 4) + self.r.random() * 6)
        return x * swell * 0.35 * strength

    def rain(self, heavy=False):
        hiss = _norm(_filt(self.noise(), lo=800, hi=9000)) * (0.5 if heavy else 0.3)
        drops = np.zeros(self.n); k = int(self.n / RATE * (220 if heavy else 90))
        idx = self.r.integers(0, self.n, k)
        for i in idx:
            L = min(300, self.n - i); env = np.exp(-np.arange(L) / 40); drops[i:i + L] += env * self.r.standard_normal(L) * (0.6 + self.r.random())
        return hiss + _filt(drops, lo=1500) * 0.25

    def thunder(self):
        x = np.zeros(self.n)
        if self.n > RATE * 2 and self.r.random() < 0.6:
            s = int(self.r.random() * (self.n - RATE * 2)); L = min(int(RATE * 2.5), self.n - s)
            env = np.exp(-np.arange(L) / (RATE * 0.6)) * (1 - np.exp(-np.arange(L) / 800))
            x[s:s + L] = _norm(_filt(self.r.standard_normal(L), hi=120)) * env * 0.9
        return x

    def waves(self):
        x = _norm(_filt(self.noise(), lo=150, hi=1500)); period = 6 + self.r.random() * 3
        env = np.clip(np.sin(2 * np.pi * self.t / period + self.r.random() * 6), 0, 1) ** 2
        return x * (0.12 + 0.4 * env)

    def birds(self, count_per_s=0.6):
        x = np.zeros(self.n); k = int(self.n / RATE * count_per_s)
        for _ in range(k):
            s = int(self.r.random() * max(1, self.n - RATE)); f0 = 2600 + self.r.random() * 2200; notes = self.r.integers(2, 6)
            for j in range(notes):
                L = int(RATE * (0.05 + self.r.random() * 0.06)); st = s + j * int(RATE * 0.09)
                if st + L >= self.n: break
                tt = np.arange(L) / RATE; f = f0 * (1 + 0.25 * np.sin(np.pi * tt / tt[-1])) * (1 + 0.1 * j)
                x[st:st + L] += np.sin(2 * np.pi * np.cumsum(f) / RATE) * np.hanning(L) * 0.25
        return x

    def crickets(self):
        car = np.sin(2 * np.pi * 4300 * self.t); pulse = (np.sin(2 * np.pi * 14 * self.t) > 0.3) * (np.sin(2 * np.pi * 0.9 * self.t + 1) > -0.2)
        return car * pulse * 0.06

    def gulls(self):
        x = np.zeros(self.n)
        if self.r.random() < 0.5 and self.n > RATE:
            s = int(self.r.random() * (self.n - RATE)); L = int(RATE * 0.5); tt = np.arange(L) / RATE
            f = 1400 - 700 * tt / tt[-1]; x[s:s + L] = np.sign(np.sin(2 * np.pi * np.cumsum(f) / RATE)) * np.hanning(L) * 0.06
        return _filt(x, hi=3000)

    def room(self, hum=0.0):
        x = _norm(_filt(self.noise(), hi=250)) * 0.08
        if hum: x += np.sin(2 * np.pi * 60 * self.t) * 0.02 * hum + np.sin(2 * np.pi * 120 * self.t) * 0.01 * hum
        return x

    def clock(self):
        x = np.zeros(self.n)
        for s in range(int(RATE * self.r.random()), self.n - 400, RATE):
            x[s:s + 400] += self.r.standard_normal(400) * np.exp(-np.arange(400) / 60) * 0.25
        return _filt(x, lo=2000)

    def murmur(self):  # a few voices across the room: formant-band noise, no words
        x = _norm(_filt(self.noise(), lo=250, hi=1200)); env = 0.5 + 0.5 * np.abs(np.sin(2 * np.pi * self.t * 1.7)) * np.abs(np.sin(2 * np.pi * self.t * 0.43 + 1))
        return x * env * 0.12

    def clinks(self, per_s=0.5):
        x = np.zeros(self.n); k = int(self.n / RATE * per_s)
        for s in self.r.integers(0, max(1, self.n - 3000), k):
            L = 3000; tt = np.arange(L) / RATE; f = 2200 + self.r.random() * 2500
            x[s:s + L] += np.sin(2 * np.pi * f * tt) * np.exp(-tt * 40) * 0.15
        return x

    def machinery(self):
        thump = (np.sin(2 * np.pi * 1.5 * self.t) > 0.85) * 1.0
        return _norm(_filt(self.noise(), hi=300)) * 0.15 + _filt(thump * self.noise(), hi=200) * 0.3 + np.sin(2 * np.pi * 50 * self.t) * 0.03

    def fire(self):
        x = _norm(_filt(self.noise(), hi=900)) * 0.25; k = int(self.n / RATE * 25)
        for s in self.r.integers(0, max(1, self.n - 200), k): x[s:s + 200] += self.r.standard_normal(200) * np.exp(-np.arange(200) / 25) * 0.7
        return x

    def bells(self):
        x = np.zeros(self.n)
        for j, s in enumerate(range(0, self.n - RATE, int(RATE * 0.8))):
            L = min(int(RATE * 2.5), self.n - s); tt = np.arange(L) / RATE; f = [523, 659, 784, 659][j % 4]
            x[s:s + L] += (np.sin(2 * np.pi * f * tt) + 0.4 * np.sin(2 * np.pi * f * 2.76 * tt)) * np.exp(-tt * 1.6) * 0.12
        return x

    def engine(self):
        return _norm(_filt(self.noise(), hi=180)) * 0.12 + np.sin(2 * np.pi * 38 * self.t) * 0.04


WET = {"coast", "island", "lakeside", "swamp"}


def layers_for(sh, gen, g):
    """The sound of one shot, from what the record says about it."""
    k = sh["kind"]; geo = gen.get("geography", "")
    if k in ("title", "ledger", "family", "endscreen", "meet", "newspaper"):
        return g.room() * 0.25
    snap = sh.get("snap") or {}
    sky = sh.get("weather") or (snap.get("weather") or {}).get("sky", "clear")
    tod = sh.get("tod", "midday"); season = sh.get("season") or snap.get("season", "summer")
    storm = (snap.get("weather") or {}).get("disaster") is not None and sky in ("rain", "storm")
    if k == "interior":
        place = sh.get("place", "home")
        x = g.room(hum=1.0 if place in ("diner", "store") else 0.3)
        if place == "home": x = x + g.clock() * 0.6
        if place == "diner": x = x + g.murmur() + g.clinks(0.7)
        if place == "store": x = x + g.murmur() * 0.5 + g.clinks(0.15)
        if place == "company": x = x + g.machinery()
        if place == "town_hall": x = x + g.murmur() * 0.3
        if sky in ("rain", "storm"): x = x + _filt(g.rain(storm), hi=1200) * 0.35   # rain on the roof, heard from inside
        return x
    if k == "cutaway":
        cut = sh.get("cut")
        extra = {"fire": g.fire(), "wedding": g.bells(), "storm": g.wind(2.0) + g.rain(True) + g.thunder(), "hearse": g.rain(False) + g.engine() * 0.7,
                 "truck_in": g.engine(), "bus_in": g.engine(), "bus_out": g.engine(), "works": g.machinery(), "tent": g.murmur() * 1.5}.get(cut)
        base = g.wind(0.5) + (g.birds(0.3) if tod in ("morning", "midday") and season != "winter" else 0)
        return base + (extra if extra is not None else 0)
    # outdoors: street pans, Main Street, the works, the country, the overview and the time-lapse
    x = g.wind(1.4 if sky == "snow" else 0.8)
    if sky in ("rain", "storm"): x = x + g.rain(storm) + (g.thunder() if storm else 0)
    elif tod in ("morning", "midday") and season in ("spring", "summer", "autumn"): x = x + g.birds(0.8 if season == "spring" else 0.5)
    if tod in ("evening", "night") and season in ("summer", "autumn") and sky not in ("rain", "storm", "snow"): x = x + g.crickets()
    if geo in WET and sh.get("setting") != "works": x = x + g.waves() * (1.0 if sh.get("setting") == "country" else 0.5) + (g.gulls() if geo in ("coast", "island") and tod != "night" else 0)
    if sh.get("setting") == "main": x = x + g.murmur() * 0.4
    if sh.get("setting") == "works": x = x + g.machinery() * 0.8
    return x


def bed_for_timeline(T, gen, seed=0):
    total = int(T.t * RATE) + RATE; out = np.zeros(total); fade = int(0.35 * RATE)
    for i, sh in enumerate(T.shots):
        s = int(sh["start"] * RATE); n = int(sh["dur"] * RATE) + fade
        n = min(n, total - s)
        if n <= 0: continue
        x = np.asarray(layers_for(sh, gen, Gen(n, (seed * 1000003 + i * 7919) & 0xFFFFFFFF)), dtype=float)
        if x.ndim == 0: x = np.zeros(n)
        env = np.ones(n); f = min(fade, n // 2); env[:f] = np.linspace(0, 1, f); env[-f:] = np.linspace(1, 0, f)
        out[s:s + n] += x * env
    out = out * LEVEL
    peak = np.max(np.abs(out)) or 1.0
    if peak > 0.6: out *= 0.6 / peak  # never clips, stays a bed
    st = np.stack([out, np.roll(out, 220)], axis=1)  # a touch of width
    return st.astype(np.float32)


def write_wav(x, path):
    pcm = (np.clip(x, -1, 1) * 32767).astype(np.int16)
    with wave.open(path, "wb") as w: w.setnchannels(2); w.setsampwidth(2); w.setframerate(RATE); w.writeframes(pcm.tobytes())


def mux(mp4_in, wav, mp4_out):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mp4_in, "-i", wav, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest", mp4_out], check=True)
