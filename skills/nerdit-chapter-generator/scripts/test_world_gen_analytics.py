"""The shared generation core, references/nerdit_world_gen.py (Plan C Tasks 2-7)."""
import csv
import hashlib
import io
import subprocess
import sys
from pathlib import Path

import pytest

from make_world_data import CORE
from nerdit_world_gen import build_files, column_order, generate, to_csv, validate_world
from test_world_data import world

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
LIBRARY = HERE.parent / "references" / "worlds"


def hashes(world_path: Path, out: Path) -> str:
    r = subprocess.run([sys.executable, str(HERE / "make_world_data.py"), "--world", str(world_path),
                        "--out-dir", str(out)], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    return "".join(f"{hashlib.sha256((out / n).read_bytes()).hexdigest()}  {n}\n"
                   for n in ("world_data.json", "world_data.sql"))


@pytest.mark.parametrize("name, path", [
    ("practice-retail", LIBRARY / "practice-retail.world.json"),
    ("records-course", FIXTURES / "records-course.world.json"),
])
def test_existing_worlds_are_byte_identical(tmp_path, name, path):
    assert hashes(path, tmp_path) == (FIXTURES / f"{name}.sha256").read_text(encoding="utf-8")


def test_column_order_is_sorted_without_dependencies():
    cols = {"b": {"generator": "int_range", "min": 1, "max": 2}, "a": {"generator": "id"}}
    assert column_order(cols) == ["a", "b"]


def test_csv_quotes_round_trip():
    tricky = 'He said "hi", then left\nlater'
    text = to_csv([{"a": tricky, "b": None}, {"a": "plain", "b": 3}], ["a", "b"])
    assert list(csv.reader(io.StringIO(text))) == [["a", "b"], [tricky, ""], ["plain", "3"]]


def recipe(seed: int, drop=()) -> dict:
    return {"seed": seed, "files": {"orders.csv": {"entity": "orders", "drop": list(drop)}}, "world": world()}


def test_build_files_uses_recipe_seed_and_drop():
    one, two = build_files(recipe(1)), build_files(recipe(2))
    assert set(one) == {"orders.csv"} and one["orders.csv"] != two["orders.csv"]
    assert one == build_files(recipe(1))
    header = build_files(recipe(1, drop=["customer"]))["orders.csv"].splitlines()[0].split(",")
    assert "customer" not in header and "order_id" in header


def test_core_runs_from_source_text():
    ns = {"__name__": "nerdit_world_gen"}
    exec(compile(CORE.read_text(encoding="utf-8"), "nerdit_world_gen.py", "exec"), ns)
    assert ns["build_files"](recipe(1)) == build_files(recipe(1))


def test_validate_and_generate_are_the_core_functions():
    import make_world_data
    assert make_world_data.generate is generate and make_world_data.validate_world is validate_world


# ---- Task 3: profiles and distributions -------------------------------------------------

def one(columns: dict, rows: int = 5000, seed: int = 7, profile: str = "analytics", **entity) -> dict:
    """A valid world with a single entity `t`."""
    w = world()
    w["seed"], w["profile"] = seed, profile
    w["entities"] = {"t": {"rows": rows, "columns": columns, **entity}}
    return w


def col(rows: list, name: str) -> list:
    return [r[name] for r in rows]


def mean(xs):
    return sum(xs) / len(xs)


def sd(xs):
    m = mean(xs)
    return (sum((x - m) ** 2 for x in xs) / (len(xs) - 1)) ** 0.5


def median(xs):
    s = sorted(xs)
    return s[len(s) // 2]


ID = {"t_id": {"generator": "id"}}


def test_profiles_cap_rows_and_cells():
    with pytest.raises(ValueError, match="between 0 and 100"):
        validate_world(one(ID, rows=101, profile="sql"))
    validate_world(one(ID, rows=20_000))
    with pytest.raises(ValueError, match="20000"):
        validate_world(one(ID, rows=20_001))
    wide = {f"c{i}": {"generator": "bernoulli", "p": 0.5} for i in range(11)}
    with pytest.raises(ValueError, match="200000 cells"):
        validate_world(one(wide, rows=20_000))
    sql_world = one(ID, rows=20_000, profile="sql")
    sql_world["entities"]["t"]["profile"] = "analytics"  # an entity may opt in on its own
    validate_world(sql_world)
    with pytest.raises(ValueError, match="profile"):
        validate_world(one(ID, profile="big"))


def test_distributions_have_expected_moments():
    rows = generate(one({
        "score": {"generator": "normal", "mean": 50, "sd": 10},
        "clamped": {"generator": "normal", "mean": 50, "sd": 30, "min": 0, "max": 100, "round": 0},
        "calls": {"generator": "poisson", "lam": 4},
        "busy": {"generator": "poisson", "lam": 60},
        "paid": {"generator": "bernoulli", "p": 0.3},
        "order_value": {"generator": "lognormal", "median": 1000, "sigma": 0.6, "max": 20000},
    }))["t"]
    score = col(rows, "score")
    assert abs(mean(score) - 50) <= 0.6 and abs(sd(score) - 10) <= 0.6
    assert all(round(v, 2) == v for v in score)
    clamped = col(rows, "clamped")
    assert all(type(v) is int and 0 <= v <= 100 for v in clamped)
    assert abs(mean(col(rows, "calls")) - 4) <= 0.15
    assert all(type(v) is int and v >= 0 for v in col(rows, "calls"))
    assert abs(mean(col(rows, "busy")) - 60) <= 0.6
    assert abs(mean(col(rows, "paid")) - 0.3) <= 0.02 and set(col(rows, "paid")) == {0, 1}
    values = col(rows, "order_value")
    assert abs(median(values) - 1000) <= 50 and max(values) <= 20000


@pytest.mark.parametrize("spec", [
    {"generator": "normal", "mean": 1, "sd": -1},
    {"generator": "bernoulli", "p": 1.5},
    {"generator": "poisson", "lam": 0},
    {"generator": "lognormal", "median": 0, "sigma": 1},
    {"generator": "normal", "mean": 1, "sd": 1, "min": 5, "max": 1},
    {"generator": "normal", "mean": 1, "sd": 1, "colour": "red"},
    {"generator": "normal", "mean": True, "sd": 1},
])
def test_bad_distribution_params_fail(spec):
    with pytest.raises(ValueError, match=r"t\.x"):
        validate_world(one({"x": spec}))


# ---- Task 4: dependent columns ----------------------------------------------------------

def slope(xs, ys):
    mx, my = mean(xs), mean(ys)
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)


def test_linear_recovers_declared_weight():
    rows = generate(one({
        "x": {"generator": "normal", "mean": 10, "sd": 3},
        "y": {"generator": "linear", "intercept": 3, "terms": {"x": 2}, "noise_sd": 1},
    }))["t"]
    assert abs(slope(col(rows, "x"), col(rows, "y")) - 2) <= 0.2


@pytest.mark.parametrize("rate", [0.30, 0.05])
def test_logistic_target_rate_sets_class_balance(rate):
    rows = generate(one({
        "x": {"generator": "normal", "mean": 0, "sd": 1},
        "kind": {"generator": "choice", "values": ["a", "b"]},
        "label": {"generator": "logistic", "intercept": 5, "terms": {"x": 1.5},
                  "effects": {"kind": {"a": 1}}, "target_rate": rate},
    }, rows=20_000))["t"]
    labels = col(rows, "label")
    assert set(labels) == {0, 1}
    assert abs(mean(labels) - rate) <= 0.01
    xs = col(rows, "x")  # the declared weight is real: positives have higher x
    assert mean([x for x, y in zip(xs, labels) if y]) > mean([x for x, y in zip(xs, labels) if not y])


def test_effects_and_bins_shift_values():
    rows = generate(one({
        "channel": {"generator": "choice", "values": ["web", "shop"]},
        "spend": {"generator": "linear", "intercept": 100, "effects": {"channel": {"web": 50}}, "noise_sd": 5},
        "age": {"generator": "int_range", "min": 18, "max": 60},
        "bonus": {"generator": "binned_effect", "column": "age", "edges": [30, 45], "deltas": [0, 10, 25]},
    }))["t"]
    web = mean([r["spend"] for r in rows if r["channel"] == "web"])
    shop = mean([r["spend"] for r in rows if r["channel"] == "shop"])
    assert 45 <= web - shop <= 55
    for r in rows:  # bisect_right: an edge value belongs to the bin above it
        assert r["bonus"] == (0 if r["age"] < 30 else 10 if r["age"] < 45 else 25)


def test_column_cycle_fails():
    with pytest.raises(ValueError, match=r"cyclic column dependency at t\.(a|b)"):
        validate_world(one({
            "a": {"generator": "linear", "intercept": 0, "terms": {"b": 1}},
            "b": {"generator": "linear", "intercept": 0, "terms": {"a": 1}},
            "c": {"generator": "linear", "intercept": 0, "terms": {"a": 1}},
        }))


def test_dependency_order_draws_inputs_first():
    w = one({
        "a_out": {"generator": "linear", "intercept": 0, "terms": {"z_in": 1}},
        "z_in": {"generator": "int_range", "min": 1, "max": 9},
    }, rows=10)
    assert column_order(w["entities"]["t"]["columns"]) == ["z_in", "a_out"]
    rows = generate(w)["t"]
    assert all(r["a_out"] == r["z_in"] for r in rows)


@pytest.mark.parametrize("spec, message", [
    ({"generator": "linear", "intercept": 0, "terms": {"nope": 1}}, "nope"),
    ({"generator": "linear", "intercept": 0, "terms": {"x": "big"}}, "weight"),
    ({"generator": "logistic", "terms": {"x": 1}}, "intercept"),
    ({"generator": "logistic", "intercept": 0, "target_rate": 1.0}, "target_rate"),
    ({"generator": "binned_effect", "column": "x", "edges": [5, 1], "deltas": [0, 1, 2]}, "ascending"),
    ({"generator": "binned_effect", "column": "x", "edges": [1, 5], "deltas": [0, 1]}, "deltas"),
])
def test_dependent_column_params_are_checked(spec, message):
    with pytest.raises(ValueError, match=message):
        validate_world(one({"x": {"generator": "normal", "mean": 0, "sd": 1}, "y": spec}))


def test_target_rate_needs_the_analytics_profile():
    w = one({"x": {"generator": "normal", "mean": 0, "sd": 1},
             "y": {"generator": "logistic", "intercept": 0, "terms": {"x": 1}, "target_rate": 0.3}},
            rows=50, profile="sql")
    with pytest.raises(ValueError, match="analytics"):
        validate_world(w)


# ---- Task 5: segments and text ----------------------------------------------------------

SEGMENTS = {
    "budget": {"weight": 0.6, "overrides": {"income": {"mean": 30000}}},
    "premium": {"weight": 0.4, "overrides": {"income": {"mean": 90000, "sd": 9000}}},
}


@pytest.mark.parametrize("profile", ["analytics", "sql"])
def test_segments_create_separable_groups(profile):
    rows_n = 5000 if profile == "analytics" else 100
    w = one({"income": {"generator": "normal", "mean": 50000, "sd": 3000, "round": 0}},
            rows=rows_n, profile=profile, segments=SEGMENTS)
    rows = generate(w)["t"]
    assert list(rows[0]) == ["income", "_segment"]
    for name, want in (("budget", 30000), ("premium", 90000)):
        got = [r["income"] for r in rows if r["_segment"] == name]
        assert abs(mean(got) - want) <= 0.1 * want
    if profile == "analytics":
        assert abs(mean([r["_segment"] == "budget" for r in rows]) - 0.6) <= 0.03
    text = build_files({"seed": 3, "files": {"t.csv": {"entity": "t", "drop": ["_segment"]}}, "world": w})["t.csv"]
    assert text.splitlines()[0] == "income"


@pytest.mark.parametrize("segments, message", [
    ({"a": {"weight": 0, "overrides": {}}}, "weight"),
    ({"a": {"weight": 1, "overrides": {"nope": {"mean": 1}}}}, "nope"),
    ({"a": {"weight": 1, "overrides": {"income": {"sd": -5}}}}, "sd"),
    ({"a": {"weight": 1, "overrides": {"income": {"generator": "poisson"}}}}, "generator"),
])
def test_bad_segments_fail(segments, message):
    with pytest.raises(ValueError, match=message):
        validate_world(one({"income": {"generator": "normal", "mean": 1, "sd": 1}}, segments=segments))


REVIEW = {
    "generator": "text",
    "templates": ["The {item} was fine."],
    "slots": {"item": ["notebook", "pen set"], "reason": ["it smudged", "it arrived late, again"]},
    "tone_from": {"rating": {
        "5": ["Love the {item}!", "Great {item}, would buy again."],
        "1": ["The {item} broke: {reason}.", "Sent the {item} back because {reason}."],
    }},
}


def test_text_follows_tone_and_fills_slots():
    rows = generate(one({"rating": {"generator": "choice", "values": [1, 3, 5]}, "review": REVIEW}))["t"]
    happy = {"Love the {item}!", "Great {item}, would buy again."}
    for r in rows:
        assert "{" not in r["review"] and "}" not in r["review"]
        if r["rating"] == 5:
            assert any(r["review"] == t.replace("{item}", i) for t in happy for i in ("notebook", "pen set"))
        if r["rating"] == 3:
            assert r["review"].startswith("The ") and r["review"].endswith(" was fine.")
        if r["rating"] == 1:
            assert "broke" in r["review"] or "back because" in r["review"]
    assert len({r["review"] for r in rows}) > 6


@pytest.mark.parametrize("change, message", [
    ({"templates": ["Call me on {phone}."]}, "phone"),
    ({"slots": {"item": ["98765 43210"], "reason": ["x"]}}, "phone number"),
    ({"slots": {"item": ["9876543210"], "reason": ["x"]}}, "phone number"),
    ({"slots": {"item": ["my email is a@b.in"], "reason": ["x"]}}, "contact"),
    ({"slots": {"item": ["{reason}"], "reason": ["x"]}}, "brace"),
    ({"tone_from": {"nope": {"1": ["x"]}}}, "nope"),
])
def test_text_rejects_unknown_placeholders_and_contact_slots(change, message):
    spec = dict(REVIEW, **change)
    with pytest.raises(ValueError, match=message):
        validate_world(one({"rating": {"generator": "choice", "values": [1, 5]}, "review": spec}))


# ---- Task 6: series and interactions -----------------------------------------------------

def series_world(seed: int = 7, **params) -> dict:
    w = one(ID, seed=seed)
    w["entities"] = {"sales": dict({"kind": "series", "start": "2025-01-01", "end": "2025-12-31",
                                    "freq": "day", "base": 100, "noise_sd": 3}, **params)}
    return w


def by_date(rows, lo, hi):
    return [r["value"] for r in rows if lo <= r["date"] <= hi]


def test_series_has_trend_season_holiday_and_break():
    rows = generate(series_world(monthly={"12": 1.6}, trend_per_period=0.05,
                                 weekly=[1, 1, 1, 1, 1.2, 1.4, 0.8],
                                 holidays=[{"date": "2025-10-20", "lift": 0.8, "days": 5}]))["sales"]
    assert len(rows) == 365 and list(rows[0]) == ["date", "value"]
    assert rows[0]["date"] == "2025-01-01" and all(type(r["value"]) is int and r["value"] >= 0 for r in rows)
    assert mean(by_date(rows, "2025-12-01", "2025-12-31")) > mean(by_date(rows, "2025-07-01", "2025-07-31"))
    festival = mean(by_date(rows, "2025-10-20", "2025-10-24"))
    around = by_date(rows, "2025-10-06", "2025-10-19") + by_date(rows, "2025-10-25", "2025-11-07")
    assert festival > mean(around) * 1.5
    assert mean(by_date(rows, "2025-07-01", "2025-07-31")) > mean(by_date(rows, "2025-02-01", "2025-02-28"))

    broken = generate(series_world(**{"break": {"date": "2025-07-01", "shift": 40}}))["sales"]
    jump = mean(by_date(broken, "2025-07-01", "2025-12-31")) - mean(by_date(broken, "2025-01-01", "2025-06-30"))
    assert abs(jump - 40) <= 4

    weekly = generate(series_world(freq="week", value_column="orders", date_column="week_start"))["sales"]
    assert len(weekly) in (52, 53) and list(weekly[0]) == ["week_start", "orders"]
    monthly = generate(series_world(freq="month"))["sales"]
    assert [r["date"] for r in monthly][:2] == ["2025-01-01", "2025-02-01"] and len(monthly) == 12


@pytest.mark.parametrize("change, message", [
    ({"freq": "hour"}, "freq"),
    ({"freq": "week", "weekly": [1] * 7}, "weekly"),
    ({"weekly": [1] * 6}, "weekly"),
    ({"monthly": {"13": 1}}, "monthly"),
    ({"holidays": [{"date": "2025-10-20", "lift": 0.5}]}, "holiday"),
    ({"start": "2025-01-15", "freq": "month"}, "first day"),
    ({"end": "2050-01-01"}, "ten years"),
    ({"colour": "red"}, "colour"),
])
def test_bad_series_fail(change, message):
    with pytest.raises(ValueError, match=message):
        validate_world(series_world(**change))


def ratings_world(seed: int = 7, **params) -> dict:
    w = one({}, seed=seed)
    w["entities"] = {
        "customers": {"rows": 200, "columns": {"customer_id": {"generator": "id", "prefix": "C"}}},
        "products": {"rows": 50, "columns": {"product_id": {"generator": "id", "prefix": "P"},
                                             "shelf": {"generator": "choice", "values": ["A", "B"]}}},
        "ratings": dict({"kind": "interactions", "users": "customers", "items": "products",
                         "user_column": "customer_id", "item_column": "product_id",
                         "k": 3, "density": 0.1, "scale": [1, 5], "noise_sd": 0.4}, **params),
    }
    return w


def test_interactions_density_scale_and_signal():
    data = generate(ratings_world())
    rows = data["ratings"]
    assert list(rows[0]) == ["customer_id", "product_id", "rating"]
    assert abs(len(rows) / (200 * 50) - 0.1) <= 0.02
    assert all(type(r["rating"]) is int and 1 <= r["rating"] <= 5 for r in rows)
    users = {r["customer_id"] for r in data["customers"]}
    assert {r["customer_id"] for r in rows} <= users
    assert len({(r["customer_id"], r["product_id"]) for r in rows}) == len(rows)
    clean = generate(ratings_world(noise_sd=0, density=0.3))["ratings"]
    per_user = {}
    for r in clean:
        per_user.setdefault(r["customer_id"], []).append(r["rating"])
    means = sorted(mean(v) for v in per_user.values() if len(v) >= 5)
    assert means[-1] - means[0] >= 1  # users really differ: there is a signal to find


@pytest.mark.parametrize("change, message", [
    ({"users": "nobody"}, "users"),
    ({"user_column": "shelf"}, "user_column"),
    ({"k": 6}, "k"),
    ({"density": 0.5}, "density"),
    ({"scale": [5, 1]}, "scale"),
])
def test_bad_interactions_fail(change, message):
    with pytest.raises(ValueError, match=message):
        validate_world(ratings_world(**change))


def test_series_and_interactions_are_seeded():
    assert generate(series_world(seed=1)) == generate(series_world(seed=1))
    assert generate(series_world(seed=1)) != generate(series_world(seed=2))
    assert generate(ratings_world(seed=1)) == generate(ratings_world(seed=1))
    assert generate(ratings_world(seed=1))["ratings"] != generate(ratings_world(seed=2))["ratings"]
    files = build_files({"seed": 4, "world": ratings_world(), "files": {
        "ratings.csv": {"entity": "ratings"}, "sales.csv": {"entity": "customers", "drop": []}}})
    assert files["ratings.csv"].splitlines()[0] == "customer_id,product_id,rating"


# ---- Task 7: planned defects and the manifest --------------------------------------------

DIRTY_COLUMNS = {
    "order_id": {"generator": "id", "prefix": "O"},
    "amount": {"generator": "normal", "mean": 500, "sd": 50},
    "score": {"generator": "normal", "mean": 70, "sd": 5},
    "label": {"generator": "bernoulli", "p": 0.3},
    "channel": {"generator": "choice", "values": ["web", "shop"]},
    "sold_on": {"generator": "date_range", "start": "2025-01-01", "end": "2025-12-31"},
}
DEFECTS = {
    "missing": [{"column": "amount", "rate": 0.05}, {"column": "channel", "rate": 0.1, "when": {"label": 1}}],
    "outliers": [{"column": "amount", "rate": 0.01, "factor": 10}],
    "label_noise": {"column": "label", "rate": 0.05},
    "duplicates": 0.02,
    "drift": {"after": "2025-07-01", "column": "score", "shift": 5},
}


def test_defects_hit_declared_rates_and_are_recorded():
    clean = generate(one(DIRTY_COLUMNS))["t"]
    manifest = {}
    rows = generate(one(DIRTY_COLUMNS, defects=DEFECTS), manifest)["t"]
    found = manifest["defects"]["t"]
    assert len(rows) == 5100
    original = rows[:5000]

    missing = found["missing"]["amount"]
    assert missing == [i for i, r in enumerate(original) if r["amount"] is None] and len(missing) == 250
    labelled = [i for i, r in enumerate(original) if r["label"] == 1]  # `when` sees the noisy labels
    assert set(found["missing"]["channel"]) <= {i for i, r in enumerate(original) if r["channel"] is None}
    assert abs(len(found["missing"]["channel"]) - 0.1 * len(labelled)) <= 1

    out = found["outliers"]["amount"]
    assert len(out) == 50
    for i in out:
        assert original[i]["amount"] is None or original[i]["amount"] == round(clean[i]["amount"] * 10, 2)

    flipped = found["label_noise"]["label"]
    assert len(flipped) == 250 and all(original[i]["label"] == 1 - clean[i]["label"] for i in flipped)
    assert all(original[i]["label"] == clean[i]["label"] for i in set(range(5000)) - set(flipped))

    drifted = found["drift"]["score"]
    assert drifted == [i for i, r in enumerate(clean) if r["sold_on"] >= "2025-07-01"]
    assert all(original[i]["score"] == round(clean[i]["score"] + 5, 2) for i in drifted)
    assert all(original[i]["score"] == clean[i]["score"] for i in set(range(5000)) - set(drifted))

    copies = found["duplicates"]
    assert copies["rows"] == list(range(5000, 5100)) and len(copies["of"]) == 100
    assert len({r["order_id"] for r in rows}) == 5100  # copies get new ids ...
    for new, src in zip(copies["rows"], copies["of"]):  # ... and keep everything else
        assert {k: v for k, v in rows[new].items() if k != "order_id"} == \
               {k: v for k, v in rows[src].items() if k != "order_id"}


@pytest.mark.parametrize("defects, message", [
    ({"missing": [{"column": "nope", "rate": 0.1}]}, "nope"),
    ({"missing": [{"column": "amount", "rate": 0.9}]}, "rate"),
    ({"outliers": [{"column": "channel", "rate": 0.1, "factor": 10}]}, "number"),
    ({"label_noise": {"column": "amount", "rate": 0.1}}, "0 or 1"),
    ({"drift": {"after": "2025-07-01", "column": "score", "shift": 1, "date_column": "amount"}}, "date"),
    ({"typos": 0.1}, "typos"),
])
def test_bad_defects_fail(defects, message):
    with pytest.raises(ValueError, match=message):
        generate(one(DIRTY_COLUMNS, rows=200, defects=defects))


def test_defects_leave_existing_draws_alone():
    """Defects are applied after an entity's columns, so the clean values of other rows stay put."""
    clean = generate(one(DIRTY_COLUMNS, rows=300))["t"]
    dirty = generate(one(DIRTY_COLUMNS, rows=300, defects={"missing": [{"column": "score", "rate": 0.1}]}))["t"]
    assert [r["amount"] for r in clean] == [r["amount"] for r in dirty]


def test_text_allows_iso_dates_but_not_phone_numbers():
    ok = dict(REVIEW, slots={"item": ["order of 2025-01-02"], "reason": ["it came on 2025-11-15"]})
    validate_world(one({"rating": {"generator": "choice", "values": [1, 5]}, "review": ok}))
    bad = dict(REVIEW, slots={"item": ["98765-43210"], "reason": ["x"]})
    with pytest.raises(ValueError, match="phone number"):
        validate_world(one({"rating": {"generator": "choice", "values": [1, 5]}, "review": bad}))


# ---- Final review fixes --------------------------------------------------------------------

def test_segment_override_terms_follow_dependency_order():
    segs = {"s": {"weight": 1, "overrides": {"a_out": {"terms": {"z_in": 1}}}}}
    w = one({"a_out": {"generator": "linear", "intercept": 0},
             "z_in": {"generator": "int_range", "min": 1, "max": 9}}, rows=50, segments=segs)
    rows = generate(w)["t"]
    assert all(r["a_out"] == r["z_in"] for r in rows)


def test_segment_override_cycle_fails():
    segs = {"s": {"weight": 1, "overrides": {"a": {"terms": {"b": 1}}}}}
    w = one({"a": {"generator": "linear", "intercept": 0},
             "b": {"generator": "linear", "intercept": 0, "terms": {"a": 1}}}, rows=50, segments=segs)
    with pytest.raises(ValueError, match="cyclic column dependency"):
        validate_world(w)


@pytest.mark.parametrize("override", [{"target_rate": 0.9}, {"intercept": 2}])
def test_segments_may_not_rebalance_a_target_rate_label(override):
    segs = {"s": {"weight": 1, "overrides": {"y": override}}}
    w = one({"x": {"generator": "normal", "mean": 0, "sd": 1},
             "y": {"generator": "logistic", "terms": {"x": 1}, "target_rate": 0.3}}, segments=segs)
    with pytest.raises(ValueError, match="target_rate"):
        validate_world(w)
