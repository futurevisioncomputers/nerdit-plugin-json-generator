"""Every checker that runs lesson or pack code gives it a headless Matplotlib backend.

plt.show() on a desktop backend opens a window and blocks until the run times out, so a writer
would drop plt.show() from code the learner downloads. test_lesson_runs.py and
test_check_offline_outputs.py run the real thing; this covers the remaining runners.
"""
import re
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent


@pytest.mark.parametrize("module", ["lesson_runs.py", "check_offline_outputs.py", "check_files.py",
                                    "check_capstone.py"])
def test_every_child_environment_sets_mplbackend_agg(module):
    source = (HERE / module).read_text(encoding="utf-8")
    envs = re.findall(r"env = \{\*\*os\.environ,.*?\}", source, re.S)
    assert envs, module
    for env in envs:
        assert re.search(r"""['"]MPLBACKEND['"]: ['"]Agg['"]""", env), (module, env)


@pytest.mark.parametrize("module", ["lesson_runs.py", "check_offline_outputs.py", "check_files.py",
                                    "check_capstone.py"])
def test_warnings_as_errors_still_let_plt_show_run(module):
    """Agg's plt.show() warns "FigureCanvasAgg is non-interactive"; every -W error is followed by
    the one ignore for it, so any other warning still fails the run."""
    source = (HERE / module).read_text(encoding="utf-8")
    calls = re.findall(r"""['"]-W['"], ['"]error['"](?:, \*?[A-Z_]+)?""", source)
    assert calls, module
    for call in calls:
        assert "SHOW_OK" in call, (module, call)
