"""Story video v3: vector/diagram/B-roll scenes, no quizzes, Google voice, Pexels B-roll (no network, no browser)."""
import array, base64, io, json, wave
from pathlib import Path

import pytest

import broll
import pronounce
import build_video
import render
import stage
import storyplan
import timeline
import voice

FIG = '<svg viewBox="0 0 10 10" role="img" aria-label="Three steps"><text>A</text></svg>'
VEC = ('<svg class="nerdit-anim" viewBox="0 0 480 360" role="img" aria-label="Enquiry flow">'
       '<g class="na-show" style="--d:0s"><rect x="10" y="10" width="100" height="40" fill="var(--bg-soft)"/>'
       '<text x="20" y="35">Enquiry</text></g>'
       '<g class="na-slide" style="--d:.8s"><text x="200" y="35">Demo 12</text></g></svg>')


def make_course(tmp_path: Path, n=5) -> Path:
    lessons = [{"id": f"l{i}", "title": f"Lesson {i}",
                "content": f"<p>Lesson {i}: an Enquiry leads to a Demo; 12 learners and 4 rows.</p>"
                f'<div class="nerdit-figure" data-nerdit-img="l{i}-visual-1">{FIG}</div>'} for i in range(1, n + 1)]
    path = tmp_path / "course.json"
    path.write_text(json.dumps({"id": "c", "title": "C", "lessons": lessons}), encoding="utf-8")
    return path


def filled_plan(tmp_path: Path) -> tuple[dict, Path, Path]:
    images, course = tmp_path / "images", make_course(tmp_path)
    plan = json.loads(storyplan.scaffold(images, course).read_text(encoding="utf-8"))
    plan["intro"].update(points=["one", "two"], narration="Hello, इस video का intro.")
    plan["recap"].update(points=["a", "b", "c"], narration="Summary: data एक recorded observation है.")
    for s in plan["scenes"]:
        s.update(narration="ये data का small scene है.", keyIdea="An enquiry is data.", terms=["data"])
        (images / "video" / "vectors" / s["vector"]).write_text(VEC, encoding="utf-8")
    plan["scenes"][0]["myth"] = {"wrong": "w", "right": "r", "narration": "Wrong idea, right idea."}
    return plan, images, course


def check(plan, images, course):
    return storyplan.check_plan(plan, images / "video", storyplan.lesson_figures(course, images),
                                storyplan.lesson_texts(course))


# ---- plan ----

def test_scaffold_starts_one_vector_scene_per_lesson(tmp_path):
    images, course = tmp_path / "images", make_course(tmp_path)
    plan = json.loads(storyplan.scaffold(images, course).read_text(encoding="utf-8"))
    assert plan["version"] == 3 and plan["voice"]["engine"] == "google"
    assert [(s["kind"], s["vector"], s["title"]) for s in plan["scenes"]][0] == ("vector", "l1-v1.svg", "Lesson 1")
    assert {"id": "l3-visual-1", "lessonId": "l3", "label": "Three steps"} in plan["availableFigures"]
    assert (images / "video" / "vectors").is_dir()
    with pytest.raises(SystemExit):
        storyplan.scaffold(images, course)


def test_filled_plan_passes(tmp_path):
    assert check(*filled_plan(tmp_path)) == []


def test_quizzes_are_refused(tmp_path):
    plan, images, course = filled_plan(tmp_path)
    plan["scenes"][1]["quiz"] = {"question": "q?"}
    assert any("the video has no quizzes" in e for e in check(plan, images, course))


def test_vector_rules():
    assert storyplan.check_vector(VEC, "Enquiry Demo 12") == []
    still = VEC.replace(' class="nerdit-anim"', "").replace("na-show", "x").replace("na-slide", "y")
    errors = storyplan.check_vector(still, "Enquiry Demo 12")
    assert any("nerdit-anim" in e for e in errors) and any("no moving part" in e for e in errors)
    tall = VEC.replace('viewBox="0 0 480 360"', 'viewBox="0 0 360 600"')
    assert any("4:3" in e for e in storyplan.check_vector(tall, "Enquiry Demo 12"))
    assert storyplan.check_vector(VEC, "Enquiry Demo") == ["draws numbers or names the lesson does not contain: 12"]
    bad = VEC.replace('fill="var(--bg-soft)"', 'fill="#ff0000"').replace("</svg>", "<style>x{}</style></svg>")
    errors = storyplan.check_vector(bad, "Enquiry Demo 12")
    assert any("hex colour" in e for e in errors) and any("<style>" in e for e in errors)


def test_missing_vector_file_and_diagram_and_broll_rules(tmp_path):
    plan, images, course = filled_plan(tmp_path)
    plan["scenes"][0]["vector"] = "nope.svg"
    plan["scenes"][1] = {**plan["scenes"][1], "kind": "diagram", "figure": "l2-visual-1"}
    plan["scenes"][2] = {**plan["scenes"][2], "kind": "broll", "query": "", "focus": [{"x": 0.5, "y": 0.5}]}
    errors = check(plan, images, course)
    assert any("write the vector to video/vectors/nope.svg" in e for e in errors)
    assert not any("scene 2" in e for e in errors)
    assert any("broll needs a search query" in e for e in errors) and any("no camera focus" in e for e in errors)


def test_broll_is_kept_to_a_minority(tmp_path):
    plan, images, course = filled_plan(tmp_path)
    for s, q in zip(plan["scenes"][:2], ("classroom", "office")):
        s.update(kind="broll", query=q, focus=[])
    assert any("are B-roll" in e for e in check(plan, images, course))


def test_check_catches_bad_scenes(tmp_path):
    plan, images, course = filled_plan(tmp_path)
    s = plan["scenes"]
    s[0]["narration"] = ""
    s[2]["terms"] = ["model"]
    s[3]["focus"] = [{"x": 1.4, "y": 0.5, "at": "बारिश"}]
    s[4]["keyIdea"] = "x" * 120
    plan["intro"]["points"] = ["only one"]
    errors = check(plan, images, course)
    for needle in ("scene 1: narration is empty", "term 'model' is never spoken", "focus x and y", "focus 'at'",
                   "keyIdea is 120 chars", "intro: give 2-4 points"):
        assert any(needle in e for e in errors), needle


def test_numbers_and_english_share(tmp_path):
    plan, images, course = filled_plan(tmp_path)
    plan["scenes"][0]["narration"] = "12 learners में से 87 present थे, यही data है."
    assert check(plan, images, course) == ["scene 1: number 87 is not in the lesson text"]
    plan["scenes"][0]["narration"] = "हर सुबह कोई दरवाज़े पर खड़ा होकर लिखता है कि कौन आया, यही data है."
    assert any("7% English words" in e for e in check(plan, images, course))


def test_old_plans_are_refused(tmp_path):
    assert storyplan.check_plan({"version": 2}, tmp_path) == ["plan.version must be 3; delete plan.json and scaffold again"]


# ---- voice ----

def write_plan(tmp_path):
    plan, images, _ = filled_plan(tmp_path)
    (images / "video" / "plan.json").write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    return plan, images


def test_clips_follow_speaking_order_without_quizzes(tmp_path):
    plan, _, _ = filled_plan(tmp_path)
    plan["scenes"][1]["quiz"] = {"narrationQ": "x", "narrationA": "y"}
    ids = [c["id"] for c in voice.clips(plan)]
    assert ids[:4] == ["intro", "s1", "s1-myth", "s2"] and ids[-1] == "recap"
    assert not any(i.endswith(("-q", "-a")) for i in ids)


def silent_wav(seconds=1.0, rate=24000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(2 * int(rate * seconds)))
    return buf.getvalue()


def test_google_engine_uses_the_key_from_the_environment(tmp_path, monkeypatch):
    plan, images = write_plan(tmp_path)
    monkeypatch.setattr(voice, "ffmpeg", lambda: "ff")
    monkeypatch.setenv("GOOGLE_TTS_API_KEY", "k123")
    calls, bodies = [], []

    def fake_request(path, body, key):
        bodies.append((path, body, key))
        return {"audioContent": base64.b64encode(silent_wav(2.0)).decode()}

    def runner(cmd, **kw):
        calls.append(cmd)
        Path(cmd[-1]).write_bytes(silent_wav(2.0))

    google = lambda text, name, rate, wav, key: voice.google_clip(text, name, rate, wav, key, request=fake_request)
    voice.run(images, None, None, None, runner=runner, google=google)
    path, body, key = bodies[0]
    assert (path, key) == ("text:synthesize", "k123")
    assert body["voice"] == {"languageCode": "hi-IN", "name": "hi-IN-Chirp3-HD-Aoede"}
    assert body["audioConfig"]["audioEncoding"] == "LINEAR16" and body["input"]["text"] == "Hello, इस video का intro."
    words = json.loads((images / "video" / "audio" / "intro.words.json").read_text(encoding="utf-8"))
    assert [w["w"] for w in words] == ["Hello", "इस", "video", "का", "intro"]
    assert len(calls) == len(voice.clips(plan))


def test_google_engine_needs_a_key(tmp_path, monkeypatch):
    _, images = write_plan(tmp_path)
    monkeypatch.setattr(voice, "ffmpeg", lambda: "ff")
    monkeypatch.delenv("GOOGLE_TTS_API_KEY", raising=False)
    with pytest.raises(SystemExit, match="GOOGLE_TTS_API_KEY"):
        voice.run(images, "google", None, None, runner=lambda *a, **k: None)


def test_edge_engine_keeps_word_timings(tmp_path, monkeypatch):
    plan, images = write_plan(tmp_path)
    monkeypatch.setattr(voice, "ffmpeg", lambda: "ff")

    async def fake_edge(text, name, rate, mp3):
        return [{"t": 0.1, "d": 0.3, "w": text.split()[0]}]

    calls = []
    voice.run(images, "edge", None, None, runner=lambda cmd, **kw: calls.append(cmd), edge=fake_edge)
    assert len(calls) == len(voice.clips(plan))


def test_edge_speaks_code_words_respelled(tmp_path, monkeypatch):
    plan, images = write_plan(tmp_path)
    plan["scenes"][0]["narration"] = "json.dumps dict को JSON text बनाता है।"
    (images / "video" / "plan.json").write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(voice, "ffmpeg", lambda: "ff")
    sent = []

    async def fake_edge(text, name, rate, mp3):
        sent.append(text)
        return []

    voice.run(images, "edge", None, None, runner=lambda cmd, **kw: None, edge=fake_edge)
    assert "Jason dot dumps dictionary को Jason text बनाता है।" in sent


def test_spoken_respells_code_words():
    say = pronounce.spoken
    assert say("Python dict और json.loads") == "Python dictionary और Jason dot loads"
    assert say("max_tokens, request_id, __init__, main.py, print()") == \
        "max tokens, request I D, dunder init, main dot P Y, print"
    assert say("HTTPException, LLM_API_KEY, CONNECT_TIMEOUT") == "H T T P Exception, L L M A P I key, connect timeout"
    assert say("SSE, PRICES, DONE, Kabir, A loop repeats steps.") == "S S E, prices, done, Kabir, A loop repeats steps."
    assert say("httpx2 AsyncClient") == "H T T P X two a-sync Client"
    assert say("इस video में 12 rows हैं।") == "इस video में twelve rows हैं।"


# A Hindi voice reads digits in Hindi ("बारह"); the owner wants every number said in English.
def test_spoken_says_every_number_in_english():
    say = pronounce.spoken
    assert say("2000 messages, 2,000 rows, 1980 drafts") ==         "two thousand messages, two thousand rows, one thousand nine hundred eighty drafts"
    assert say("connect timeout 2.0 s, read 10.0 s, 0.5 s") ==         "connect timeout two point zero s, read ten point zero s, zero point five s"
    assert say("429, 502 और 504 errors") == "four hundred twenty-nine, five hundred two और five hundred four errors"
    assert say("M7 पर 14.0 s, M12 को 3.0 s") == "M seven पर fourteen point zero s, M twelve को three point zero s"
    assert say("30% English, 1,23,456 rows") == "thirty percent English, one hundred twenty-three thousand four hundred fifty-six rows"
    assert say("0 errors, 100 calls, 1000000 tokens") == "zero errors, one hundred calls, one million tokens"


def test_key_term_found_when_spoken_respelled():
    words = [{"t": 0.2, "w": "Jason"}, {"t": 0.6, "w": "dot"}, {"t": 0.9, "w": "dumps"}, {"t": 1.4, "w": "dictionary"}]
    assert timeline.first_spoken(words, "json.dumps", 1.0) == 1.2
    assert timeline.first_spoken(words, "dict", 1.0) == 2.4


def test_clone_engine_cleans_refs_then_calls_the_venv_once(tmp_path, monkeypatch):
    plan, images = write_plan(tmp_path)
    monkeypatch.setattr(voice, "ffmpeg", lambda: "ff")
    calls = []
    voice.run(images, "clone", "venv/python.exe", Path("ref.wav"),
              runner=lambda cmd, **kw: calls.append((cmd, kw.get("env", {}).get("COQUI_TOS_AGREED"))))
    assert calls[0][0][-1].endswith("ref1-%02d.wav")
    assert calls[1][0][0] == "venv/python.exe" and calls[1][1] == "1"
    assert len(calls) == 2 + len(voice.clips(plan))


def test_estimated_words_fill_the_clip():
    words = voice.estimate_words("एक दो तीन चार", 2.0)
    assert [w["w"] for w in words] == ["एक", "दो", "तीन", "चार"]
    assert words[0]["t"] == 0.15 and words[-1]["t"] + words[-1]["d"] < 2.0


def test_chunks_keep_every_word_within_the_clone_limit():
    text = "पहला sentence है. " + ", ".join(["records बहुत सारे हैं"] * 12) + ". आखिरी।"
    parts = voice.chunks(text)
    assert all(len(p) <= voice.CLONE_LIMIT for p in parts) and " ".join(parts).split() == text.split()


def test_prepare_refs_cleans_and_splits_every_recording(tmp_path):
    rec = tmp_path / "rec"
    rec.mkdir()
    for name in ("a.m4a", "b.wav", "notes.txt"):
        (rec / name).write_bytes(b"x")
    calls = []
    voice.prepare_refs(rec, tmp_path / "out", "ff", runner=lambda cmd, **kw: calls.append(cmd))
    assert [c[5] for c in calls] == [str(rec / "a.m4a"), str(rec / "b.wav")]


# ---- B-roll ----

class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_broll_picks_a_landscape_mp4_and_records_credit(tmp_path):
    plan, images = write_plan(tmp_path)
    plan["scenes"][2].update(kind="broll", query="students in classroom", focus=[])
    (images / "video" / "plan.json").write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    videos = {"videos": [
        {"duration": 3, "video_files": [{"file_type": "video/mp4", "width": 1280, "link": "https://v/short"}]},
        {"duration": 12, "url": "https://pexels.com/v/1", "user": {"name": "Asha"},
         "video_files": [{"file_type": "video/mp4", "width": 3840, "link": "https://v/4k"},
                         {"file_type": "video/mp4", "width": 1920, "link": "https://v/fhd"},
                         {"file_type": "video/mp4", "width": 1280, "link": "https://v/hd"}]}]}
    seen = []

    def opener(req, timeout):
        seen.append((req.full_url, req.headers.get("Authorization")))
        return FakeResponse(json.dumps(videos).encode() if "api.pexels.com" in req.full_url else b"MP4")

    assert broll.fetch(images, opener=opener, key="pk") == ["s3"]
    assert "query=students+in+classroom" in seen[0][0] and seen[0][1] == "pk" and seen[1][0] == "https://v/hd"
    assert (images / "video" / "broll" / "s3.mp4").read_bytes() == b"MP4"
    credits = json.loads((images / "video" / "broll" / "credits.json").read_text(encoding="utf-8"))
    assert credits["s3"]["by"] == "Asha" and credits["s3"]["page"] == "https://pexels.com/v/1"
    assert broll.fetch(images, opener=opener, key="pk") == []      # cached until the query changes


def test_broll_overlay_fills_the_box_only_during_its_window():
    cmd = build_video.broll_command("ff", Path("v.mp4"), [{"scene": 3, "start": 40.0, "end": 52.5}],
                                    [Path("s3.mp4")], Path("o.mp4"))
    graph = cmd[cmd.index("-filter_complex") + 1]
    assert "scale=720:540:force_original_aspect_ratio=increase,crop=720:540" in graph
    assert "overlay=40:104:enable='between(t,40.0,52.5)'" in graph and "setpts=PTS-STARTPTS+40.0/TB" in graph
    assert cmd[cmd.index("-stream_loop") + 1] == "-1"


# ---- timeline, stage, render, build ----

def build_tl(tmp_path):
    plan, _, _ = filled_plan(tmp_path)
    plan["scenes"][0]["focus"] = [{"x": 0.2, "y": 0.3, "zoom": 1.5, "at": "data"}]
    plan["scenes"][2].update(kind="broll", query="classroom", focus=[])
    clips = {c["id"]: {"dur": 2.0, "words": [{"t": 0.1, "d": 0.3, "w": c["text"].split()[0]},
                                             {"t": 1.0, "d": 0.3, "w": "data"}]} for c in voice.clips(plan)}
    return plan, timeline.build(plan, clips)


def test_timeline_orders_cards_scenes_and_myths(tmp_path):
    plan, tl = build_tl(tmp_path)
    kinds = [(s["kind"], s.get("scene")) for s in tl["segments"]]
    assert kinds[:4] == [("intro", None), ("scene", 1), ("myth", 1), ("scene", 2)] and kinds[-1] == ("recap", None)
    assert all(a["end"] == b["start"] for a, b in zip(tl["segments"], tl["segments"][1:]))
    assert not any(s["kind"] == "quiz" for s in tl["segments"])
    s3 = next(s for s in tl["segments"] if s.get("scene") == 3)
    assert tl["broll"] == [{"scene": 3, "start": s3["start"], "end": s3["end"]}]
    scene = tl["segments"][1]
    assert scene["focus"][0]["t"] == pytest.approx(scene["start"] + timeline.PAD_IN + 1.0 - timeline.MOVE / 2)


def test_stage_draws_vectors_and_leaves_broll_windows_empty(tmp_path):
    plan, tl = build_tl(tmp_path)
    plan["scenes"][1]["keyIdea"] = "a </script> b"
    svgs = [VEC, VEC, None, VEC, VEC]
    page = stage.build_stage(plan, tl, svgs, "/*lesson css*/")
    data = json.loads(page.split("window.DATA = ")[1].split(";</script>")[0].replace("<\\/", "</"))
    assert [("srcdoc" in s) for s in data["scenes"]] == [True, True, False, True, True]
    assert "a <\\/script> b" in page and "/*lesson css*/" in page and "quiz" not in page.lower()
    assert "BUILD = 0.8" in page


def test_description_lists_chapters():
    text = timeline.description({"course": "C", "intro": {"points": ["p"]}}, [(0.0, "Introduction"), (75.2, "Two")])
    assert "0:00 Introduction\n1:15 Two" in text and "- p" in text


def test_frame_ranges_and_encode():
    assert render.frame_ranges(10, 3) == [(0, 4), (4, 8), (8, 10)]
    assert "scale=out_range=tv,format=yuv420p" in render.encode_command("ff", 25, Path("o.mp4"))


def test_mix_places_each_clip_at_its_time(tmp_path):
    with wave.open(str(tmp_path / "a.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(build_video.RATE)
        w.writeframes(array.array("h", [1000] * 2400).tobytes())
    out = build_video.mix(tmp_path, [{"clip": "a", "at": 0.5}], 1.0, tmp_path / "mix.wav")
    with wave.open(str(out)) as w:
        samples = array.array("h", w.readframes(w.getnframes()))
    assert samples[11999] == 0 and samples[12000] == 1000 and samples[14400] == 0


def test_mux_adds_music_only_when_given():
    plain = build_video.mux_command("ff", Path("v.mp4"), Path("n.wav"), Path("o.mp4"))
    music = build_video.mux_command("ff", Path("v.mp4"), Path("n.wav"), Path("o.mp4"), Path("m.mp3"))
    assert "amix" not in " ".join(plain) and any("amix=inputs=2" in a for a in music)


def test_one_clip_per_topic_plus_intro_and_recap(tmp_path):
    plan, tl = build_tl(tmp_path)
    for s in plan["scenes"]:
        s["topic"] = 1
    plan["scenes"][1].update(lessonId="l1", topic=1)    # two scenes in l1 topic 1: one clip
    plan["scenes"][2].update(lessonId="l1", topic=2)    # same lesson, next topic: its own clip
    clips = build_video.topic_clips(plan, tl, {"l1": "Lesson One"}, {"l1": {2: "Counting"}})
    assert [c["key"] for c in clips] == ["l1-intro-video", "l1-t1-video", "l1-t2-video", "l4-t1-video",
                                         "l5-t1-video", "l5-recap-video"]
    assert clips[0]["start"] == 0.0 and clips[-1]["end"] == tl["duration"]
    assert all(a["end"] <= b["start"] for a, b in zip(clips, clips[1:]))
    assert clips[2]["title"] == "Counting" and clips[1]["title"] == storyplan.title_case(plan["scenes"][0]["title"])
    assert clips[2]["file"] == "clip-03-l1-t2.mp4" and clips[0]["title"] == "Lesson One: Introduction"
    cmd = build_video.cut_command("ff", Path("story.mp4"), clips[1], Path("c.mp4"))
    assert cmd[cmd.index("-ss") + 1] == f"{clips[1]['start']:.3f}" and "+faststart" in cmd


def test_topics_are_checked():
    scenes = [{"lessonId": "l1", "topic": 1, "narration": "x"}, {"lessonId": "l1", "topic": 2, "narration": "As we saw, y"},
              {"lessonId": "l1", "topic": 1, "narration": "z"}, {"lessonId": "l1", "narration": "q"},
              {"lessonId": "l1", "topic": 9, "narration": "w"}]
    errors = storyplan.check_topics(scenes, {"l1": {1: "A", 2: "B"}})
    assert any("scene 2" in e and "refers back" in e for e in errors)
    assert any("scene 3" in e and "together" in e for e in errors)
    assert any("scene 4" in e and "topic must be" in e for e in errors)
    assert any("scene 5" in e and "no section 9" in e for e in errors)
    assert len(errors) == 4


def test_lesson_topics_read_numbered_sections(tmp_path):
    path = tmp_path / "c.json"
    path.write_text(json.dumps({"lessons": [{"id": "l1", "content": "<h2>1 — 🔍 From a worry</h2><h2>📌 Cheat</h2>"}]}),
                    encoding="utf-8")
    assert storyplan.lesson_topics(path) == {"l1": {1: "From a worry"}}


def test_place_video_puts_each_clip_where_it_belongs():
    import place_video
    course = {"lessons": [
        {"id": "l1", "content": '<div class="nerdit-wrapper"><p>intro</p><section><h2>1 — A</h2><p>a</p></section>'
                                '<section><h2>2 — B</h2></section><section><h2>📌 Quick cheat sheet</h2></section></div>'},
        {"id": "l2", "content": '<div class="nerdit-wrapper"><p>x</p></div>'}]}
    clips = [{"key": "l1-intro-video", "place": "intro", "lessonId": "l1", "topic": None, "title": "Intro"},
             {"key": "l1-t1-video", "place": "topic", "lessonId": "l1", "topic": 1, "title": 'Rates & "counts"'},
             {"key": "l1-t2-video", "place": "topic", "lessonId": "l1", "topic": 2, "title": "B"},
             {"key": "l1-recap-video", "place": "recap", "lessonId": "l1", "topic": None, "title": "Recap"},
             {"key": "l2-t1-video", "place": "topic", "lessonId": "l2", "topic": 1, "title": "C"}]
    course, added = place_video.add_slots(course, clips)
    assert added == [c["key"] for c in clips]
    c1 = course["lessons"][0]["content"]
    at = {c["key"]: c1.find(f'data-nerdit-video="{c["key"]}"') for c in clips[:4]}
    assert c1.index("<p>intro</p>") < at["l1-intro-video"] < c1.index("1 — A")
    assert c1.index("<p>a</p>") < at["l1-t1-video"] < c1.index("2 — B") < at["l1-t2-video"] < at["l1-recap-video"]
    assert at["l1-recap-video"] < c1.index("📌")
    assert 'data-title="Rates &amp; &quot;counts&quot;"></div>' in c1
    assert course["lessons"][1]["content"].endswith('data-nerdit-video="l2-t1-video" data-title="C"></div>\n</div>')
    assert place_video.add_slots(course, clips)[1] == []


def test_lesson_css_loads_the_site_stylesheets():
    assert ".nerdit-anim.na-play .na-show" in stage.lesson_css()


# ---- "Now practise" card (practice files plan §5b) ----

PRACTICE_LESSON = (
    '<h2>Overview</h2><script type="application/json" class="nerdit-files-spec">'
    '{"python": "3.12", "files": [{"name": "L01-practice-starter.py", "from": {"practice": "starters"}},'
    ' {"name": "L01-practice-starter.ipynb", "from": {"practice": "starters"}}]}</script>'
    '<section><h2>1 — Read rows</h2><p>Text.</p><div class="nerdit-predict"><pre data-lang="python"><code>print(1)'
    '</code></pre></div></section>'
    '<section><h2>2 — No practice here</h2><p>Text.</p></section>'
    '<section><h2>Practice</h2><div class="nerdit-practical">'
    '<div class="nerdit-task">Task 1: One.<details class="nerdit-solution"><pre data-lang="python"><code>print(1)'
    '</code></pre></details></div>'
    '<div class="nerdit-task">Task 2: Two.<details class="nerdit-solution"><pre data-lang="python"><code>print(2)'
    '</code></pre></details></div></div></section>')


def practice_course(tmp_path):
    path = tmp_path / "course.json"
    path.write_text(json.dumps({"id": "c", "title": "C", "lessons": [
        {"id": "l1", "title": "Lesson 1", "content": PRACTICE_LESSON}]}), encoding="utf-8")
    return path


def test_lesson_practice_reads_try_its_starter_and_tasks(tmp_path):
    info = storyplan.lesson_practice(practice_course(tmp_path))["l1"]
    assert info == {"tryits": {1: 1, 2: 0}, "starter": "L01-practice-starter.ipynb", "tasks": 2}


def test_scaffold_adds_one_practise_entry_per_topic(tmp_path):
    images = tmp_path / "images"
    plan = json.loads(storyplan.scaffold(images, practice_course(tmp_path)).read_text(encoding="utf-8"))
    assert plan["practise"] == [{"lessonId": "l1", "topic": 1, "tryIt": "", "task": None},
                                {"lessonId": "l1", "topic": 2, "tryIt": "", "task": None}]


def test_check_practise_rules(tmp_path):
    practice = storyplan.lesson_practice(practice_course(tmp_path))
    covered = {("l1", 1), ("l1", 2)}
    good = {"practise": [{"lessonId": "l1", "topic": 1, "tryIt": "predict what print(1) shows", "task": 2}]}
    errors = storyplan.check_practise(good, practice, covered)
    assert errors == ["l1 section 2: no practise card; add a practise entry naming its Try It"]
    bad = {"practise": [{"lessonId": "l1", "topic": 1, "tryIt": "", "task": 3},
                        {"lessonId": "l1", "topic": 2, "tryIt": "fill the blank", "task": None}]}
    text = "\n".join(storyplan.check_practise(bad, practice, covered))
    assert "tryIt is empty" in text and "task 3" in text and "has no Try It" in text and "starter has tasks 1-2" in text


def test_practise_card_names_the_starter_file_and_task(tmp_path):
    practice = storyplan.lesson_practice(practice_course(tmp_path))
    plan = {"practise": [{"lessonId": "l1", "topic": 1, "tryIt": "predict what print(1) shows", "task": 2}]}
    assert storyplan.practise_cards(plan, practice) == {
        ("l1", 1): {"tryIt": "Try It: predict what print(1) shows", "pack": "Pack: L01-practice-starter.ipynb, Task 2"}}


def test_timeline_ends_each_topic_with_its_card_and_the_clip_keeps_it():
    plan = {"intro": {"points": ["a"]}, "recap": {"points": ["b"]},
            "scenes": [{"kind": "vector", "lessonId": "l1", "topic": 1, "title": "One"},
                       {"kind": "vector", "lessonId": "l1", "topic": 1, "title": "One"},
                       {"kind": "vector", "lessonId": "l1", "topic": 2, "title": "Two"}]}
    clips = {k: {"dur": 2.0, "words": []} for k in ("intro", "s1", "s2", "s3", "recap")}
    cards = {("l1", 1): {"tryIt": "Try It: x", "pack": None}}
    tl = timeline.build(plan, clips, cards)
    cardsegs = [s for s in tl["segments"] if s["kind"] == "practise"]
    assert len(cardsegs) == 1 and cardsegs[0]["scene"] == 2 and cardsegs[0]["card"]["tryIt"] == "Try It: x"
    scene2 = next(s for s in tl["segments"] if s["kind"] == "scene" and s["scene"] == 2)
    scene3 = next(s for s in tl["segments"] if s["kind"] == "scene" and s["scene"] == 3)
    assert cardsegs[0]["start"] == scene2["end"] and scene3["start"] == cardsegs[0]["end"]
    assert cardsegs[0]["end"] - cardsegs[0]["start"] == timeline.CARD
    topic1 = next(c for c in build_video.topic_clips(plan, tl, {}, {}) if c["topic"] == 1)
    assert topic1["end"] == cardsegs[0]["end"]


def test_stage_draws_the_practise_card():
    plan = {"intro": {"title": "T", "points": ["a"]}, "recap": {"points": ["b"]},
            "scenes": [{"kind": "vector", "lessonId": "l1", "topic": 1, "title": "One", "keyIdea": "k"}]}
    clips = {k: {"dur": 2.0, "words": []} for k in ("intro", "s1", "recap")}
    tl = timeline.build(plan, clips, {("l1", 1): {"tryIt": "Try It: x", "pack": "Pack: L01-practice-starter.ipynb, Task 1"}})
    page = stage.build_stage(plan, tl, ["<svg></svg>"], "")
    assert "Now practise" in page and "Pack: L01-practice-starter.ipynb, Task 1" in page
