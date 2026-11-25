import json
import subprocess
from datetime import date

import imageio_ffmpeg
from PIL import Image

from compose import caption_groups, caption_png, card_png, compose, endcard_png
from runs import new_run

FF = imageio_ffmpeg.get_ffmpeg_exe()


def ink_gaps(png, pill):
    """Rows of dark text inside the pill: (gap above the ink, gap below it)."""
    im = Image.open(png).convert("RGBA")
    x0, y0, x1, y1 = [int(v) for v in pill]
    rows = [y for y in range(y0, y1) if any(
        sum(im.getpixel((x, y))[:3]) < 400 and im.getpixel((x, y))[3] > 0 for x in range(x0, x1, 2))]
    return rows[0] - y0, y1 - rows[-1]


def test_caption_text_is_centred_in_the_pill(tmp_path):
    for words in (["your", "company", "will"], ["signal", "of", "what"]):
        info = caption_png(tmp_path / "c.png", words)
        top_gap, bottom_gap = ink_gaps(tmp_path / "c.png", info["pill"])
        assert abs(top_gap - bottom_gap) <= 4, (words, top_gap, bottom_gap)


def test_every_pill_has_the_same_height(tmp_path):
    a = caption_png(tmp_path / "a.png", ["no", "descenders", "here"])["pill"]
    b = caption_png(tmp_path / "b.png", ["only", "gyp"])["pill"]
    assert a[3] - a[1] == b[3] - b[1]


def test_numbers_are_orange(tmp_path):
    caption_png(tmp_path / "n.png", ["85,000", "of", "its"])
    im = Image.open(tmp_path / "n.png").convert("RGBA")
    assert any(abs(r - 0xF9) < 20 and abs(g - 0x73) < 30 and b < 60 and a > 200 for r, g, b, a in im.get_flattened_data())


def test_news_card_sits_below_the_face(tmp_path):
    info = card_png(tmp_path / "card.png", "AI & JOBS  ·  25 NOV 2026", "PwC is training 85,000 staff for the AI age",
                    ["Business Insider", "Inc."])
    assert info["card"][1] >= 1000


def test_end_card_button_is_below_the_meta_line(tmp_path):
    info = endcard_png(tmp_path / "e.png", {"title": "Machine Learning Fundamentals", "lessons": 12})
    assert info["button_top"] > info["meta_bottom"]


def test_caption_groups_break_at_three_words_and_sentence_ends():
    words = [{"w": w, "s": i, "e": i + .5} for i, w in enumerate("PwC is training. Not a small tech team".split())]
    assert [[x["w"] for x in g] for g in caption_groups(words)] == [
        ["PwC", "is", "training."], ["Not", "a", "small"], ["tech", "team"]]


def test_compose_short_clip_renders(tmp_path):
    run = new_run("daily", "test", date(2026, 11, 25))
    subprocess.run([FF, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=size=720x1280:rate=24:duration=3",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=3", "-shortest", "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", str(run / "clips" / "clip1.mp4")], check=True)
    (run / "transcript.json").write_text(json.dumps(
        [{"w": "Learn", "s": 0.2, "e": 0.6}, {"w": "AI", "s": 0.7, "e": 1.0}, {"w": "now.", "s": 1.1, "e": 1.5}]))
    (run / "script.json").write_text(json.dumps({
        "kind": "daily", "line": "Learn AI now. Link in bio.",
        "card": {"chip": "AI & JOBS  ·  25 NOV 2026", "facts": ["PwC is training 85,000 staff"],
                 "sources": ["Business Insider", "Inc."]},
        "course": {"id": "x", "title": "Machine Learning Fundamentals", "lessons": 12, "url": "https://nerdit.in/course/x/preview"}}))
    reel = compose(run)
    probe = subprocess.run([FF, "-i", str(reel)], capture_output=True, text=True).stderr
    assert "1080x1920" in probe
    assert "Duration: 00:00:03" in probe or "Duration: 00:00:02.9" in probe
    assert json.loads((run / "checks.json").read_text())["reel_sha256"]
