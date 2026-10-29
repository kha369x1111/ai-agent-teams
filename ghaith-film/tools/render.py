"""Frame-accurate compositor for the Ghaith short film.

Renders the whole timeline in one pass: virtual camera (Ken Burns) moves,
soft dissolves between shots, caption overlays with alpha fades, then encodes
H.264 and muxes the mixed audio — no heavy ffmpeg filter graphs, so memory
stays flat on small machines.

    python3 tools/render.py --timeline build/timeline.json --audio build/mix.wav \
                            --out out/film.mp4
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).parent))
import artext  # noqa: E402
import imageio_ffmpeg  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FF = imageio_ffmpeg.get_ffmpeg_exe()
W, H = 1920, 1080
FPS = 24
SS = 2  # source upscale for smooth sub-pixel camera motion
DISSOLVE = 0.55

MOVES = {
    "push_in":    (1.00, 1.12, 0.50, 0.50, 0.50, 0.50),
    "pull_out":   (1.13, 1.00, 0.50, 0.50, 0.50, 0.50),
    "close_push": (1.16, 1.30, 0.50, 0.50, 0.50, 0.50),
    "pan_right":  (1.13, 1.13, 0.34, 0.66, 0.50, 0.50),
    "pan_left":   (1.13, 1.13, 0.66, 0.34, 0.50, 0.50),
    "tilt_up":    (1.16, 1.16, 0.50, 0.50, 0.70, 0.36),
    "diag":       (1.04, 1.18, 0.38, 0.60, 0.58, 0.44),
    "hold_drift": (1.05, 1.09, 0.50, 0.50, 0.50, 0.50),
}


def ease(u: float) -> float:
    return u * u * (3 - 2 * u)


class Shot:
    """A rendered shot: source image + camera path + captions active in it."""

    def __init__(self, spec: dict, root: Path):
        self.spec = spec
        self.id = spec["id"]
        self.start = spec["start"]
        self.dur = spec["dur"]
        self.clip = None
        if "card" in spec:
            self.src = root / "_work/cards" / f"{spec['card']}.png"
        else:
            base = None
            for ext in (".png", ".jpg"):
                cand = root / "storyboard/raw" / f"{spec['img']}{ext}"
                if cand.exists():
                    base = cand
                    break
            self.src = base or (root / "storyboard/raw" / f"{spec['img']}.png")
            animated = root / "storyboard/clips" / f"{spec['img']}.mp4"
            if animated.exists():
                self.clip = animated
        self.move = MOVES.get(spec.get("move", "push_in"), MOVES["push_in"])
        if "focus" in spec:
            fx, fy = spec["focus"]
            z0, z1 = self.move[0], self.move[1]
            self.move = (z0, z1, fx, fx, fy, fy)

    @property
    def end(self):
        return self.start + self.dur

    def camera(self, t_local: float):
        z0, z1, fx0, fx1, fy0, fy1 = self.move
        u = 0.0 if self.dur <= 0 else min(1.0, max(0.0, t_local / self.dur))
        e = ease(u)
        z = z0 + (z1 - z0) * e
        fx = fx0 + (fx1 - fx0) * e
        fy = fy0 + (fy1 - fy0) * e
        return z, fx, fy

    def frame_parallax(self, base: Image.Image, t_local: float, strength: float = 1.0,
                       mask: Image.Image | None = None) -> Image.Image:
        """طبقتان بعمق مختلف: خلفية أبطأ ومقدمة أسرع، تُدمجان بقناع ناعم."""
        z, fx, fy = self.camera(t_local)
        dx = 0.012 * strength
        back = crop_layer(base, max(1.0, z - 0.05 * strength), fx, fy, -dx)
        front = crop_layer(base, z + 0.06 * strength, fx, fy, dx * 1.6)
        if mask is None:
            mask = depth_mask(fx, fy)
        return Image.composite(front, back, mask)

    def frame(self, base: Image.Image, t_local: float) -> Image.Image:
        z, fx, fy = self.camera(t_local)
        bw, bh = base.width / z, base.height / z
        x = min(max(fx * base.width - bw / 2, 0), base.width - bw)
        y = min(max(fy * base.height - bh / 2, 0), base.height - bh)
        px, py = int(round(x)), int(round(y))
        box = (px, py, min(base.width, px + int(round(bw))), min(base.height, py + int(round(bh))))
        return base.crop(box).resize((W, H), Image.BILINEAR)


def depth_mask(fx: float, fy: float, rx: float = 0.60, ry: float = 0.58) -> Image.Image:
    """قناع عمق ناعم: أبيض (مقدمة) حول نقطة التركيز، أسود (خلفية) في الأطراف."""
    w, h = W // 2, H // 2
    m = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(m)
    cx, cy = fx * w, fy * h
    d.ellipse([cx - rx * w, cy - ry * h, cx + rx * w, cy + ry * h], fill=255)
    return m.filter(ImageFilter.GaussianBlur(70)).resize((W, H), Image.BILINEAR)


def crop_layer(base: Image.Image, z: float, fx: float, fy: float, dx: float = 0.0) -> Image.Image:
    bw, bh = base.width / z, base.height / z
    x = min(max((fx + dx) * base.width - bw / 2, 0), base.width - bw)
    y = min(max(fy * base.height - bh / 2, 0), base.height - bh)
    box = (int(round(x)), int(round(y)),
           min(base.width, int(round(x + bw))), min(base.height, int(round(y + bh))))
    return base.crop(box).resize((W, H), Image.BILINEAR)


class ClipReader:
    """Reads decoded frames from an animated shot (mp4) sequentially."""

    def __init__(self, path: Path):
        self.path = path
        self.proc = None
        self.index = -1
        self.size = W * H * 3

    def _spawn(self):
        self.close()
        self.proc = subprocess.Popen(
            [FF, "-v", "error", "-i", str(self.path), "-f", "rawvideo",
             "-pix_fmt", "rgb24", "-"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.index = -1

    def frame(self, idx: int) -> Image.Image | None:
        if self.proc is None or idx < self.index:
            self._spawn()
        while self.index < idx:
            buf = self.proc.stdout.read(self.size)
            if not buf or len(buf) < self.size:
                return None
            self.index += 1
        if self.index != idx:
            return None
        # index == idx already read on a previous call -> keep last frame
        return self._last

    def read_next(self) -> Image.Image | None:
        buf = self.proc.stdout.read(self.size) if self.proc else None
        if not buf or len(buf) < self.size:
            return None
        self.index += 1
        self._last = Image.frombytes("RGB", (W, H), buf)
        return self._last

    def close(self):
        if self.proc:
            try:
                self.proc.stdout.close()
            except Exception:
                pass
            self.proc.kill()
            self.proc.wait()
            self.proc = None


@lru_cache(maxsize=6)
def load_base(path: str, mtime: float) -> Image.Image:
    img = Image.open(path).convert("RGB")
    img = img.resize((img.width * SS, img.height * SS), Image.LANCZOS)
    return img


def base_of(shot: Shot, fallback: Path) -> Image.Image:
    path = shot.src if shot.src.exists() else fallback
    return load_base(str(path), path.stat().st_mtime)


# --------------------------------------------------------------------------- #
def draw_caption(frame: Image.Image, cap: dict, alpha: float):
    if alpha <= 0.003 or not Path(cap["path"]).exists():
        return frame
    img = cap["_img"]
    if alpha < 0.999:
        a = img.getchannel("A").point(lambda v: int(v * alpha))
        img = img.copy()
        img.putalpha(a)
    frame.alpha_composite(img, (cap["x"], cap["y"]))
    return frame


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeline", default="_work/timeline.json")
    ap.add_argument("--audio", default="_work/mix.wav")
    ap.add_argument("--out", default="deliver/ghaith_alhurras_1080p.mp4")
    ap.add_argument("--crf", default="18")
    ap.add_argument("--from", dest="t_from", type=float, default=0.0)
    ap.add_argument("--to", dest="t_to", type=float, default=None)
    ap.add_argument("--shots", nargs="*", help="only these shot ids (debug)")
    ap.add_argument("--parallax", type=float, default=0.0,
                    help="تحريك بعمق 2.5D بقوة 0..1.5 (0 = معطّل)")
    a = ap.parse_args()

    tl = json.loads(Path(a.timeline).read_text())
    total = tl["total"] if a.t_to is None else a.t_to
    t_from = a.t_from

    shots = [Shot(s, ROOT) for s in tl["shots"]]
    if a.shots:
        shots = [s for s in shots if s.id in a.shots]
    for s in shots:
        if not s.src.exists():
            print(f"!! {s.id}: missing {s.src.name}")
    fallback = ROOT / "_work/cards/title.png"

    caps = []
    for c in tl["captions"]:
        if c["start"] > total:
            continue
        c = dict(c)
        if Path(c["path"]).exists():
            c["_img"] = Image.open(c["path"]).convert("RGBA")
            caps.append(c)

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [FF, "-y",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-"]
    has_audio = Path(a.audio).exists()
    if has_audio:
        cmd += ["-ss", f"{t_from:.3f}", "-i", str(a.audio)]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", a.crf, "-pix_fmt", "yuv420p",
            "-profile:v", "high", "-movflags", "+faststart"]
    if has_audio:
        cmd += ["-c:a", "aac", "-b:a", "192k", "-shortest"]
    cmd += [str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    n0 = int(round(t_from * FPS))
    n1 = int(round(total * FPS))
    idx = 0
    t0 = time.time()
    prev_shot: Shot | None = None
    cur_shot = None
    cur_base = None
    prev_last = None
    last_frame = None
    readers: dict[str, ClipReader] = {}
    parallax_masks: dict = {}
    par_mode = max(0.0, a.parallax)
    animated = sum(1 for s in shots if s.clip)
    if animated:
        print(f"  animated shots: {animated}/{len(shots)} (storyboard/clips)", flush=True)
    if par_mode:
        print(f"  parallax depth: {par_mode:.2f}", flush=True)

    for n in range(n0, n1):
        t = n / FPS
        # active shot
        shot = None
        for s in shots:
            if s.start <= t < s.end:
                shot = s
                break
        if shot is None:
            shot = shots[-1]
        if shot is not cur_shot:
            prev_shot = cur_shot
            prev_last = last_frame
            cur_shot = shot
            cur_base = None if shot.clip else base_of(shot, fallback)

        if cur_shot.clip is not None:
            reader = readers.get(cur_shot.id)
            if reader is None:
                reader = readers[cur_shot.id] = ClipReader(cur_shot.clip)
            frame = reader.read_next()
            if frame is None:                      # clip shorter than the shot
                frame = last_frame or Image.new("RGB", (W, H), (20, 16, 24))
        elif par_mode > 0:
            pm = parallax_masks.get(cur_shot.id)
            if pm is None:
                fx, fy = cur_shot.spec.get("focus", [0.5, 0.5])[:2]
                pm = depth_mask(fx, fy)
                parallax_masks[cur_shot.id] = pm
            frame = cur_shot.frame_parallax(cur_base, t - cur_shot.start, par_mode, pm)
        else:
            frame = cur_shot.frame(cur_base, t - cur_shot.start)
        frame = frame.convert("RGBA")

        last_frame = frame

        # dissolve from the previous shot's final frame
        if prev_shot is not None and prev_last is not None:
            dt = t - cur_shot.start
            if 0 <= dt < DISSOLVE:
                k = ease(dt / DISSOLVE)
                frame = Image.blend(prev_last, frame, k)

        # captions
        for c in caps:
            if c["start"] <= t <= c["end"]:
                fin, fout = 0.28, 0.24
                alpha = 1.0
                if t - c["start"] < fin:
                    alpha = (t - c["start"]) / fin
                if c["end"] - t < fout:
                    alpha = min(alpha, (c["end"] - t) / fout)
                frame = draw_caption(frame, c, max(0.0, alpha))

        arr = np.asarray(frame.convert("RGB"), dtype=np.uint8)
        proc.stdin.write(arr.tobytes())

        idx += 1
        if idx % 240 == 0:
            el = time.time() - t0
            rate = idx / el
            print(f"  {t:7.1f}s / {total:.1f}s   {rate:5.1f} fps  eta {(total-t)/rate/60:4.1f} min",
                  flush=True)

    for r in readers.values():
        r.close()
    proc.stdin.close()
    proc.wait()
    print(f"done -> {out}  ({idx} frames)")
    # poster
    poster = out.parent / "poster.jpg"
    subprocess.run([FF, "-y", "-ss", "6", "-i", str(out), "-frames:v", "1", "-q:v", "2",
                    str(poster)], capture_output=True)
    print("poster ->", poster)


if __name__ == "__main__":
    main()
