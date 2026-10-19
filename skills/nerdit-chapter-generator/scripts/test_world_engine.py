"""The generator core on the website's engine (Plan C Task 8): same bytes, fast enough, pandas-readable.

Engine-only: skipped, with the reason, when tools/pyodide is not installed.
"""
import hashlib
import json

import pytest

from make_world_data import CORE
from nerdit_world_gen import build_files, generate
from pyodide_engine import engine_available, run_job
from test_world_data import world

AVAILABLE, REASON = engine_available()
pytestmark = pytest.mark.skipif(not AVAILABLE, reason=REASON)

LOAD = ('import json, hashlib\n'
        'ns = {"__name__": "nerdit_world_gen"}\n'
        'exec(open("nerdit_world_gen.py").read(), ns)\n'
        'recipe = json.load(open("recipe.json"))\n')


def everything() -> dict:
    """An analytics world that uses every generator, entity kind and defect."""
    w = world()
    w["profile"] = "analytics"
    w["entities"] = {
        "products": {"rows": 40, "columns": {
            "product_id": {"generator": "id", "prefix": "P"},
            "shelf": {"generator": "weighted_choice", "values": ["A", "B", "C"], "weights": [3, 2, 1]},
            "price_paise": {"generator": "money_range", "min": 1000, "max": 90000}}},
        "customers": {"rows": 3000, "segments": {
            "budget": {"weight": 0.7, "overrides": {"income": {"median": 25000}}},
            "premium": {"weight": 0.3, "overrides": {"income": {"median": 90000}}}}, "columns": {
            "customer_id": {"generator": "id", "prefix": "C"},
            "first_name": {"generator": "person_name", "values": ["Aarav", "Diya", "Kabir"]},
            "city": {"generator": "choice", "values": ["Surat", "Pune"]},
            "age": {"generator": "int_range", "min": 18, "max": 70},
            "joined_on": {"generator": "date_range", "start": "2024-01-01", "end": "2025-12-31",
                          "monthWeights": {"10": 3, "11": 2}},
            "income": {"generator": "lognormal", "median": 40000, "sigma": 0.5, "round": 0},
            "visits": {"generator": "poisson", "lam": 3},
            "score": {"generator": "normal", "mean": 60, "sd": 12, "min": 0, "max": 100, "round": 1},
            "has_app": {"generator": "bernoulli", "p": 0.4},
            "age_band_bonus": {"generator": "binned_effect", "column": "age", "edges": [30, 50],
                               "deltas": [0, 400, 900]},
            "spend": {"generator": "linear", "intercept": 500, "terms": {"visits": 120, "age_band_bonus": 1},
                      "effects": {"city": {"Pune": 250}}, "noise_sd": 80, "min": 0},
            "churned": {"generator": "logistic", "terms": {"visits": -0.4, "has_app": -0.8},
                        "effects": {"city": {"Surat": 0.3}}, "target_rate": 0.2},
            "note": {"generator": "text", "templates": ["Asked about {thing}."],
                     "slots": {"thing": ["fees", "the \"weekend\" batch", "timings, again"]},
                     "tone_from": {"churned": {"1": ["Left: {thing}, said \"too late\".", "Gone.\nNo reply."]}}},
            "favourite": {"generator": "fk", "entity": "products", "column": "product_id"}},
            "defects": {"missing": [{"column": "score", "rate": 0.05}, {"column": "city", "rate": 0.1,
                                                                        "when": {"has_app": 1}}],
                        "outliers": [{"column": "spend", "rate": 0.01, "factor": 8}],
                        "label_noise": {"column": "churned", "rate": 0.03},
                        "drift": {"after": "2025-06-01", "column": "score", "shift": -4},
                        "duplicates": 0.02}},
        "ratings": {"kind": "interactions", "users": "customers", "items": "products",
                    "user_column": "customer_id", "item_column": "product_id", "k": 3,
                    "density": 0.05, "scale": [1, 5], "noise_sd": 0.5,
                    "defects": {"missing": [{"column": "rating", "rate": 0.02}]}},
        "daily": {"kind": "series", "start": "2025-01-01", "end": "2025-12-31", "freq": "day",
                  "base": 40, "trend_per_period": 0.02, "weekly": [1, 1, 1, 1, 1.1, 1.3, 0.7],
                  "monthly": {"10": 1.4, "11": 1.6}, "holidays": [{"date": "2025-10-20", "lift": 0.9, "days": 5}],
                  "noise_sd": 4, "break": {"date": "2025-08-01", "shift": 6}, "value_column": "enquiries",
                  "defects": {"outliers": [{"column": "enquiries", "rate": 0.01, "factor": 3}]}},
    }
    return w


def recipe(w: dict, seed: int = 11) -> dict:
    return {"seed": seed, "world": w, "files": {name: {"entity": name.removesuffix(".csv")}
                                                for name in ("customers.csv", "products.csv", "ratings.csv", "daily.csv")}}


def engine_run(code: str, rec: dict, timeout: int = 180) -> str:
    res = run_job({"files": {"nerdit_world_gen.py": CORE.read_text(encoding="utf-8"), "recipe.json": json.dumps(rec)},
                   "steps": [{"id": "a", "code": LOAD + code, "fresh": True}], "probe": []}, timeout=timeout)
    step = res["results"][0]
    assert step["error"] is None, step
    return step["stdout"]


def test_cpython_and_pyodide_build_identical_files():
    rec = recipe(everything())
    local = {n: hashlib.sha256(t.encode("utf-8")).hexdigest() for n, t in build_files(rec).items()}
    printed = engine_run('out = ns["build_files"](recipe)\n'
                         'for n in sorted(out): print(n, hashlib.sha256(out[n].encode("utf-8")).hexdigest())', rec)
    assert dict(line.split(" ") for line in printed.splitlines()) == local


def test_twenty_thousand_rows_build_within_two_seconds():
    w = everything()
    cols = w["entities"]["customers"]["columns"]
    keep = ("customer_id", "city", "joined_on", "income", "visits", "score", "has_app", "spend", "churned", "note")
    w["entities"] = {"customers": {"rows": 20_000, "columns": {
        c: s for c, s in cols.items() if c in keep}}}
    w["entities"]["customers"]["columns"]["spend"]["terms"] = {"visits": 120}
    assert len(w["entities"]["customers"]["columns"]) == 10
    rec = {"seed": 3, "world": w, "files": {"customers.csv": {"entity": "customers"}}}
    out = engine_run('import time\nt = time.perf_counter()\nns["build_files"](recipe)\n'
                     'print(round(time.perf_counter() - t, 3))', rec)
    assert float(out) < 2.0, f"{out} s in Pyodide"


def test_text_csv_reads_back_in_pandas():
    w = everything()
    w["entities"]["customers"].pop("defects")
    rec = {"seed": 5, "world": w, "files": {"customers.csv": {"entity": "customers", "drop": ["_segment"]}}}
    want = [r["note"] for r in generate(dict(w, seed=5))["customers"]]
    assert any("\n" in n for n in want) and any('"' in n for n in want) and any("," in n for n in want)
    printed = engine_run('import pandas as pd\n'
                         'open("customers.csv", "w").write(ns["build_files"](recipe)["customers.csv"])\n'
                         'print(json.dumps(pd.read_csv("customers.csv")["note"].tolist()))', rec)
    assert json.loads(printed) == want
