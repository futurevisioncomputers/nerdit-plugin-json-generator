"""Change the timbre of a recording to the owner's voice with Chatterbox VC (MIT); the words,
timing and pronunciation of the source stay.

    tts-venv\\Scripts\\python convert_voice.py <source.wav> <owner ref.wav> <out.wav>
"""
import sys

import torchaudio
from chatterbox.vc import ChatterboxVC

src, ref, out = sys.argv[1:4]
model = ChatterboxVC.from_pretrained(device="cuda")
wav = model.generate(src, target_voice_path=ref)
torchaudio.save(out, wav.cpu(), model.sr)
print("wrote", out)
