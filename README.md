# Nobody's Town

**An AI town. Nobody runs it.**

Nobody's Town is a small American town whose residents are all AI. Each resident has a temperament, a household, a job, a memory, secrets and old grudges, and makes their own choices every day. Nobody steers what happens: not the people who built it, and not the viewers. We watch, edit and narrate it for the YouTube channel [@nobodystowntv](https://www.youtube.com/@nobodystowntv).

The town starts on **January 1, 1950**. One episode covers one calendar year, and one season covers one decade. The world moves into the 1960s, 70s, 80s and 90s, and residents adopt new things (or don't) as they choose.

## How it stays honest

- **One town, rolled once.** The town is generated from a single random seed and is never re-rolled.
- **Locked rules.** Every file that decides what happens in town (see `RULE_FILES` in `nt/golive.py`) is fingerprinted at the official roll. The run script refuses to continue if any of them change afterward.
- **The dice decide.** When a resident tries something, a neutral referee lists realistic outcomes with real-life odds, and a die roll picks one. The model estimates; it never chooses.
- **Real history, real money.** Radio news follows real dates. Prices follow the Consumer Price Index and wages follow real factory pay, year by year. Every job pays at period rates; nobody's fortune is capped, and nobody is rescued.
- **Era data by season.** History, prices, wages and technology for each new decade are published and fingerprinted before that season starts. The run script will not go past the last published year.

The proof (seed, world fingerprint, rules fingerprint) is published at launch in `proof/`.

Episode material (scripts, subtitles, cast lists) and operations notes are kept private until they air.

## Layout

| Path | What it is |
|---|---|
| `nt/generator.py`, `nt/names.py` | Rolls a town from one seed |
| `nt/world.py`, `nt/history.py` | Weather, disasters, economy and pay, homes, illness, births, deaths, real history, era data |
| `nt/fate.py` | The world step: real-rate events, options with odds, dice; ongoing matters ("threads") |
| `nt/minds.py`, `nt/engine.py` | Resident minds, memory, plans, conversations, elections, the council |
| `nt/referee.py` | Neutral judge of free-form attempts |
| `nt/llm.py` | API client, cost meter, budget cap |
| `nt/audit.py`, `nt/test_year.py`, `nt/ab_frame.py` | Audits and test runners (test towns only) |
| `nt/editor.py`, `nt/assemble.py`, `nt/mix.py`, `nt/shorts.py` | Episode editor, rendering, final mix, Shorts |
| `nt/art.py`, `nt/scenes.py`, `nt/places.py`, `nt/cutaways.py`, `nt/overlays.py`, `nt/ambience.py`, `nt/voices.py` | Pixel art, scenes, on-screen boards, sound beds, voice casting |
| `nt/site.py` | The fan site (Ledger, Family Board, residents, timeline, proof) |
| `nt/brand*.py`, `nt/globe.py` | Brand kit |
| `nt/golive.py` | `ping`, `smoke`, `roll` (official town, once), `season <n>`, `episode <n>` |

## Running

Python 3 with Pillow, numpy, scipy and ffmpeg. Run from the folder that contains `nt/`:

```
python3 -m nt.golive ping            # check the API key and credits
python3 -m nt.test_year 4242 --mock  # a free mock test town
```

The Anthropic API key is read from `~/.secrets/anthropic_key`. It is never stored in this repository.
