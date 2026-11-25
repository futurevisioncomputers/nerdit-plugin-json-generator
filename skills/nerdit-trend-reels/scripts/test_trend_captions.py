from trend_captions import fill, trend_caption_errors

SCRIPT = {"kind": "daily", "line": "x",
          "card": {"chip": "AI & JOBS", "facts": ["PwC is training 85,000 staff for the AI age"],
                   "sources": ["Business Insider", "Inc."]},
          "course": {"id": "c", "title": "Machine Learning Fundamentals", "lessons": 12,
                     "url": "https://nerdit.in/course/machine-learning-fundamentals-1792397644108/preview"}}
KEPT = [{"headline": "PwC Is Training 85,000 Employees on AI Skills", "evidence": ["certify 85,000 workers"]}]
ITEM = {"id": "2026-11-25-daily-pwc", "date": "2026-11-25", "campaign": "trend"}
SRC = "Source: Business Insider, Inc."
CAPS = {
    "instagram": ("PwC is training 85,000 of its people for the AI age. The skill companies want now is working "
                  "with AI, not fearing it.\n\nSave this and share it with a friend in tech. Start free, link in bio.\n"
                  f"{SRC}\n#AI #careers"),
    "facebook": f"PwC is training 85,000 of its people for the AI age. Learn how AI works, free: {{link}}\n{SRC}",
    "youtube": (f"PwC is training 85,000 people for the AI age\n\nLearn how AI works, free: {{link}}\n{SRC}\n#AI #shorts"),
    "pinterest": f"AI skills companies want now\nPwC is training 85,000 of its people for the AI age. {SRC}",
}


def errors(caps):
    return trend_caption_errors(caps, SCRIPT, KEPT, ITEM)


def test_good_captions_pass():
    assert errors(CAPS) == []


def test_caption_without_source_names_the_platform():
    caps = {**CAPS, "facebook": CAPS["facebook"].replace(SRC, "")}
    assert any(e.startswith("facebook:") and "Source:" in e for e in errors(caps))


def test_caption_missing_one_outlet_fails():
    caps = {**CAPS, "instagram": CAPS["instagram"].replace(", Inc.", "")}
    assert any(e.startswith("instagram:") and "Inc." in e for e in errors(caps))


def test_banned_phrase_fails():
    caps = {**CAPS, "facebook": CAPS["facebook"].replace("free:", "free certificate:")}
    assert any("free certificate" in e for e in errors(caps))


def test_number_not_in_evidence_fails():
    caps = {**CAPS, "instagram": CAPS["instagram"].replace("85,000", "90,000")}
    assert any("90" in e for e in errors(caps))


def test_required_platforms():
    caps = {k: v for k, v in CAPS.items() if k != "youtube"}
    assert "youtube: caption is missing" in errors(caps)


def test_fill_puts_the_trend_utm_link_in():
    filled = fill(CAPS, SCRIPT, ITEM)
    assert "utm_source=facebook" in filled["facebook"] and "utm_campaign=trend-2026-11-25" in filled["facebook"]
    assert "{link}" not in filled["youtube"]
