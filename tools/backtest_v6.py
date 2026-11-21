#!/usr/bin/env python3
"""Backtest harness for the v6 forecaster (own code, written fresh).

Scores v6 head-to-head against v3r, v4, v5 and the house persistence
baseline on four suites, all built only from the competition's published
numbers (never from any per-trophy answer, which is sealed):

  (a) practice-proxy worlds -- the real p00/p01 cases with answers built
      from the published aggregates (3,868 players, 4,276 trophies
      earned in the answering read): 13 worlds (uniform / earliness /
      lognormal / 10 random valid truths).
  (b) uniform-factor truths -- the real p00/p01 cases with every
      non-100 rate scaled by one factor f in {0.15, 0.20, 0.25, 0.30}.
      The production board pins the real factor near 0.20: persistence
      scores 1.51 there, v5 scores 1.85 there, v2 scored 0.139 there.
  (c) v5-style final-like worlds -- 60 h history, 108 h horizon,
      Weibull / loglogistic / delayed / flat-refresh x 2 seeds.
  (d) v4-style synthetic worlds -- cohort simulation fitted to the
      launch-night snapshot: practice-like (3 h / 1.5 h), final-like
      (48 h / 108 h), expanding CV (24/36/48 h cuts), 3 families.

v6 is scored in-process (imported); v3r/v4/v5/persistence via subprocess
or direct computation. Usage: python3 tools/backtest_v6.py [proxy|factor|
final5|synth|all] [tune] -- 'tune' grid-searches the flat-path knobs
(NEW_AGE_H, GROWTH, S_MULT, S_ALPHA) on suites (a)+(b) only.
"""

import importlib.util
import json
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, "/home/hatch/workspace/makefun/gta6-trophy-rarity-forecast-01-v4/tools")
import worlds as W4

import main as v6

V3R = Path("/home/hatch/workspace/makefun/gta6-trophy-rarity-forecast-01-v3r/main.py")
V4 = Path("/home/hatch/workspace/makefun/gta6-trophy-rarity-forecast-01-v4/main.py")
V5 = Path("/home/hatch/workspace/makefun/gta6-trophy-rarity-forecast-01-v5/main.py")
KIT_IN = Path("/home/hatch/workspace/makefun/gta6-trophy-rarity-forecast-01-kit-v27"
              "/gta6-trophy-rarity-forecast-01-kit/input")

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.6448536269514722, -0.6744897501960817, 0.0,
     0.6744897501960817, 1.6448536269514722]


def clamp_pct(x):
    return min(99.99, max(0.01, x))


def logit_pct(p):
    p = clamp_pct(p) / 100.0
    return math.log(p / (1.0 - p))


def inv_logit_pct(lg):
    if lg >= 0:
        return 100.0 / (1.0 + math.exp(-lg))
    e = math.exp(lg)
    return 100.0 * e / (1.0 + e)


def pinball(y, qs):
    tot = 0.0
    for tau, q in zip(LEVELS, qs):
        d = logit_pct(y) - logit_pct(q)
        tot += 2.0 * max(tau * d, (tau - 1.0) * d)
    return tot / len(LEVELS)


def score_forecast(truth, forecast):
    """truth: list of 55 rates in trophy order; forecast: {'trophies': [...]}.
    Returns (loss, typical_miss_pp, coverage_90)."""
    by_id = {r["id"]: r["q"] for r in forecast["trophies"]}
    vals, miss, cov = [], 0.0, 0
    for i in range(len(truth)):
        q = by_id[i + 1]
        vals.append(pinball(truth[i], q))
        miss += abs(truth[i] - q[2])
        if q[0] <= truth[i] <= q[4]:
            cov += 1
    return sum(vals) / len(vals), miss / len(vals), cov / len(vals)


def persistence_forecast(case):
    last = case["history"][-1]["rates"]
    d = case["horizon_minutes"] / 1440.0
    spread = 0.5 * math.sqrt(d)
    rows = []
    for i, tr in enumerate(case["trophies"]):
        r = last[i] if last[i] is not None else 0.0
        lg = logit_pct(r)
        rows.append({"id": tr["id"],
                     "q": [round(inv_logit_pct(lg + z * spread), 4)
                           for z in Z]})
    return {"trophies": rows}


def run_subprocess(main_path, case):
    with tempfile.TemporaryDirectory() as td:
        ind = Path(td) / "in"
        outd = Path(td) / "out"
        ind.mkdir()
        (ind / (case["id"] + ".in")).write_text(json.dumps(case))
        env = dict(os.environ, MAKEFUN_INPUT_DIR=str(ind),
                   MAKEFUN_OUTPUT_DIR=str(outd))
        r = subprocess.run([sys.executable, str(main_path)], env=env,
                           capture_output=True, text=True, timeout=120)
        assert r.returncode == 0, r.stderr[-1500:]
        return json.loads((outd / (case["id"] + ".out")).read_text())


def run_v6(case):
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / (case["id"] + ".in")
        p.write_text(json.dumps(case))
        c, hist, series = v6.read_case(p)
        return v6.forecast_case(c, hist, series)


MODELS = {"v6": run_v6, "v3r": lambda c: run_subprocess(V3R, c),
          "v4": lambda c: run_subprocess(V4, c),
          "v5": lambda c: run_subprocess(V5, c),
          "pers": persistence_forecast}


def suite_proxy(models=("v6", "v3r", "v4", "v5", "pers")):
    print("== (a) practice-proxy worlds (13, aggregate-consistent) ==")
    cases, proxy = W4.proxy_worlds()
    tot = {m: [] for m in models}
    for wname, ans in sorted(proxy.items()):
        line = "%-22s " % wname
        for cid in ("p00", "p01"):
            truth = [ans[cid][i + 1] for i in range(55)]
            for m in models:
                s = score_forecast(truth, MODELS[m](cases[cid]))[0]
                tot[m].append(s)
        line += "  ".join("%s %.4f" % (m, sum(tot[m][-2:]) / 2)
                          for m in models)
        print(line)
    for m in models:
        print("MEAN %-4s %.4f" % (m, sum(tot[m]) / len(tot[m])))
    return {m: sum(tot[m]) / len(tot[m]) for m in models}


def suite_factor(models=("v6", "v3r", "v4", "v5", "pers")):
    print("== (b) uniform-factor truths on real p00/p01 ==")
    tot = {m: [] for m in models}
    for f in (0.15, 0.20, 0.25, 0.30):
        for cid in ("p00", "p01"):
            case = json.loads((KIT_IN / (cid + ".in")).read_text())
            last = case["history"][-1]["rates"]
            truth = [100.0 if r >= 99.99 else round(r * f, 2)
                     for r in last]
            for m in models:
                tot[m].append(score_forecast(truth, MODELS[m](case))[0])
        print("f=%.2f  " % f + "  ".join(
            "%s %.4f" % (m, sum(tot[m][-2:]) / 2) for m in models))
    for m in models:
        print("MEAN %-4s %.4f" % (m, sum(tot[m]) / len(tot[m])))
    return {m: sum(tot[m]) / len(tot[m]) for m in models}


def load_bt5():
    spec = importlib.util.spec_from_file_location(
        "bt5", "/home/hatch/workspace/makefun/"
        "gta6-trophy-rarity-forecast-01-v5/tools/backtest_v5.py")
    bt5 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bt5)
    return bt5


def suite_final5(models=("v6", "v3r", "v4", "v5", "pers")):
    print("== (c) v5-style final-like worlds (60h hist, 108h horizon) ==")
    bt5 = load_bt5()
    tot = {m: [] for m in models}
    for world in ("weibull", "loglogistic", "delayed", "flat-refresh"):
        for seed in (101, 202):
            case, truth = bt5.build_case(world, seed)
            line = "%-14s %-4d " % (world, seed)
            for m in models:
                s = score_forecast(truth, MODELS[m](case))[0]
                tot[m].append(s)
                line += "%s %.4f  " % (m, s)
            print(line)
    for m in models:
        print("MEAN %-4s %.4f" % (m, sum(tot[m]) / len(tot[m])))
    return {m: sum(tot[m]) / len(tot[m]) for m in models}


def suite_synth(models=("v6", "v3r", "v4", "v5", "pers")):
    print("== (d) v4-style synthetic worlds (cohort simulation) ==")
    synth = W4.synthetic_worlds()
    tot = {m: [] for m in models}
    for prefix in ("synth-practice-", "synth-final-"):
        sel = {k: v for k, v in synth.items() if k.startswith(prefix)}
        sub = {m: [] for m in models}
        for name, (case, ans) in sorted(sel.items()):
            truth = [ans[i + 1] for i in range(55)]
            for m in models:
                s = score_forecast(truth, MODELS[m](case))[0]
                tot[m].append(s)
                sub[m].append(s)
        print("%-16s " % prefix + "  ".join(
            "%s %.4f" % (m, sum(sub[m]) / len(sub[m])) for m in models))
    print("== expanding CV ==")
    for name, (case, ans) in sorted(W4.cv_worlds().items()):
        truth = [ans[i + 1] for i in range(55)]
        line = "%-12s " % name
        for m in models:
            s = score_forecast(truth, MODELS[m](case))[0]
            tot[m].append(s)
            line += "%s %.4f  " % (m, s)
        print(line)
    for m in models:
        print("MEAN %-4s %.4f" % (m, sum(tot[m]) / len(tot[m])))
    return {m: sum(tot[m]) / len(tot[m]) for m in models}


def checks():
    print("== format / determinism / runtime ==")
    import time
    for cid in ("p00", "p01"):
        case = json.loads((KIT_IN / (cid + ".in")).read_text())
        t0 = time.time()
        o1 = run_v6(case)
        dt = time.time() - t0
        o2 = run_v6(case)
        assert o1 == o2, "non-deterministic!"
        assert set(o1.keys()) == {"trophies"} and len(o1["trophies"]) == 55
        for r in o1["trophies"]:
            assert set(r.keys()) == {"id", "q"} and len(r["q"]) == 5
            assert all(0.0 <= v <= 100.0 for v in r["q"])
            assert all(r["q"][i] <= r["q"][i + 1] for i in range(4))
        blob = json.dumps(o1, separators=(",", ":"))
        assert len(blob) <= 65536, len(blob)
        print("%s: valid, %d bytes, deterministic, %.2fs" % (cid, len(blob), dt))
    # a final-like case (v5 world) for runtime on a moving history
    bt5 = load_bt5()
    case, _ = bt5.build_case("weibull", 101)
    t0 = time.time()
    run_v6(case)
    print("moving-history case: %.2fs (cap 8s)" % (time.time() - t0))
    print("ALL CHECKS DONE")


def tune():
    """Grid-search the flat-path knobs on suites (a)+(b), v6 only,
    in-process. Two stages (median knobs, then fan knobs), N_MC reduced
    for speed; every config prints as it finishes so a timeout still
    leaves partial results. The winner is re-verified at full N_MC by
    the normal suites."""
    import itertools
    cases, proxy = W4.proxy_worlds()
    p_cases = [json.loads((KIT_IN / (c + ".in")).read_text())
               for c in ("p00", "p01")]
    proxy_truths = []
    for wname, ans in sorted(proxy.items()):
        for cid in ("p00", "p01"):
            proxy_truths.append((p_cases[0] if cid == "p00" else p_cases[1],
                                 [ans[cid][i + 1] for i in range(55)]))
    factor_truths = []
    for f in (0.15, 0.20, 0.25, 0.30):
        for case in p_cases:
            last = case["history"][-1]["rates"]
            factor_truths.append((case, [100.0 if r >= 99.99 else round(r * f, 2)
                                         for r in last]))
    v6.N_MC = 800

    def eval_cfg():
        pa = sum(score_forecast(t, run_v6(c))[0] for c, t in proxy_truths) \
            / len(proxy_truths)
        fa = sum(score_forecast(t, run_v6(c))[0] for c, t in factor_truths) \
            / len(factor_truths)
        return (pa + fa) / 2, pa, fa

    print("stage 1: median knobs (S_MULT=0.25, S_ALPHA=0.50)")
    stage1 = []
    for age, gr in itertools.product((0.15, 0.20, 0.30), (0.10, 0.15, 0.25)):
        v6.NEW_AGE_H = age
        v6.GROWTH = gr
        v6.S_MULT = 0.25
        v6.S_ALPHA = 0.50
        mean, pa, fa = eval_cfg()
        stage1.append((mean, pa, fa, age, gr))
        print("  mean %.4f proxy %.4f factor %.4f  NEW_AGE=%.2f GROWTH=%.2f"
              % (mean, pa, fa, age, gr), flush=True)
    stage1.sort()
    _, _, _, best_age, best_gr = stage1[0]
    print("stage 2: fan knobs (NEW_AGE=%.2f, GROWTH=%.2f)"
          % (best_age, best_gr))
    stage2 = []
    for sm, sa in itertools.product((0.15, 0.25, 0.35), (0.30, 0.50, 0.70)):
        v6.NEW_AGE_H = best_age
        v6.GROWTH = best_gr
        v6.S_MULT = sm
        v6.S_ALPHA = sa
        mean, pa, fa = eval_cfg()
        stage2.append((mean, pa, fa, sm, sa))
        print("  mean %.4f proxy %.4f factor %.4f  S_MULT=%.2f S_ALPHA=%.2f"
              % (mean, pa, fa, sm, sa), flush=True)
    stage2.sort()
    print("BEST stage1: mean %.4f proxy %.4f factor %.4f NEW_AGE=%.2f "
          "GROWTH=%.2f" % stage1[0])
    print("BEST stage2: mean %.4f proxy %.4f factor %.4f S_MULT=%.2f "
          "S_ALPHA=%.2f" % stage2[0])
    v6.N_MC = 3000
    return stage1, stage2


if __name__ == "__main__":
    which = sys.argv[1:] or ["all"]
    if "tune" in which:
        tune()
    if "all" in which or "proxy" in which:
        suite_proxy()
    if "all" in which or "factor" in which:
        suite_factor()
    if "all" in which or "final5" in which:
        suite_final5()
    if "all" in which or "synth" in which:
        suite_synth()
    if "all" in which or "checks" in which:
        checks()
