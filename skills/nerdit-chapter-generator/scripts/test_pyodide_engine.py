"""The pinned Pyodide engine (Plan C Task 1). Engine tests skip, with the reason, when it is not installed."""
import pytest

from pyodide_engine import engine_available, run_job

AVAILABLE, REASON = engine_available()
engine = pytest.mark.skipif(not AVAILABLE, reason=REASON)


def steps(*codes, fresh=()):
    return [{"id": str(i), "code": c, "fresh": i in fresh} for i, c in enumerate(codes)]


def test_engine_reports_unavailable_for_an_empty_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("NERDIT_PYODIDE_DIR", str(tmp_path))
    ok, reason = engine_available()
    assert ok is False
    assert "npm ci" in reason


@engine
def test_shared_and_fresh_namespaces():
    res = run_job({"files": {}, "steps": steps("x = 2", "print(x)", "print(x)", fresh={2}), "probe": []})
    a, b, c = res["results"]
    assert a["error"] is None and b["stdout"] == "2"
    assert c["error"] == "NameError: name 'x' is not defined"


@engine
def test_files_are_readable():
    res = run_job({"files": {"t.csv": "a\n1\n"}, "steps": steps("print(open('t.csv').read().strip())"),
                   "probe": []})
    assert res["results"][0]["stdout"] == "a\n1"


@engine
def test_probe_reports_versions():
    res = run_job({"files": {}, "steps": [], "probe": ["numpy", "nosuchmod"]})
    assert isinstance(res["versions"]["numpy"], str) and res["versions"]["numpy"]
    assert res["versions"]["nosuchmod"] is None


@engine
def test_figures_are_counted():
    res = run_job({"files": {}, "steps": steps("import matplotlib.pyplot as plt\nplt.plot([1, 2])"), "probe": []})
    assert res["results"][0]["error"] is None
    assert res["results"][0]["figures"] == 1
