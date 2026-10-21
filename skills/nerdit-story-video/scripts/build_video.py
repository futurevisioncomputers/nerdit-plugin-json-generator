"""Build the story video from plan.json, the approved visuals and the narration clips.

    python build_video.py --images-dir <images> [--workers 3] [--music <file>]

Writes to <images>/video/: story.mp4 (1280x720, H.264 + AAC), thumbnail.jpg, title.txt and
description.txt (with YouTube chapters), plus one short clip per lesson topic, an intro clip and
a recap clip (clip-NN-<key>.mp4), listed in clips.json.
Host the MP4 on YouTube (unlisted is fine) and link it from the course; never upload it to Firebase.
"""
import argparse, array, json, subprocess, sys, time, wave
from pathlib import Path

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


def scene_svgs(plan: dict, vid: Path, figures: dict) -> list:
    out = []
    for s in plan["scenes"]:
        if s["kind"] == "vector":
            out.append((vid / "vectors" / s["vector"]).read_text(encoding="utf-8-sig"))
        elif s["kind"] == "diagram":
            out.append(figures[s["figure"]]["svg"])
        else:
            out.append(None)
    return out


def build(images_dir: Path, workers: int = 3, music: Path | None = None) -> Path:
    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    vid = images_dir / "video"
    plan = storyplan.load_json(vid / "plan.json")
    course = Path(plan["source"]) if plan.get("source") else None
    figures = storyplan.lesson_figures(course, images_dir) if course else {}
    errors = storyplan.check_plan(plan, vid, figures, storyplan.lesson_texts(course) if course else None,
                                  storyplan.lesson_topics(course) if course else None)
    clips = [vid / "broll" / f"s{n}.mp4" for n, s in enumerate(plan["scenes"], 1) if s["kind"] == "broll"]
    errors += [f"missing {c}; run broll.py first" for c in clips if not c.is_file()]
    if errors:
        raise SystemExit("plan has problems; run storyplan.py check:\n" + "\n".join(errors))

    tl = timeline.build(plan, clip_info(vid / "audio", plan))
    work = vid / "parts"
    work.mkdir(parents=True, exist_ok=True)
    html = vid / "stage.html"
    html.write_text(stage.build_stage(plan, tl, scene_svgs(plan, vid, figures), stage.lesson_css()), encoding="utf-8")
    narration = mix(vid / "audio", tl["audio"], tl["duration"], work / "narration.wav")
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
    for c in clips:
        subprocess.run(cut_command(ff, final, c, vid / c["file"]), check=True)
        c["youtubeTitle"] = storyplan.title_case(f"{plan.get('course', '')}: {c['title']}")
    (vid / "clips.json").write_text(json.dumps(clips, ensure_ascii=False, indent=2), encoding="utf-8")
    return final


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--images-dir", required=True, type=Path)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--music", type=Path, help="optional background music, mixed quietly under the voice")
    a = ap.parse_args(argv)
    t0 = time.time()
    final = build(a.images_dir, a.workers, a.music)
    print(f"built {final} ({final.stat().st_size / 1e6:.1f} MB) in {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
