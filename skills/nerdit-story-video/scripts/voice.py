"""Narration audio for a checked story plan: one <clip>.wav (24 kHz mono) and <clip>.words.json per clip.

    python voice.py --images-dir <images>                         # engine from plan.json
    python voice.py --images-dir <images> --engine clone --python <venv python> --ref <ref.wav or folder>
    python voice.py --list-voices hi-IN                           # Google voices for a language

Clips: intro, s1, s1-myth, ..., recap. The words file holds each spoken word's start and length in
seconds; the video uses it for key-term pop-ins, camera focus and vector build-up.

google: Google Cloud Text-to-Speech Chirp 3 HD (default hi-IN-Chirp3-HD-Aoede), the most human
        voice; key in the GOOGLE_TTS_API_KEY environment variable, never in the plan. Word timings
        are estimated from text length (Chirp returns none). Needs internet.
edge  : Microsoft neural voice through edge-tts (hi-IN-SwaraNeural), exact word timings, sounds synthetic.
clone : local XTTS-v2 in a separate venv (xtts_narrate.py); word timings are estimated from text length.
        Non-commercial licence: local tests only.
"""
import argparse, asyncio, json, os, re, subprocess, sys, wave
from pathlib import Path

HERE = Path(__file__).parent
CLONE_LIMIT = 150   # XTTS truncates Hindi input longer than this, so clone speaks one chunk at a time
AUDIO_EXT = {".wav", ".mp3", ".m4a", ".aac", ".ogg", ".opus", ".flac", ".mp4"}
CLIP_SECONDS = 25
TICKS = 1e7         # edge-tts offsets are in 100 ns units
DEFAULT_RATE = "+10%"


def ffmpeg() -> str:
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def clips(plan: dict) -> list[dict]:
    """Every narrated clip in speaking order: {id, text, say (spoken by clone)}."""
    out = [{"id": "intro", "text": plan["intro"]["narration"]}]
    for n, s in enumerate(plan["scenes"], 1):
        out.append({"id": f"s{n}", "text": s["narration"], "say": s.get("say")})
        if s.get("myth"):
            out.append({"id": f"s{n}-myth", "text": s["myth"]["narration"]})
    out.append({"id": "recap", "text": plan["recap"]["narration"]})
    return out


def chunks(text: str, limit: int = CLONE_LIMIT) -> list[str]:
    """Sentences, each within `limit` characters (long ones split at a comma, else a space)."""
    out = []
    for sentence in re.findall(r"[^.!?।]+[.!?।]*", text):
        sentence = sentence.strip()
        while len(sentence) > limit:
            cut = sentence.rfind(",", 0, limit)
            cut = cut if cut > 0 else sentence.rfind(" ", 0, limit)
            out.append(sentence[:cut + 1].strip())
            sentence = sentence[cut + 1:].strip()
        if sentence:
            out.append(sentence)
    return out


def estimate_words(text: str, seconds: float) -> list[dict]:
    """Word timings spread by character length, for engines that give none."""
    words = text.split()
    total = sum(len(w) + 1 for w in words) or 1
    out, t = [], 0.15
    span = max(seconds - 0.3, 0.1)
    for w in words:
        d = span * (len(w) + 1) / total
        out.append({"t": round(t, 3), "d": round(d * 0.9, 3), "w": w.strip(".,!?।:;")})
        t += d
    return out


def wav_seconds(path: Path) -> float:
    with wave.open(str(path)) as w:
        return w.getnframes() / w.getframerate()


async def edge_clip(text: str, name: str, rate: str, mp3: Path) -> list[dict]:
    import edge_tts
    words = []
    with open(mp3, "wb") as f:
        async for chunk in edge_tts.Communicate(text, name, rate=rate, boundary="WordBoundary").stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                words.append({"t": round(chunk["offset"] / TICKS, 3), "d": round(chunk["duration"] / TICKS, 3),
                              "w": chunk["text"]})
    return words


def to_wav(ff: str, src: Path, wav: Path, runner=subprocess.run) -> None:
    runner([ff, "-y", "-loglevel", "error", "-i", str(src), "-ar", "24000", "-ac", "1", str(wav)], check=True)


def prepare_refs(ref: Path, out_dir: Path, ff: str, runner=subprocess.run) -> Path:
    """Reference recordings (one file or a folder of them) -> clean 22.05 kHz mono wavs in out_dir.

    Cuts rumble below 80 Hz, trims leading/trailing silence and evens the loudness, so phone
    recordings from different days blend into one voice.
    """
    sources = sorted(p for p in ref.iterdir() if p.suffix.lower() in AUDIO_EXT) if ref.is_dir() else [ref]
    if not sources:
        raise SystemExit(f"no audio files in {ref}")
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("ref*.wav"):
        old.unlink()
    clean = ("highpass=f=80,silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
             "silenceremove=start_periods=1:start_threshold=-45dB,areverse,loudnorm=I=-18:TP=-2")
    # XTTS reads only the first 30 s of each reference, so long recordings become 25 s clips.
    for n, src in enumerate(sources, 1):
        runner([ff, "-y", "-loglevel", "error", "-i", str(src), "-af", clean, "-ar", "22050", "-ac", "1",
                "-f", "segment", "-segment_time", str(CLIP_SECONDS), str(out_dir / f"ref{n}-%02d.wav")],
               check=True)
    return out_dir


GOOGLE_URL = "https://texttospeech.googleapis.com/v1/{path}?key={key}"


def google_key() -> str:
    key = os.environ.get("GOOGLE_TTS_API_KEY", "").strip()
    if not key:
        raise SystemExit("set GOOGLE_TTS_API_KEY (Cloud Text-to-Speech API key) in your user environment, "
                         "then restart the terminal; never put the key in plan.json")
    return key


def google_request(path: str, body: dict | None, key: str) -> dict:
    """POST (or GET when body is None) to the Text-to-Speech REST API; errors never echo the key."""
    import urllib.error, urllib.request
    req = urllib.request.Request(GOOGLE_URL.format(path=path, key=key),
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        detail = json.loads(e.read() or b"{}").get("error", {}).get("message", "")
        raise SystemExit(f"Google Text-to-Speech {path}: HTTP {e.code} {detail}") from None


def google_body(text: str, name: str, rate: float) -> dict:
    return {"input": {"text": text},
            "voice": {"languageCode": "-".join(name.split("-")[:2]), "name": name},
            "audioConfig": {"audioEncoding": "LINEAR16", "sampleRateHertz": 24000, "speakingRate": rate}}


def google_clip(text: str, name: str, rate: float, wav: Path, key: str, request=google_request) -> None:
    """LINEAR16 comes back as a complete WAV file, base64-encoded."""
    import base64
    wav.write_bytes(base64.b64decode(request("text:synthesize", google_body(text, name, rate), key)["audioContent"]))


def list_voices(language: str) -> list[str]:
    data = google_request("voices", None, google_key())
    return sorted(v["name"] for v in data.get("voices", []) if language in v.get("languageCodes", []))


def clone_command(python: str, clips_path: Path, ref: Path, raw_dir: Path) -> list[str]:
    return [python, str(HERE / "xtts_narrate.py"), str(clips_path), str(ref), str(raw_dir)]


def run(images_dir: Path, engine: str | None, python: str | None, ref: Path | None,
        runner=subprocess.run, edge=edge_clip, google=google_clip):
    plan = json.loads((images_dir / "video" / "plan.json").read_text(encoding="utf-8-sig"))
    voice = plan.get("voice") or {}
    engine = engine or voice.get("engine", "google")
    audio = images_dir / "video" / "audio"
    audio.mkdir(parents=True, exist_ok=True)
    ff = ffmpeg()
    items = clips(plan)
    if engine == "google":
        key = google_key()
        name, rate = voice.get("name", "hi-IN-Chirp3-HD-Aoede"), float(voice.get("rate", 1.0))
        for c in items:
            wav = audio / f"{c['id']}.wav"
            raw = audio / f"{c['id']}.google.wav"
            google(c["text"], name, rate, raw, key)
            to_wav(ff, raw, wav, runner)
            (audio / f"{c['id']}.words.json").write_text(
                json.dumps(estimate_words(c["text"], wav_seconds(wav)), ensure_ascii=False), encoding="utf-8")
    elif engine == "edge":
        for c in items:
            mp3, wav = audio / f"{c['id']}.mp3", audio / f"{c['id']}.wav"
            own = voice.get("engine") == "edge"   # an override keeps edge's own voice, not the plan's
            words = asyncio.run(edge(c["text"], voice.get("name") if own else "hi-IN-SwaraNeural",
                                     voice.get("rate") if own else DEFAULT_RATE, mp3))
            to_wav(ff, mp3, wav, runner)
            (audio / f"{c['id']}.words.json").write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")
    elif engine == "clone":
        python = python or voice.get("python")
        ref = ref or (Path(voice["ref"]) if voice.get("ref") else None)
        if not python or not ref:
            raise SystemExit("clone needs --python (voice venv) and --ref (recording or folder), or voice.python/voice.ref")
        raw = audio / "raw"
        refs = prepare_refs(ref, audio / "ref", ff, runner)
        clips_path = audio / "clips.json"
        clips_path.write_text(json.dumps([{"id": c["id"], "text": c.get("say") or c["text"]} for c in items],
                                         ensure_ascii=False), encoding="utf-8")
        runner(clone_command(python, clips_path, refs, raw), check=True, env=dict(os.environ, COQUI_TOS_AGREED="1"))
        for c in items:
            wav = audio / f"{c['id']}.wav"
            to_wav(ff, raw / f"{c['id']}.wav", wav, runner)
            seconds = wav_seconds(wav) if wav.is_file() else 1.0
            (audio / f"{c['id']}.words.json").write_text(
                json.dumps(estimate_words(c["text"], seconds), ensure_ascii=False), encoding="utf-8")
    else:
        raise SystemExit(f"unknown engine {engine!r}")
    return audio


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--images-dir", type=Path)
    ap.add_argument("--engine", choices=["google", "edge", "clone"])
    ap.add_argument("--python")
    ap.add_argument("--ref", type=Path)
    ap.add_argument("--list-voices", metavar="LANG")
    a = ap.parse_args(argv)
    if a.list_voices:
        print("\n".join(list_voices(a.list_voices)))
        return 0
    if not a.images_dir:
        ap.error("--images-dir is required")
    print(f"narration in {run(a.images_dir, a.engine, a.python, a.ref)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
