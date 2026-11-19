import subprocess
from pathlib import Path

import imageio_ffmpeg
from PIL import Image

from reel import PADS, probe, reel_command

FF = imageio_ffmpeg.get_ffmpeg_exe()


def test_command_overlays_cues_with_enable_windows_and_keeps_clip_audio():
    cmd = reel_command("ffmpeg", Path("c.mp4"), Path("b.png"), Path("f.png"), [(Path("q1.png"), 4.0, 6.2)],
                       Path("cta.png"), 51.0, Path("o.mp4"))
    graph = cmd[cmd.index("-filter_complex") + 1]
    assert "scale=1000:562" in graph and "overlay=40:520" in graph
    assert "between(t,4.000,6.200)" in graph and "gte(t,49.000)" in graph
    assert cmd[cmd.index("-t") + 1] == "51.000"
    assert cmd[-1] == "o.mp4" and "libx264" in cmd and "+faststart" in cmd


def test_voice_is_mixed_over_a_soft_pad_that_ducks_under_it():
    cmd = reel_command("ffmpeg", Path("c.mp4"), Path("b.png"), Path("f.png"), [], Path("cta.png"), 51.0, Path("o.mp4"),
                       pad=PADS["ember"])
    graph = cmd[cmd.index("-filter_complex") + 1]
    assert "[1:a]" in graph and "aevalsrc=" in graph and "164.81" in graph
    assert "sidechaincompress" in graph and "amix=inputs=2:duration=first:normalize=0" in graph
    assert cmd[cmd.index("-map", cmd.index("-map") + 1) + 1] == "[a]"
    assert "48000" in graph


def test_each_theme_has_its_own_chord():
    assert len({tuple(v) for v in PADS.values()}) == len(PADS) == 5


def run_synthetic_reel(tmp: Path) -> Path:
    clip = tmp / "c.mp4"
    subprocess.run([FF, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30:duration=3",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=3", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-shortest", str(clip)], check=True)
    Image.new("RGB", (1080, 1920), "#003b6c").save(tmp / "b.png")
    for name in ("f.png", "q.png", "cta.png"):
        Image.new("RGBA", (1080, 1920), (0, 0, 0, 0)).save(tmp / name)
    out = tmp / "o.mp4"
    subprocess.run(reel_command(FF, clip, tmp / "b.png", tmp / "f.png", [(tmp / "q.png", 0.5, 1.5)], tmp / "cta.png",
                                3.0, out), check=True)
    return out


def test_reel_from_a_synthetic_clip_is_1080x1920_with_audio(tmp_path):
    out = run_synthetic_reel(tmp_path)
    info = probe(out)
    assert info["size"] == (1080, 1920) and info["fps"] == 30 and info["audio"] and 2.9 <= info["seconds"] <= 3.1
    err = subprocess.run([FF, "-hide_banner", "-i", str(out)], capture_output=True, text=True).stderr
    assert "48000 Hz" in err and "stereo" in err


def max_volume(path: Path) -> float:
    import re
    err = subprocess.run([FF, "-hide_banner", "-i", str(path), "-af", "volumedetect", "-vn", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    return float(re.search(r"max_volume: (-?\d+(?:\.\d+)?) dB", err)[1])


def test_voice_keeps_its_loudness_in_the_reel(tmp_path):
    out = run_synthetic_reel(tmp_path)
    assert abs(max_volume(out) - max_volume(tmp_path / "c.mp4")) < 1.5


def test_without_the_pad_the_reel_carries_only_the_voice():
    cmd = reel_command("ffmpeg", Path("c.mp4"), Path("b.png"), Path("f.png"), [], Path("cta.png"), 51.0, Path("o.mp4"), pad=None)
    graph = cmd[cmd.index("-filter_complex") + 1]
    assert "aevalsrc" not in graph and "amix" not in graph and "[1:a]" in graph
    assert cmd[cmd.index("-map", cmd.index("-map") + 1) + 1] == "[a]"
