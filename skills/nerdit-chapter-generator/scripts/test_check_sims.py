import json

import check_sims as cs

MODEL = '''def simulate(path, converter):
    code = {"lines": ['@app.route("/files/' + converter + '")', "def show_file(filename):"], "highlight": [0]}
    if path == "":
        return {"ok": False, "result": "not matched: 404 Not Found", "why": "Nothing comes after /files/.", "code": code}
    pieces = path.split("/")
    if converter == "<filename>" and len(pieces) > 1:
        return {"ok": False, "result": "not matched: 404 Not Found", "why": "A plain part stops at the next slash.",
                "picture": {"type": "pieces", "items": ["files"] + pieces, "take": [1, 1], "takeLabel": "takes " + pieces[0],
                            "left": [2, len(pieces)], "leftLabel": "left over"},
                "details": [["Left over", "/" + "/".join(pieces[1:])]], "code": code}
    return {"ok": True, "result": "matched", "why": "path also accepts slashes.",
            "picture": {"type": "pieces", "items": ["files"] + pieces, "take": [1, len(pieces)],
                        "takeLabel": "filename = " + path}, "code": code}
'''
SPEC = {
    "controls": [{"id": "path", "type": "text", "label": "Path after /files/", "value": "notes/week1.txt"},
                 {"id": "converter", "type": "choice", "label": "Converter",
                  "options": ["<filename>", "<path:filename>"], "value": "<filename>"}],
    "examples": {"control": "path", "values": ["report.txt", "a/b/c.txt"]},
    "predict": {"question": "Does /files/notes/week1.txt reach the view?", "inputs": {"converter": "<filename>"},
                "options": ["Yes", "No, 404"], "answer": 1},
    "challenge": "Find a path that matches only with <path:filename>.",
    "tests": [{"inputs": {"path": "report.txt"}, "ok": True},
              {"inputs": {"path": "notes/week1.txt"}, "ok": False, "result": "not matched"},
              {"inputs": {"path": "notes/week1.txt", "converter": "<path:filename>"}, "ok": True}],
}


def encode_spec(spec):
    return json.dumps(spec).replace("<", "\\u003c")


def lesson(spec=SPEC, model=MODEL, loader=True, count=1):
    sim = ('<div class="nerdit-sim"><div class="nerdit-sim-head">Experiment</div><p class="nerdit-sim-goal">Goal.</p>'
           '<p class="nerdit-sim-note">A teaching model of the rule; not a live Flask server.</p>'
           f'<script type="application/json" class="nerdit-sim-spec">{encode_spec(spec)}</script>'
           f'<script type="text/plain" class="nerdit-sim-model">{model.replace("<", chr(92) + "x3c")}</script></div>')
    page = '<div class="nerdit-wrapper nerdit-simple"><section><h2>1 — Paths</h2>' + sim * count + '</section></div>'
    return page + ('<script src="/nerdit-sim.js"></script>' if loader else "")


def spec_with(**changes):
    return {**json.loads(json.dumps(SPEC)), **changes}


def test_a_working_experiment_passes():
    assert cs.check_lesson(lesson()) == []


def test_a_lesson_without_an_experiment_is_not_judged():
    assert cs.check_lesson("<p>No experiment here.</p>") == []


def test_the_lesson_must_load_the_renderer_and_hold_one_experiment():
    assert any("/nerdit-sim.js" in p for p in cs.check_lesson(lesson(loader=False)))
    assert any("one experiment per lesson" in p for p in cs.check_lesson(lesson(count=2)))


def test_simulate_takes_exactly_the_control_ids():
    bad = MODEL.replace("def simulate(path, converter):", "def simulate(path):")
    assert any("control ids" in p for p in cs.check_lesson(lesson(model=bad)))


def test_a_model_that_crashes_on_an_edge_fails():
    # An empty text box is always tried: this model splits before checking for it.
    bad = MODEL.replace('    if path == "":\n', '    path[0]\n    if path == "":\n')
    assert any("path = ''" in p and "IndexError" in p for p in cs.check_lesson(lesson(model=bad)))


def test_every_result_says_why_in_words():
    bad = MODEL.replace('"why": "path also accepts slashes."', '"why": ""')
    assert any("why" in p for p in cs.check_lesson(lesson(model=bad)))


def test_a_picture_the_renderer_cannot_draw_fails():
    bad = MODEL.replace('"take": [1, len(pieces)]', '"take": [1, 9]')
    assert any("take" in p for p in cs.check_lesson(lesson(model=bad)))
    bad = MODEL.replace('"type": "pieces", "items": ["files"] + pieces, "take": [1, 1]', '"type": "spiral", "take": [1, 1]')
    assert any("picture type" in p for p in cs.check_lesson(lesson(model=bad)))


def test_tests_must_agree_with_the_model_and_show_both_outcomes():
    wrong = spec_with(tests=[*SPEC["tests"][:2], {"inputs": {"path": "a/b"}, "ok": True}])
    assert any("test 3" in p and "ok=True" in p for p in cs.check_lesson(lesson(spec=wrong)))
    same = spec_with(tests=[{"inputs": {"path": p}, "ok": True} for p in ("a.txt", "b.txt", "c.txt")])
    assert any("both outcomes" in p for p in cs.check_lesson(lesson(spec=same)))


def test_the_spec_needs_a_prediction_and_a_new_challenge():
    no_answer = spec_with(predict={**SPEC["predict"], "answer": 5})
    assert any("predict" in p for p in cs.check_lesson(lesson(spec=no_answer)))
    assert any("challenge" in p for p in cs.check_lesson(lesson(spec=spec_with(challenge=""))))


def test_a_model_may_only_import_what_the_browser_has():
    bad = "import os\n" + MODEL
    assert any("imports os" in p for p in cs.check_lesson(lesson(model=bad)))


def test_pictures_of_every_type_are_checked():
    assert cs.picture_problems({"type": "flow", "steps": ["Browser", "Route", "View"], "reached": 1}) == []
    assert cs.picture_problems({"type": "compare", "columns": [
        {"title": "GET", "lines": ["in the URL"], "verdict": "visible", "ok": False},
        {"title": "POST", "lines": ["in the body"], "verdict": "hidden", "ok": True}]}) == []
    assert cs.picture_problems({"type": "bars", "items": [{"label": "Vesu", "value": 12}]}) == []
    assert cs.picture_problems({"type": "table", "head": ["id", "branch"], "rows": [["E1", "Vesu"]], "mark": [0]}) == []
    assert cs.picture_problems({"type": "compare", "columns": [{"title": "only one"}]})
    assert cs.picture_problems({"type": "table", "head": ["a"], "rows": [["x", "y"]]})


def test_cli(tmp_path, capsys):
    course = tmp_path / "course.json"
    course.write_text(json.dumps({"lessons": [{"id": "L1", "content": lesson(loader=False)}]}), encoding="utf-8")
    assert cs.main(["--course", str(course)]) == 1
    assert "FAIL L1: sim:" in capsys.readouterr().out


def test_a_script_that_looks_like_a_tag_fails():
    # The admin's DOMPurify drops <script> text such as "<filename>": the experiment vanished on publish.
    raw = lesson().replace(encode_spec(SPEC), json.dumps(SPEC))
    assert any("\\u003c" in p and "vanish" in p for p in cs.check_lesson(raw))
    raw = lesson().replace(chr(92) + "x3c", "<")
    assert any("\\x3c" in p for p in cs.check_lesson(raw))

