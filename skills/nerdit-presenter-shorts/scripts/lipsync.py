"""Lip-sync the owner's face clip to the recorded voice with LatentSync 1.5 (Apache-2.0).

    python lipsync.py --latentsync <LatentSync folder> --python <sync venv python> \
        --face <presenter>/ref/face_drive.mp4 --voice <voice.wav> --out <face-voice.mp4> [--print]

Runs scripts.inference from the LatentSync folder with ffmpeg on PATH. With --print (or when
the agent may not run code from that repo) it only prints the PowerShell command for the user.
The face clip loops when the voice is longer than it.
"""
import argparse, os, subprocess, sys
from pathlib import Path


def command(python: str, face: Path, voice: Path, out: Path) -> list[str]:
    return [python, "-m", "scripts.inference", "--unet_config_path", "configs/unet/stage2.yaml",
            "--inference_ckpt_path", "checkpoints/latentsync_unet.pt", "--inference_steps", "20",
            "--guidance_scale", "1.5", "--enable_deepcache", "--video_path", str(face),
            "--audio_path", str(voice), "--video_out_path", str(out)]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--latentsync", required=True, type=Path)
    ap.add_argument("--python", required=True)
    ap.add_argument("--face", required=True, type=Path)
    ap.add_argument("--voice", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--print", action="store_true", help="print the command instead of running it")
    a = ap.parse_args(argv)
    cmd = command(a.python, a.face.resolve(), a.voice.resolve(), a.out.resolve())
    scripts = str(Path(a.python).parent)   # ffmpeg.exe is copied there at setup
    if a.print:
        print(f'$env:PATH = "{scripts};$env:PATH"; cd "{a.latentsync}"; '
              + " ".join(f'"{c}"' if " " in c else c for c in cmd))
        return 0
    subprocess.run(cmd, cwd=a.latentsync, check=True, env=dict(os.environ, PATH=scripts + os.pathsep + os.environ["PATH"]))
    print("wrote", a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
