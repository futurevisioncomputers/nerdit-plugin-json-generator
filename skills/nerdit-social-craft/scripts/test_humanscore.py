import re

from humanscore import human_errors, human_score

# The good LinkedIn caption from nerdit-social-posts/scripts/test_captions.py (link shortened).
OK_LI = ("Installing packages globally is a common beginner mistake. A virtual environment keeps each project's "
         "packages apart, so a project is faster to set up again.\n\nFree lesson: "
         "https://nerdit.in/course/course-demo-1/preview?utm_source=linkedin\n#Python #FastAPI")
SLOP = ("In today's fast-paced world, we leverage cutting-edge, robust, seamless tools to unlock a transformative "
        "journey. Moreover, it's not just a course, it's a game-changer!")


def test_plain_caption_passes():
    assert human_errors(OK_LI, "linkedin") == []


def test_slop_caption_is_flagged():
    errs = human_errors(SLOP, "linkedin")
    assert len(errs) == 1
    m = re.fullmatch(r"linkedin: reads machine-written \(human score (\d+); at least 50; weakest: [A-Z ]+\)", errs[0])
    assert m and int(m.group(1)) < 50


def test_checks_are_named():
    assert set(human_score(OK_LI)["checks"]) == {"BURSTINESS", "SPECIFICITY", "SLOP DENSITY", "FINGERPRINT", "VOICE"}
