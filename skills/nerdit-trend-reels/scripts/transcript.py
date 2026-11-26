"""What Dev actually said, with word times, and the check against the script line.

The spike showed Flow's presenter adding words ("85,000 in cream") and reordering a line, so every clip is
transcribed (faster-whisper small, cached on this PC) and compared word by word before anything is composed.

CLI: transcript.py <run>   writes transcript.json, records checks.json["transcript"]; exit 1 on errors
"""
import difflib
import json
import re
import subprocess
import sys
from pathlib import Path

from numwords import MULT, SCALES, plain, words_to_digits
from runs import record_check

FIX = {"PWC": "PwC", "nerdid": "nerdit", "Nerdid": "nerdit"}
CURRENCY = {"$": "dollars", "€": "euros", "£": "pounds", "₹": "rupees"}
STOP = set("a an the of its to in on and so is are for it that this be".split())
RATE = 16_000


def merge_tokens(raw: list[tuple[str, float, float]]) -> list[dict]:
    out = []
    for word, start, end in raw:
        w = word.strip()
        w = FIX.get(w, w)
        if out and w[:1] in ",." and len(w) > 1:   # "85" ",000" -> "85,000"; "nerdit" ".in" -> "nerdit.in"
            out[-1]["w"] += w
            out[-1]["e"] = end
        elif w:
            out.append({"w": w, "s": start, "e": end})
    return out


def _content(words: list[str]) -> list[str]:
    """Content words with numbers in one form. Whisper writes "72%", "85K", "$1 billion" for what Dev says in
    words ("seventy-two percent", "eighty-five thousand", "one billion dollars"), so both sides normalise alike."""
    raw = []
    for w in words:
        t = w.lower().replace("’", "'").replace("'", "")
        t = re.sub(r"(?<=\d),(?=\d)", "", t).strip(".,!?;:\"()")
        if t:
            raw.append(t)
    tokens, i = [], 0
    while i < len(raw):
        t, after = raw[i], []
        currency = CURRENCY.get(t[:1])
        if currency:
            t = t[1:]
        if t == "%":   # Whisper sometimes writes "42 %" as two words
            t = "percent"
        elif t.endswith("%"):
            t, after = t[:-1], ["percent"]
        m = re.fullmatch(r"(\d+(?:\.\d+)?)(k|m|mn|b|bn)", t)
        if m:
            t = plain(float(m.group(1)) * MULT[m.group(2)])
        tokens.append(t)
        if currency:
            if i + 1 < len(raw) and raw[i + 1] in SCALES:   # "$1 billion" -> 1 billion dollars
                i += 1
                tokens.append(raw[i])
            after.append(currency)
        tokens += after
        i += 1
    return [t for t in words_to_digits(tokens) if t and t not in STOP]


def match_errors(heard: list[str], line: str) -> list[str]:
    said = _content(heard)
    if not said:
        return ["no speech heard"]
    want = _content(line.split())
    missing, extra = [], []
    for op, a1, a2, b1, b2 in difflib.SequenceMatcher(a=want, b=said, autojunk=False).get_opcodes():
        if op in ("delete", "replace"):
            missing += want[a1:a2]
        if op in ("insert", "replace"):
            extra += said[b1:b2]
    errors = []
    if missing:
        errors.append(f"missing: {' '.join(missing)}")
    if extra:
        errors.append(f"extra: {' '.join(extra)}")
    return errors


def _pcm(clip: Path):
    import imageio_ffmpeg
    import numpy as np
    raw = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-i", str(clip), "-f", "f32le", "-ac", "1",
                          "-ar", str(RATE), "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32)


def transcribe(clip: Path, model: str = "small") -> list[dict]:
    from faster_whisper import WhisperModel
    # the installed av is too new for faster-whisper's own decoder, so ffmpeg decodes to 16 kHz float PCM
    segments, _ = WhisperModel(model, device="cpu", compute_type="int8").transcribe(
        _pcm(clip), language="en", word_timestamps=True)
    return merge_tokens([(w.word, w.start, w.end) for s in segments for w in s.words])


def transcribe_run(run: Path) -> list[dict]:
    words, offset = [], 0.0
    for clip in sorted((run / "clips").glob("*.mp4")):
        for w in transcribe(clip):
            words.append({"w": w["w"], "s": round(w["s"] + offset, 3), "e": round(w["e"] + offset, 3)})
        offset += len(_pcm(clip)) / RATE
    return words


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__)
        return 2
    run = Path(argv[0])
    words = transcribe_run(run)
    (run / "transcript.json").write_text(json.dumps(words, indent=1), encoding="utf-8")
    line = json.loads((run / "script.json").read_text(encoding="utf-8"))["line"]
    errors = match_errors([w["w"] for w in words], line)
    record_check(run, "transcript", errors, [*sorted((run / "clips").glob("*.mp4")), run / "script.json"])
    print("heard: " + " ".join(w["w"] for w in words).encode("ascii", "replace").decode())
    for e in errors or ["transcript ok"]:
        print(e)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
