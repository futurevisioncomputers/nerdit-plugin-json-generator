"""Match user images in incoming/ to manifest slots, convert them to WebP and write previews.

Usage: python convert_images.py --images-dir <dir>
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

import manifest as mf

ACCEPTED = (".png", ".jpg", ".jpeg", ".webp")
MAX_WIDTH = 1200
PREVIEW_WIDTH = 640
TARGET_BYTES = 150_000
HARD_LIMIT_BYTES = 250_000
START_QUALITY = 80
FLOOR_QUALITY = 60


def _prepare(im: Image.Image) -> Image.Image:
    im.seek(0)  # first frame of an animated file
    im = ImageOps.exif_transpose(im)
    if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
        return im.convert("RGBA")
    return im.convert("RGB")


def _scaled(img: Image.Image, width: int) -> Image.Image:
    if img.width <= width:
        return img
    return img.resize((width, round(img.height * width / img.width)), Image.LANCZOS)


def encode_webp(source: Path | bytes) -> tuple[bytes, int, int, int]:
    with Image.open(BytesIO(source) if isinstance(source, bytes) else source) as im:
        img = _prepare(im)
    img = _scaled(img, MAX_WIDTH)
    q = START_QUALITY
    while True:
        buf = BytesIO()
        img.save(buf, "WEBP", quality=q, method=6)
        data = buf.getvalue()
        if len(data) <= TARGET_BYTES or q <= FLOOR_QUALITY:
            return data, img.width, img.height, q
        q = max(FLOOR_QUALITY, q - 5)


def _write_preview(webp: bytes, dst: Path) -> None:
    with Image.open(BytesIO(webp)) as im:
        img = im.convert("RGBA")
    flat = Image.new("RGB", img.size, (255, 255, 255))
    flat.paste(img, mask=img.split()[3])
    _scaled(flat, PREVIEW_WIDTH).save(dst, "JPEG", quality=80)


def find_incoming(m: dict, incoming: Path) -> tuple[dict[str, Path], list[str], list[str]]:
    wanted = {Path(s["requestFile"]).stem.lower(): s["id"] for s in m["images"]}
    files, unexpected = {}, []
    if incoming.is_dir():
        for f in sorted(incoming.iterdir()):
            if not f.is_file() or f.name.startswith("."):
                continue
            image_id = wanted.get(f.stem.lower()) if f.suffix.lower() in ACCEPTED else None
            if image_id is None:
                unexpected.append(f.name)
            elif image_id in files:
                unexpected.append(f"{f.name} (duplicate)")
            else:
                files[image_id] = f
    missing = [s["id"] for s in m["images"] if s["id"] not in files and s["status"] in ("planned", "failed")]
    return files, missing, unexpected


def convert_all(m: dict, images_dir: Path) -> dict:
    images_dir = Path(images_dir)
    files, missing, unexpected = find_incoming(m, images_dir / "incoming")
    (images_dir / "upload").mkdir(exist_ok=True)
    (images_dir / "preview").mkdir(exist_ok=True)
    report = {"converted": [], "unchanged": [], "errors": [], "warnings": [],
              "missing": missing, "unexpected": unexpected}
    slots = {s["id"]: s for s in m["images"]}
    for image_id, f in files.items():
        slot = slots[image_id]
        sha = hashlib.sha256(f.read_bytes()).hexdigest()
        if sha == slot.get("sourceSha256") and slot["status"] != "planned":
            report["unchanged"].append(image_id)
            continue
        try:
            data, w, h, q = encode_webp(f)
        except (UnidentifiedImageError, OSError) as e:
            report["errors"].append(f"{f.name}: cannot read image ({e})")
            continue
        if len(data) > HARD_LIMIT_BYTES:
            report["errors"].append(f"{f.name}: {len(data) // 1000} KB after compression, over the 250 KB limit")
            continue
        if len(data) > TARGET_BYTES:
            report["warnings"].append(f"{f.name}: {len(data) // 1000} KB at quality {q}, above the 150 KB target")
        (images_dir / "upload" / slot["outputFile"]).write_bytes(data)
        _write_preview(data, images_dir / "preview" / f"{image_id}.jpg")
        slot.update(status="converted", sourceSha256=sha, bytes=len(data), width=w, height=h)
        slot["check"] = {"result": None, "reason": None}
        report["converted"].append(image_id)
    return report


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--images-dir", required=True)
    images_dir = Path(ap.parse_args().images_dir)
    m = mf.load(images_dir)
    report = convert_all(m, images_dir)
    mf.save(images_dir, m)
    (images_dir / "PROMPTS.md").write_text(mf.render_prompts(m), encoding="utf-8")
    print(f"Converted {len(report['converted'])} · unchanged {len(report['unchanged'])} · "
          f"missing {len(report['missing'])} · errors {len(report['errors'])}")
    for key in ("errors", "warnings"):
        for line in report[key]:
            print(f"  {key[:-1]}: {line}")
    if report["missing"]:
        print("  waiting for: " + ", ".join(f"{i}.png" for i in report["missing"]))
    if report["unexpected"]:
        print("  ignored files: " + ", ".join(report["unexpected"]))
    print(f"Previews to check: {images_dir / 'preview'}")
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
