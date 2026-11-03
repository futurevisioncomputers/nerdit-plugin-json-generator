# One-time setup (Windows, NVIDIA GPU with 12 GB)

About 15 GB of downloads. `<tools>` is any folder outside the course, e.g. `D:\siddharth\ai-presenter`.
Some agents may not run code fetched from GitHub; the owner runs those lines in PowerShell.

```powershell
cd <tools>
py -3.11 -m venv tts-venv
tts-venv\Scripts\python -m pip install torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu124
tts-venv\Scripts\python -m pip install chatterbox-tts

py -3.10 -m venv sync-venv
git clone https://github.com/bytedance/LatentSync.git
```

LatentSync's `requirements.txt` without `insightface`, `onnxruntime-gpu` and `gradio`, saved as
`sync-req.txt`, then:

```powershell
sync-venv\Scripts\python -m pip install -r sync-req.txt "huggingface_hub[cli]"
sync-venv\Scripts\huggingface-cli download ByteDance/LatentSync-1.5 whisper/tiny.pt latentsync_unet.pt --local-dir LatentSync\checkpoints
Copy-Item sync-venv\lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win64-*.exe sync-venv\Scripts\ffmpeg.exe
```

Face detection without InsightFace (its models are non-commercial): copy
`scripts/mp_face_detector.py` to `LatentSync\latentsync\utils\`, and in
`LatentSync\latentsync\utils\image_processor.py` change
`from .face_detector import FaceDetector` to
`from .mp_face_detector import FaceDetector  # MediaPipe (Apache-2.0) instead of InsightFace`.

Use the 1.5 checkpoint with `configs/unet/stage2.yaml` (256 px, fits 12 GB); 1.6 needs 18 GB.

The reference clips, from a recording of the owner talking to camera (ffmpeg):

```
ffmpeg -i owner.mp4 -ss <start> -t <seconds> -vf "crop=1080:900:0:0,fps=25" -an -c:v libx264 -crf 16 ref/face_drive.mp4
ffmpeg -i owner.mp4 -t 10 -vn -ac 1 -ar 24000 ref/voice_ref10.wav
```

Crop so no burned-in captions or logos remain; check a contact sheet of the clip.
