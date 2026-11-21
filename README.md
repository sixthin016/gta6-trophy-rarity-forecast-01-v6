# GTA VI Trophy Rarity Forecaster — v6

[![make.fun · gta6-trophy-rarity-forecast-01](https://make.fun/badge/gta6-trophy-rarity-forecast-01.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![rank](https://make.fun/badge/gta6-trophy-rarity-forecast-01/sixthin016/gta6-trophy-rarity-forecast-01-v6/rank.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![reward](https://make.fun/badge/gta6-trophy-rarity-forecast-01/sixthin016/gta6-trophy-rarity-forecast-01-v6/reward.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)

Forecasts every Grand Theft Auto VI PlayStation 5 trophy's Exophase earn
rate at 2026-11-26T00:00:00Z as five quantiles per trophy, scored by
pinball loss on the logit scale. Entry for the
[make.fun competition](https://make.fun/competitions/gta6-trophy-rarity-forecast-01)
`gta6-trophy-rarity-forecast-01` ($250, top 20 paid).

## How it works

Exophase refreshes a game's counts in jumps: the page can sit frozen for
hours, then a refresh brings in a batch of newly tracked players who hold
fewer trophies, so every rate is diluted and then climbs again as players
earn. This program handles the two regimes a case's history can show:

* **Flat history** (no movement at all, as in the practice cases): one
  refresh lands at the target, so the median is built in earners/players
  space — the tracked cohort keeps earning at a damped hazard fitted from
  the trophy's own rate and age, players multiply once by the published
  first-refresh multiplier (6.064: 638 → 3,868 players), and the new
  cohort holds each trophy at the rate a player of ~0.2 h effective age
  reaches under that hazard. The spread is a count fan (new earners
  Poisson with a lognormally overdispersed mean, refresh multiplier
  lognormal), which is skewed for rare trophies exactly as counts are.
* **Moving history** (the final case): a backtest-weighted ensemble of a
  saturating curve on logit(rate) in log-time, a log-linear trend of
  log(earners) (immune to the refresh sawtooth), and refresh
  extrapolation from the per-refresh deltas actually observed. Candidate
  weights come from rolling-origin backtests on the case's own history.
  Trophies with (nearly) no earners yet borrow their tier's pooled curve.
  The spread is conformal, from the same backtest's standardised errors.

Standard library only, no network, deterministic (two runs on the same
input are byte-identical).

## Local validation

`tools/backtest_v6.py` scores the entry on four suites built only from
the competition's published numbers (never from any per-trophy answer):

| suite | v6 | v3r | v4 | v5 | persistence |
|---|---|---|---|---|---|
| practice-proxy (13 worlds, aggregate-consistent) | **0.0794** | 0.6998 | 0.1135 | 1.7459 | 1.4034 |
| uniform-factor truths (f = 0.15–0.30) | **0.1455** | 0.7065 | 0.1585 | 1.7492 | 1.4066 |
| v5-style final-like worlds (8) | 0.7960 | 1.5217 | 1.7800 | **0.5797** | 1.5518 |
| v4-style synthetic worlds (practice + final + CV) | **0.1778** | 1.1162 | 0.1955 | 1.1197 | 1.0652 |

Detail: synth-final v6 0.1598 ≈ v4 0.1579; synth-practice v6 0.0856;
at the production-pinned factor f = 0.20, v6 0.0824 vs v4 0.1262 vs v3r
0.7770. v5 wins only the v5-style suite, driven by its flat-refresh
world, whose refresh gives newcomers 70% of the incumbent rate — a
regime the published refresh (newcomers hold almost nothing) does not
have; v6 does not chase it.

## Run

```sh
mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

Reads every `*.in` file in the input dir and writes one `<id>.out` per
case: `{"trophies": [{"id": n, "q": [q05, q25, q50, q75, q95]}, ...]}`.

## Diagnosis: why v5 fell and what v6 fixes

The production board is the practice phase: flat histories whose answers
are the single refresh at the target. The real refresh dilutes rates to
roughly a fifth (newcomers hold almost nothing except the first trophy:
only ~103 new earners across 54 trophies, forced by the published
3,868 players / 4,276 trophies earned). v5's median sat at or above the
last rate (saturating trend + tier-pool shrinkage pulling rare trophies
up) with a symmetric normal fan, and it was tuned on synthetic worlds
whose refresh gives newcomers 70% of the incumbent rate — a regime the
real refresh does not have. It scored 1.85 in production, worse than
persistence (1.51). v6 restores the earners/players dilution model with
the published multiplier and a count fan, and keeps a real trend
ensemble for the moving-history final.
