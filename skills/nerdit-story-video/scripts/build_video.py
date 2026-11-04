"""Build the story video from plan.json, the approved visuals and the narration clips.

    python build_video.py --images-dir <images> [--workers 3] [--music <file>]

Writes to <images>/video/: story.mp4 (1280x720, H.264 + AAC), thumbnail.jpg, title.txt and
description.txt (with YouTube chapters), plus one short clip per lesson topic, an intro clip and
a recap clip (clip-NN-<key>.mp4), listed in clips.json.
Host the MP4 on YouTube (unlisted is fine) and link it from the course; never upload it to Firebase.
"""
import argparse, array, json, shutil, subprocess, sys, time, wave
from pathlib import Path

import lessonparts
import render
import stage
import storyplan
import timeline
import voice

RATE = 24000
FPS = 25
MUSIC_VOLUME = 0.07


def clip_info(audio: Path, plan: dict) -> dict:
    info = {}
    for c in voice.clips(plan):
        wav, words = audio / f"{c['id']}.wav", audio / f"{c['id']}.words.json"
        if not wav.is_file() or not words.is_file():
            raise SystemExit(f"missing {wav.name} or its words file; run voice.py first")
        info[c["id"]] = {"dur": voice.wav_seconds(wav),
                         "words": json.loads(words.read_text(encoding="utf-8"))}
    return info


def mix(audio: Path, placements: list[dict], duration: float, out: Path) -> Path:
    """Place each 24 kHz mono clip at its start time on one silent track."""
    track = array.array("h", bytes(2 * int(duration * RATE + RATE)))
    for p in placements:
        with wave.open(str(audio / f"{p['clip']}.wav")) as w:
            if w.getframerate() != RATE or w.getnchannels() != 1:
                raise SystemExit(f"{p['clip']}.wav must be {RATE} Hz mono")
            samples = array.array("h", w.readframes(w.getnframes()))
        at = int(p["at"] * RATE)
        track[at:at + len(samples)] = samples
    del track[int(duration * RATE):]
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(track.tobytes())
    return out


def mux_command(ff: str, video: Path, narration: Path, out: Path, music: Path | None = None) -> list[str]:
    cmd = [ff, "-y", "-loglevel", "error", "-i", str(video), "-i", str(narration)]
    if music:
        cmd += ["-stream_loop", "-1", "-i", str(music), "-filter_complex",
                f"[2:a]volume={MUSIC_VOLUME}[m];[1:a][m]amix=inputs=2:duration=first:normalize=0[a]",
                "-map", "0:v", "-map", "[a]"]
    else:
        cmd += ["-map", "0:v", "-map", "1:a"]
    return cmd + ["-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", str(out)]


BOX = (40, 104, 720, 540)   # x, y, w, h of the picture box on the stage (stage.py .box)


def broll_command(ff: str, video: Path, windows: list[dict], clips: list[Path], out: Path) -> list[str]:
    """Paste each B-roll clip, cropped to the 4:3 box, into the stage video during its scene window.
    The browser cannot decode H.264, so B-roll goes in here instead of on the stage page."""
    x, y, w, h = BOX
    cmd = [ff, "-y", "-loglevel", "error", "-i", str(video)]
    graph, last = [], "0:v"
    for i, (win, clip) in enumerate(zip(windows, clips), 1):
        cmd += ["-stream_loop", "-1", "-i", str(clip)]
        graph.append(f"[{i}:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1,"
                     f"fps={FPS},setpts=PTS-STARTPTS+{win['start']}/TB[b{i}]")
        graph.append(f"[{last}][b{i}]overlay={x}:{y}:enable='between(t,{win['start']},{win['end']})':"
                     f"shortest=1[v{i}]")
        last = f"v{i}"
    return cmd + ["-filter_complex", ";".join(graph), "-map", f"[{last}]", "-c:v", "libx264", "-preset", "medium",
                  "-crf", "22", "-pix_fmt", "yuv420p", "-colorspace", "bt709", str(out)]


def topic_clips(plan: dict, tl: dict, titles: dict, topics: dict) -> list[dict]:
    """One short clip per lesson topic (its scenes and myths), plus an intro clip and a recap clip.
    A learner stuck on one section watches only that section's clip, placed at its end."""
    def clip(place: str, lid: str, topic, title: str, start: float, end: float) -> dict:
        key = f"{lid}-{place}-video" if place != "topic" else f"{lid}-t{topic}-video"
        return {"key": key, "place": place, "lessonId": lid, "topic": topic, "title": title,
                "start": round(start, 3), "end": round(end, 3)}

    scenes = [s for s in tl["segments"] if s.get("scene")]
    groups = []
    for seg in scenes:
        s = plan["scenes"][seg["scene"] - 1]
        key = (s["lessonId"], s.get("topic", 1))
        if groups and groups[-1][0] == key:
            groups[-1][1].append(seg)
        else:
            groups.append((key, [seg], s["title"]))
    first, last = groups[0][0][0], groups[-1][0][0]
    lesson = titles.get(first, first)
    out = [clip("intro", first, None, f"{lesson}: introduction", 0.0, groups[0][1][0]["start"])]
    for (lid, topic), segs, scene_title in groups:
        title = (topics.get(lid) or {}).get(topic) or scene_title
        out.append(clip("topic", lid, topic, title, segs[0]["start"], segs[-1]["end"]))
    recap = next(s for s in tl["segments"] if s["kind"] == "recap")
    out.append(clip("recap", last, None, f"{plan.get('course') or titles.get(last, last)}: recap",
                    recap["start"], tl["duration"]))
    for i, c in enumerate(out, 1):
        c["title"] = storyplan.title_case(c["title"])
        c["file"] = f"clip-{i:02d}-{c['key'][:-len('-video')]}.mp4"
    return out


def cut_command(ff: str, video: Path, clip: dict, out: Path) -> list[str]:
    """Frame-accurate cut (re-encoded) with a short fade in and out."""
    dur = clip["end"] - clip["start"]
    fade = f"fade=t=in:st=0:d=0.3,fade=t=out:st={max(dur - 0.4, 0):.3f}:d=0.4"
    return [ff, "-y", "-loglevel", "error", "-ss", f"{clip['start']:.3f}", "-i", str(video), "-t", f"{dur:.3f}",
            "-vf", fade, "-af", f"afade=t=in:st=0:d=0.2,afade=t=out:st={max(dur - 0.4, 0):.3f}:d=0.4",
            "-c:v", "libx264", "-preset", "medium", "-crf", "22", "-pix_fmt", "yuv420p", "-c:a", "aac",
            "-b:a", "128k", "-movflags", "+faststart", str(out)]


def scene_svgs(plan: dict, vid: Path, figures: dict, parts: dict | None = None) -> list:
    out = []
    for s in plan["scenes"]:
        if s["kind"] == "vector":
            out.append((vid / "vectors" / s["vector"]).read_text(encoding="utf-8-sig"))
        elif s["kind"] == "diagram":
            out.append(figures[s["figure"]]["svg"])
        elif s["kind"] == "table":   # the page's own table, redrawn
            out.append(lessonparts.table_svg(storyplan.part_of(s, parts), s.get("highlight")))
        elif s["kind"] == "code":    # the page's own worked example and its output
            out.append(lessonparts.code_svg(storyplan.part_of(s, parts), s.get("highlight")))
        else:
            out.append(None)
    return out


THUMB_CSS = """html,body{margin:0;width:1280px;height:720px;overflow:hidden;background:#0B1F3A;
font-family:'Segoe UI','Noto Sans',Arial,sans-serif}
.photo{position:absolute;right:0;top:0;width:640px;height:720px;background:url('PHOTO') 50% 30%/cover}
.fade{position:absolute;left:520px;top:0;width:200px;height:720px;background:linear-gradient(90deg,#0B1F3A 15%,rgba(11,31,58,0))}
.text{position:absolute;left:64px;top:0;bottom:0;width:520px;display:flex;flex-direction:column;justify-content:center}
.brand{font-weight:800;letter-spacing:6px;color:#2dd4bf;font-size:30px}
.course{color:#fff;font-weight:800;font-size:60px;line-height:1.05;margin-top:18px}
.title{color:#fbbf24;font-weight:700;line-height:1.15;margin-top:24px}
.lesson{color:#cbd5e1;font-size:28px;margin-top:22px}"""


def thumbnail_html(photo: Path, course: str, title: str, lesson: str = "") -> str:
    """A YouTube thumbnail page: the owner's photo on the right, the course and the clip's title
    on the left (owner, 2026-11-04). Static, but with renderAt and ready like the stage page."""
    import html as h
    size = 46 if len(title) <= 34 else 38 if len(title) <= 52 else 32
    return ("<!doctype html><html><head><meta charset='utf-8'><style>"
            + THUMB_CSS.replace("PHOTO", photo.resolve().as_uri()) + "</style></head><body>"
            "<div class='photo'></div><div class='fade'></div><div class='text'>"
            "<div class='brand'>NERDIT</div>"
            f"<div class='course'>{h.escape(course)}</div>"
            f"<div class='title' style='font-size:{size}px'>{h.escape(title)}</div>"
            + (f"<div class='lesson'>{h.escape(lesson)}</div>" if lesson else "")
            + "</div><script>window.renderAt=function(){};window.ready=Promise.resolve(true);</script></body></html>")


def make_thumbnails(vid: Path, plan: dict, clips: list[dict], titles: dict) -> list[Path]:
    """thumb-<clip>.jpg for every clip, plus thumbnail.jpg for the whole video, when the plan names
    the owner's photo (plan.thumbnail.photo, a file in the video folder). Adds "thumbnail" to each clip."""
    photo_name = (plan.get("thumbnail") or {}).get("photo")
    if not photo_name:
        return []
    photo, course = vid / photo_name, plan.get("course", "")
    if not photo.is_file():
        raise SystemExit(f"thumbnail photo {photo} is missing")
    work = vid / "parts" / "thumbs"
    work.mkdir(parents=True, exist_ok=True)
    pages = [(course, "Full course explained", "", vid / "thumbnail.jpg")]
    for c in clips:
        c["thumbnail"] = "thumb-" + Path(c["file"]).stem + ".jpg"
        title = c["title"].split(": ", 1)[-1] if c["title"].startswith(course + ":") else c["title"]
        pages.append((course, title, titles.get(c["lessonId"], ""), vid / c["thumbnail"]))
    jobs = []
    for i, (crs, title, lesson, out) in enumerate(pages):
        page = work / f"t{i:03d}.html"
        page.write_text(thumbnail_html(photo, crs, title, lesson), encoding="utf-8")
        jobs.append((page, out))
    render.stills(jobs)
    return [out for _, out in jobs]


def svg_parts(svg: str) -> list | None:
    """The animated parts of a vector, in drawing order: each top-level <g> with a na- class gives
    its text (the label the narration must name) or None (an arrow or line). stage.py walks the
    same groups, so the two lists line up."""
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(svg)
    except ET.ParseError:
        return None
    parts = []
    for g in root:
        if g.tag.split("}")[-1] == "g" and "na-" in g.get("class", ""):
            text = " ".join(" ".join(t.itertext()) for t in g.iter() if t.tag.split("}")[-1] == "text").strip()
            parts.append(text or None)
    return parts if any(parts) else None


def vector_labels(plan: dict, vid: Path) -> dict:
    """labels[scene number] for timeline.build: the parts of every vector scene."""
    out = {}
    for n, s in enumerate(plan["scenes"], 1):
        if s["kind"] == "vector":
            parts = svg_parts((vid / "vectors" / s["vector"]).read_text(encoding="utf-8-sig"))
            if parts:
                out[n] = parts
    return out


def build(images_dir: Path, workers: int = 3, music: Path | None = None) -> Path:
    images_dir = Path(images_dir).resolve()
    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    vid = images_dir / "video"
    plan = storyplan.load_json(vid / "plan.json")
    course = Path(plan["source"]) if plan.get("source") else None
    figures = storyplan.lesson_figures(course, images_dir) if course else {}
    parts = storyplan.lesson_parts(course) if course else None
    practice = storyplan.lesson_practice(course) if course else None
    errors = storyplan.check_plan(plan, vid, figures, storyplan.lesson_texts(course) if course else None,
                                  storyplan.lesson_topics(course) if course else None, parts, practice)
    clips = [vid / "broll" / f"s{n}.mp4" for n, s in enumerate(plan["scenes"], 1) if s["kind"] == "broll"]
    errors += [f"missing {c}; run broll.py first" for c in clips if not c.is_file()]
    if errors:
        raise SystemExit("plan has problems; run storyplan.py check:\n" + "\n".join(errors))

    tl = timeline.build(plan, clip_info(vid / "audio", plan),
                        storyplan.practise_cards(plan, practice) if practice else None, vector_labels(plan, vid))
    work = vid / "parts"
    work.mkdir(parents=True, exist_ok=True)
    html = vid / "stage.html"
    headings = {(lid, n): p["heading"] for lid, secs in (parts or {}).items() for n, p in secs.items()}
    html.write_text(stage.build_stage(plan, tl, scene_svgs(plan, vid, figures, parts), stage.lesson_css(), headings),
                    encoding="utf-8")
    narration = mix(vid / "audio", tl["audio"], tl["duration"], work / "narration.wav")
    print(f"rendering {tl['duration'] / 60:.0f} min of video with {workers} workers", flush=True)
    silent = render.render(html, tl["duration"], FPS, workers, work / "video.mp4", ff)
    if tl["broll"]:
        with_broll = work / "video-broll.mp4"
        subprocess.run(broll_command(ff, silent, tl["broll"], clips, with_broll), check=True)
        silent = with_broll
    final = vid / "story.mp4"
    subprocess.run(mux_command(ff, silent, narration, final, music), check=True)

    first = next(s for s in tl["segments"] if s["kind"] == "scene" and s.get("visual") != "broll")
    render.still(html, first["end"] - 1.0, vid / "thumbnail.jpg")   # the finished drawing
    (vid / "title.txt").write_text(f"{plan.get('course', '')}: concept recap\n", encoding="utf-8")
    text = timeline.description(plan, tl["chapters"])
    credits_path = vid / "broll" / "credits.json"
    if tl["broll"] and credits_path.is_file():
        credits = json.loads(credits_path.read_text(encoding="utf-8"))
        text += "\nB-roll from Pexels:\n" + "".join(f"- {c['by']}: {c['page']}\n" for c in credits.values())
    (vid / "description.txt").write_text(text, encoding="utf-8")

    titles = {l["id"]: l.get("title", "") for l in storyplan.course_lessons(course)} if course else {}
    topics = storyplan.lesson_topics(course) if course else {}
    for old in vid.glob("clip-*.mp4"):   # a rebuild may cut a different set of clips
        old.unlink()
    clips = topic_clips(plan, tl, titles, topics)
    print(f"cutting {len(clips)} clips", flush=True)
    for c in clips:
        subprocess.run(cut_command(ff, final, c, vid / c["file"]), check=True)
        c["youtubeTitle"] = storyplan.title_case(f"{plan.get('course', '')}: {c['title']}")
    make_thumbnails(vid, plan, clips, titles)
    (vid / "clips.json").write_text(json.dumps(clips, ensure_ascii=False, indent=2), encoding="utf-8")
    return final


STILL_CPS = 14.0   # characters per second of narration, to time a preview before anything is recorded


def _course_context(vid: Path, plan: dict):
    course = Path(plan["source"]) if plan.get("source") else None
    figures = storyplan.lesson_figures(course, vid.parent) if course else {}
    parts = storyplan.lesson_parts(course) if course else None
    practice = storyplan.lesson_practice(course) if course else None
    errors = storyplan.check_plan(plan, vid, figures, storyplan.lesson_texts(course) if course else None,
                                  storyplan.lesson_topics(course) if course else None, parts, practice)
    if errors:
        raise SystemExit("plan has problems; run storyplan.py check:\n" + "\n".join(errors))
    return course, figures, parts, practice


def _subset(plan: dict, only: str | None) -> tuple[dict, list[int]]:
    """The plan with only the scenes of `only` (all when None), and their original numbers."""
    pick = voice.selected(plan, only)
    numbers = [n for n in range(1, len(plan["scenes"]) + 1) if pick is None or f"s{n}" in pick]
    return dict(plan, scenes=[plan["scenes"][n - 1] for n in numbers]), numbers


def _stage(vid: Path, sub: dict, tl: dict, figures: dict, parts: dict | None, html: Path) -> None:
    headings = {(lid, n): p["heading"] for lid, secs in (parts or {}).items() for n, p in secs.items()}
    html.parent.mkdir(parents=True, exist_ok=True)
    html.write_text(stage.build_stage(sub, tl, scene_svgs(sub, vid, figures, parts), stage.lesson_css(), headings),
                    encoding="utf-8")


def preview_stills(images_dir: Path, only: str | None = None) -> list[Path]:
    """One frame per scene, at the end of its build-up, before any narration is recorded: a free
    check of the visuals. Timing comes from the narration's length; writes <video>/stills/<lesson>.jpg
    contact sheets (3 frames per row)."""
    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    vid = Path(images_dir).resolve() / "video"
    plan = storyplan.load_json(vid / "plan.json")
    course, figures, parts, practice = _course_context(vid, plan)
    sub, _ = _subset(plan, only)
    info = {}
    for c in voice.clips(sub):
        dur = max(len(c["text"]) / STILL_CPS, 1.0)
        info[c["id"]] = {"dur": dur, "words": voice.estimate_words(c["text"], dur)}
    tl = timeline.build(sub, info, storyplan.practise_cards(sub, practice) if practice else None, vector_labels(sub, vid))
    out_dir = vid / "stills"
    shutil.rmtree(out_dir, ignore_errors=True)
    _stage(vid, sub, tl, figures, parts, out_dir / "stage.html")
    shots, by_lesson = [], {}
    for seg in (s for s in tl["segments"] if s["kind"] == "scene"):
        lesson = sub["scenes"][seg["scene"] - 1]["lessonId"]
        folder = out_dir / lesson
        folder.mkdir(exist_ok=True)
        by_lesson[lesson] = by_lesson.get(lesson, 0) + 1
        shots.append((round(seg["end"] - 0.6, 3), folder / f"{by_lesson[lesson]:03d}.jpg"))
    render.frames(out_dir / "stage.html", shots)
    sheets = []
    for lesson, count in by_lesson.items():
        sheet = out_dir / f"{lesson}.jpg"
        subprocess.run([ff, "-y", "-v", "error", "-framerate", "1", "-i", str(out_dir / lesson / "%03d.jpg"),
                        "-vf", f"scale=640:-1,tile=3x{(count + 2) // 3}", "-frames:v", "1", "-q:v", "3", str(sheet)],
                       check=True)
        sheets.append(sheet)
    return sheets


def pilot(images_dir: Path, only: str, workers: int = 3) -> Path:
    """One lesson or topic, voiced and rendered on its own (voice.py --only first), so the owner can
    watch a minute of the real video before the whole course is recorded and rendered.
    Writes <video>/pilot/pilot-<lesson>[-t<topic>].mp4."""
    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    vid = Path(images_dir).resolve() / "video"
    plan = storyplan.load_json(vid / "plan.json")
    course, figures, parts, practice = _course_context(vid, plan)
    sub, numbers = _subset(plan, only)
    work = vid / "pilot"
    audio = work / "audio"
    shutil.rmtree(work, ignore_errors=True)
    audio.mkdir(parents=True)
    for new, old in enumerate(numbers, 1):           # the subset's scenes are numbered from 1
        for suffix in ("", "-myth"):
            for ext in (".wav", ".words.json"):
                src = vid / "audio" / f"s{old}{suffix}{ext}"
                if src.is_file():
                    shutil.copy(src, audio / f"s{new}{suffix}{ext}")
                elif not suffix:
                    raise SystemExit(f"missing {src}; run voice.py --only {only} first")
    for clip in ("intro", "recap"):                  # not part of the pilot: a short silence
        with wave.open(str(audio / f"{clip}.wav"), "wb") as w:
            w.setnchannels(1), w.setsampwidth(2), w.setframerate(RATE), w.writeframes(b"\0\0" * (RATE // 10))
        (audio / f"{clip}.words.json").write_text("[]", encoding="utf-8")
    tl = timeline.build(sub, clip_info(audio, sub), storyplan.practise_cards(sub, practice) if practice else None,
                        vector_labels(sub, vid))
    _stage(vid, sub, tl, figures, parts, work / "stage.html")
    narration = mix(audio, tl["audio"], tl["duration"], work / "narration.wav")
    silent = render.render(work / "stage.html", tl["duration"], FPS, workers, work / "video.mp4", ff)
    brolls = [vid / "broll" / f"s{n}.mp4" for n in numbers if plan["scenes"][n - 1]["kind"] == "broll"]
    if tl["broll"]:
        subprocess.run(broll_command(ff, silent, tl["broll"], brolls, work / "video-broll.mp4"), check=True)
        silent = work / "video-broll.mp4"
    full = work / "full.mp4"
    subprocess.run(mux_command(ff, silent, narration, full), check=True)
    segs = [s for s in tl["segments"] if s.get("scene")]
    start, end = segs[0]["start"], segs[-1]["end"]
    out = work / f"pilot-{only.replace(':', '-t')}.mp4"
    subprocess.run([ff, "-y", "-v", "error", "-ss", str(start), "-i", str(full), "-t", str(end - start),
                    "-c:v", "libx264", "-crf", "18", "-c:a", "aac", "-b:a", "192k", str(out)], check=True)
    return out


def thumbnails_only(images_dir: Path) -> list[Path]:
    """Redo the thumbnails of an already built video from plan.json and clips.json."""
    vid = Path(images_dir).resolve() / "video"
    plan = storyplan.load_json(vid / "plan.json")
    clips = json.loads((vid / "clips.json").read_text(encoding="utf-8"))
    course = Path(plan["source"]) if plan.get("source") else None
    titles = {l["id"]: l.get("title", "") for l in storyplan.course_lessons(course)} if course else {}
    made = make_thumbnails(vid, plan, clips, titles)
    (vid / "clips.json").write_text(json.dumps(clips, ensure_ascii=False, indent=2), encoding="utf-8")
    return made


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--images-dir", required=True, type=Path)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--music", type=Path, help="optional background music, mixed quietly under the voice")
    ap.add_argument("--thumbnails-only", action="store_true", help="redo the thumbnails of a built video")
    ap.add_argument("--stills", action="store_true", help="free preview: one frame per scene, no narration needed")
    ap.add_argument("--only", metavar="LESSON[:TOPIC]", help="pilot: render only this lesson or topic")
    a = ap.parse_args(argv)
    t0 = time.time()
    if a.stills:
        for sheet in preview_stills(a.images_dir, a.only):
            print("stills", sheet)
        return 0
    if a.only:
        print(f"pilot {pilot(a.images_dir, a.only, a.workers)} in {time.time() - t0:.0f}s")
        return 0
    if a.thumbnails_only:
        made = thumbnails_only(a.images_dir)
        print(f"{len(made)} thumbnails" if made else "no plan.thumbnail.photo: nothing to do")
        return 0
    final = build(a.images_dir, a.workers, a.music)
    print(f"built {final} ({final.stat().st_size / 1e6:.1f} MB) in {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
