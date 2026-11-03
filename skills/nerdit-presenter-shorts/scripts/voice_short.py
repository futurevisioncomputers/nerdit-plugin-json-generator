"""Record a short's lines in the owner's voice.

    python voice_short.py --plan <short.plan.json> --out-dir <dir> --tts-python <tts venv python> --ref <owner voice.wav>

1. Google Chirp 3 HD (plan "voice", default hi-IN-Chirp3-HD-Charon) reads each line, respelled by
   the story video's pronounce.py, so English terms (Flask, SQLAlchemy, REST API) are said right:
   <out-dir>/parts/01.wav, 02.wav, ... and the joined <out-dir>/chirp.wav.
2. convert_voice.py (Chatterbox VC, MIT, in the TTS venv) changes the timbre to the owner's voice
   from their reference recording: <out-dir>/voice.wav. Timing stays the same, so the line lengths
   in parts/ time the captions.
Key: GOOGLE_TTS_API_KEY in the environment, never in a file.
"""
import argparse, json, subprocess, sys, wave
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "nerdit-story-video" / "scripts"))
from voice import google_clip, google_key   # noqa: E402
from pronounce import spoken                # noqa: E402
from shorts import PAUSE                    # noqa: E402


def join(parts: list[Path], out: Path) -> None:
    frames, params = [], None
    for p in parts:
        with wave.open(str(p)) as w:
            params = params or w.getparams()
            frames.append(w.readframes(w.getnframes()))
    gap = b"\0" * int(params.framerate * PAUSE) * params.sampwidth * params.nchannels
    with wave.open(str(out), "wb") as w:
        w.setparams(params)
        w.writeframes(gap.join(frames))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True, type=Path)
    ap.add_argument("--out-dir", required=True, type=Path)
    ap.add_argument("--tts-python", required=True, help="python of the venv with chatterbox-tts")
    ap.add_argument("--ref", required=True, type=Path, help="the owner's voice, about 10 s")
    a = ap.parse_args(argv)
    plan = json.loads(a.plan.read_text(encoding="utf-8"))
    name, key = plan.get("voice", "hi-IN-Chirp3-HD-Charon"), google_key()
    parts_dir = a.out_dir / "parts"
    parts_dir.mkdir(parents=True, exist_ok=True)
    parts = []
    for n, line in enumerate(plan["lines"], 1):
        part = parts_dir / f"{n:02d}.wav"
        google_clip(spoken(line["say"]), name, 1.0, part, key)
        parts.append(part)
    join(parts, a.out_dir / "chirp.wav")
    subprocess.run([a.tts_python, str(HERE / "convert_voice.py"), str(a.out_dir / "chirp.wav"), str(a.ref),
                    str(a.out_dir / "voice.wav")], check=True)
    print("wrote", a.out_dir / "voice.wav")
    return 0


if __name__ == "__main__":
    sys.exit(main())
