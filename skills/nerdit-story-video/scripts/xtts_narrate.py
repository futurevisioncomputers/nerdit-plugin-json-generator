"""Run with the voice venv's python (XTTS-v2). Called by voice.py --engine clone.

    <venv python> xtts_narrate.py <clips.json> <ref.wav or folder> <out dir>

clips.json is [{"id", "text"}]; writes <out dir>/<id>.wav for each.
Licence: Coqui Public Model License (non-commercial). Local tests only.
"""
import json, os, sys, time, wave
from pathlib import Path

os.environ.setdefault("COQUI_TOS_AGREED", "1")
import numpy as np
import torch
from TTS.api import TTS

sys.path.insert(0, str(Path(__file__).parent))
from voice import chunks  # stdlib-only module, shared with the tests

PAUSE = 0.25     # seconds of silence between sentences


def save(samples: np.ndarray, rate: int, path: Path) -> None:
    pcm = (np.clip(samples, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())


items = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8-sig"))
ref, out = Path(sys.argv[2]), Path(sys.argv[3])
refs = [str(p) for p in sorted(ref.glob("*.wav"))] if ref.is_dir() else [str(ref)]  # XTTS blends them
out.mkdir(parents=True, exist_ok=True)
device = "cuda" if torch.cuda.is_available() else "cpu"
t0 = time.time()
tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)
print(f"model ready in {time.time() - t0:.0f}s on {device}")
rate = tts.synthesizer.output_sample_rate
gap = np.zeros(int(rate * PAUSE), dtype=np.float32)
for item in items:
    parts = []
    for text in chunks(item["text"]):
        parts += [np.asarray(tts.tts(text=text, speaker_wav=refs, language="hi", split_sentences=False),
                             dtype=np.float32), gap]
    save(np.concatenate(parts), rate, out / f"{item['id']}.wav")
    print(f"{item['id']} done ({len(parts) // 2} sentences)")
