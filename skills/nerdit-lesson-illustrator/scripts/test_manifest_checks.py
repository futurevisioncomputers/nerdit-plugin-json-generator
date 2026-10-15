from fixture_course import PLAN, course
from manifest import accept, add_slots, new_manifest, record_checks, render_prompts


def converted():
    m = new_manifest(course(), "course.json")
    assert add_slots(m, course(), PLAN) == []
    for s in m["images"]:
        s.update(status="converted", width=1200, height=800, bytes=90_000)
    return m


def test_pass_and_fail_update_status_and_reason():
    m = converted()
    errors = record_checks(m, [
        {"id": "load-basics-01-img1", "result": "pass", "reason": "Shows the conveyor clearly."},
        {"id": "old-style-02-img1", "result": "fail", "reason": "Label reads 'Strat'.",
         "revisedSubject": "A student opening a notebook beside a laptop, label spelled Start."},
    ])
    assert errors == []
    a, b = m["images"]
    assert a["status"] == "passed" and a["check"]["result"] == "pass"
    assert b["status"] == "failed" and b["check"]["reason"] == "Label reads 'Strat'."
    assert b["prompt"].startswith("A student opening a notebook beside a laptop, label spelled Start.")
    assert "#0B1F3A" in b["prompt"]
    out = render_prompts(m)
    assert "## Regenerate" in out and "Why it failed: Label reads 'Strat'." in out


def test_fail_needs_reason_and_unknown_ids_and_bad_status_are_errors():
    m = converted()
    m["images"][1]["status"] = "planned"
    errors = record_checks(m, [
        {"id": "load-basics-01-img1", "result": "fail"},
        {"id": "nope", "result": "pass", "reason": "x"},
        {"id": "old-style-02-img1", "result": "pass", "reason": "x"},
        {"id": "load-basics-01-img1", "result": "maybe", "reason": "x"},
    ])
    assert any("a fail needs a reason" in e for e in errors)
    assert any("unknown image id nope" in e for e in errors)
    assert any("status planned cannot be checked" in e for e in errors)
    assert any("result must be pass or fail" in e for e in errors)


def test_accept_overrides_a_fail():
    m = converted()
    record_checks(m, [{"id": "load-basics-01-img1", "result": "fail", "reason": "Too dark."}])
    assert accept(m, "load-basics-01-img1") == []
    assert m["images"][0]["status"] == "passed"
    assert m["images"][0]["check"]["reason"] == "accepted by reviewer"
    assert accept(m, "old-style-02-img1") == [] and accept(m, "nope") == ["unknown image id nope"]
