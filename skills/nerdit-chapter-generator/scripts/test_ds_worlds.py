"""The five Data Science worlds and the course map (Plan C Task 13, spec Part 4)."""
import json
import re
from pathlib import Path

import pytest

from make_world_data import load_world
from nerdit_world_gen import PRIVATE, generate, looks_like_phone, validate_world

WORLDS = Path(__file__).resolve().parent.parent / "references" / "worlds"
NAMES = ("fvc-institute", "saree-wholesale", "stationery-d2c", "boat-cruises", "wire-mesh")
REAL = ("akruti", "roohani", "jain wire", "australian boat", "australianboatparties")


def load(name: str) -> dict:
    return json.loads((WORLDS / f"{name}.world.json").read_text(encoding="utf-8"))


def clean(world: dict) -> dict:
    """The world without planned defects: the declared, true distributions."""
    w = json.loads(json.dumps(world))
    for e in w["entities"].values():
        e.pop("defects", None)
    return w


def mean(xs):
    return sum(xs) / len(xs)


@pytest.mark.parametrize("name", NAMES)
def test_every_world_validates_and_builds_within_caps(name):
    w = load(name)
    assert w["profile"] == "analytics" and w["cast"] and w["arc"]
    validate_world(w)
    assert load_world(WORLDS / f"{name}.world.json") == w
    data = generate(w)
    assert set(data) == set(w["entities"]) and all(data[e] for e in data)


REAL_BUSINESSES = {  # owner permission confirmed by the course author, 2026-10-20
    "fvc-institute": ("Future Vision Computer Institute", "Surat", "Siddharth Parakh"),
    "saree-wholesale": ("Akruti Sarees", "Surat", "Rohit Jain"),
    "stationery-d2c": ("Roohani Rang", "Mumbai", "Rashi Agarwal"),
    "boat-cruises": ("Australian Boat Parties", "Melbourne", "Akshay"),
    "wire-mesh": ("Jain Wire Netting", "Visakhapatnam", "Rahul Dosi"),
}


@pytest.mark.parametrize("name", NAMES)
def test_real_worlds_record_name_owner_and_permission(name):
    business = load(name)["business"]
    title, city, owner = REAL_BUSINESSES[name]
    assert (business["name"], business["city"], business["owner"]["name"]) == (title, city, owner)
    assert business.get("fictional") is not True
    assert all(business["realName"][k].strip() for k in ("approvedBy", "date", "note"))
    # the owner is the business's real person; every cast member stays invented
    assert owner not in [p["name"] for p in load(name)["cast"]]


def test_practice_world_stays_fictional():
    business = load_world(WORLDS / "practice-retail.world.json")["business"]
    assert business["fictional"] is True and "realName" not in business and "owner" not in business


def test_target_rates_match_the_spec():
    enrolled = [r["enrolled"] for r in generate(clean(load("fvc-institute")))["enquiries"]]
    assert abs(mean(enrolled) - 0.30) <= 0.01
    defective = [r["defective"] for r in generate(clean(load("wire-mesh")))["roll_defects"]]
    assert abs(mean(defective) - 0.05) <= 0.01


def test_seasons_are_present():
    weeks = generate(load("saree-wholesale"))["weekly_orders"]
    festive = [r["sarees_ordered"] for r in weeks if r["week_start"][5:7] in ("10", "11")]
    summer = [r["sarees_ordered"] for r in weeks if r["week_start"][5:7] in ("06", "07")]
    assert mean(festive) > mean(summer)
    days = generate(load("boat-cruises"))["daily_bookings"]
    december = [r["bookings"] for r in days if r["date"][5:7] == "12"]
    july = [r["bookings"] for r in days if r["date"][5:7] == "07"]
    assert mean(december) > mean(july)


def test_course_map_points_at_real_entities():
    rows = json.loads((WORLDS / "ds-course-map.json").read_text(encoding="utf-8"))
    assert len(rows) == 17
    for row in rows:
        uses = ([{"world": row["world"], "entities": row["entities"]}] if row["world"] else []) + row.get("also", [])
        if not uses:
            assert row.get("offline") or row.get("note"), row
        for use in uses:
            assert use["world"] in NAMES, row
            entities = load(use["world"])["entities"]
            assert use["entities"] and all(e in entities for e in use["entities"]), row
    assert any(r.get("offline") for r in rows)


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for k, v in value.items():
            yield k
            yield from strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from strings(v)


@pytest.mark.parametrize("name", NAMES)
def test_no_contact_fields_or_numbers(name):
    for s in strings(load(name)):
        assert not PRIVATE.search(s) and "@" not in s, s
        assert not looks_like_phone(s), s
        assert not re.search(r"https?://|www\.|\.com\b|\.in\b", s), s
