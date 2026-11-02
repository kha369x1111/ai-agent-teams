"""30 FPS Vertical Reels Compositor (1080×1920 · 9:16 · Chiaroscuro + 2.5D Depth + VFX).

Assembles:
  • Retouched & color-graded 9:16 plates with Virtual Camera (Dolly In / Slow Orbit)
  • 2.5D Depth Parallax + Peripheral Optical Depth-of-Field (Bokeh)
  • Floating volumetric golden dust motes
  • Smooth cinematic dissolves between shots & scenes
  • Per-frame Sacred Calligraphic, Geometric, Particle & Cosmic VFX (`sacred_vfx.py`)
  • Ornamental manuscript scene headers + waveform-locked highlighted Arabic subtitles
  • H.264 High Profile (`CRF 17`) + 48 kHz `192 kbps` AAC master audio + Vertical Poster
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
from pathlib import Path

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "project"))
sys.path.insert(0, str(_ROOT / "tools"))

import artext  # noqa: E402
import reel_spec as R  # noqa: E402
import sacred_vfx as V  # noqa: E402

FF = imageio_ffmpeg.get_ffmpeg_exe()
W, H = R.W, R.H
FPS = R.FPS
DISSOLVE_SEC = 0.72

# Virtual camera profiles: (z0, z1, dx0, dx1, dy0, dy1)
CAMERA_MOVES = {
    "dolly_in_fast":    (1.00, 1.16,  0.00,  0.00,  0.00,  0.00),
    "dolly_in":         (1.00, 1.12,  0.00,  0.00,  0.00, -0.02),
    "slow_orbit_in":    (1.02, 1.13, -0.03, +0.03, +0.01, -0.01),
    "slow_orbit_right": (1.06, 1.12, -0.04, +0.04,  0.00,  0.00),
    "slow_orbit_left":  (1.04, 1.11, +0.03, -0.03, +0.01, -0.01),
    "macro_dive":       (1.00, 1.22,  0.00,  0.00,  0.02, -0.01),
    "tilt_ascend":      (1.10, 1.16,  0.00,  0.00, +0.05, -0.05),
    "sovereign_push":   (1.00, 1.13, -0.02, +0.02, +0.02, -0.02),
    "pull_out_seal":    (1.13, 1.01,  0.00,  0.00, -0.02, +0.01),
}


def ease_sine(u: float) -> float:
    u = max(0.0, min(1.0, u))
    return 0.5 - 0.5 * math.cos(math.pi * u)


def make_vignette_and_dof_mask() -> tuple[Image.Image, Image.Image]:
    """Create cinema Chiaroscuro edge vignette & radial optical Depth-of-Field mask."""
    yy = np.linspace(-1.0, 1.0, H, dtype=np.float32)[:, None]
    xx = np.linspace(-1.0, 1.0, W, dtype=np.float32)[None, :]
    r2 = (xx * 0.95) ** 2 + (yy * 0.82) ** 2

    # Chiaroscuro edge darkening
    vig_a = np.clip((r2 - 0.42) / 0.88, 0.0, 1.0) ** 1.25 * 165.0
    vig = np.zeros((H, W, 4), dtype=np.uint8)
    vig[..., :3] = (6, 5, 8)
    vig[..., 3] = vig_a.astype(np.uint8)

    # Radial DOF mask: 255 in center sharp zone, 0 at far edges (so edges get shallow lens blur)
    dof = np.clip(1.0 - np.clip((r2 - 0.36) / 0.72, 0.0, 1.0), 0.15, 1.0) * 255.0
    return Image.fromarray(vig, mode="RGBA"), Image.fromarray(dof.astype(np.uint8), mode="L")


def init_dust_motes(count: int = 55):
    rng = np.random.default_rng(777)
    return {
        "x": rng.uniform(0, W, count).astype(np.float32),
        "y": rng.uniform(0, H, count).astype(np.float32),
        "vx": rng.uniform(-7.5, 7.5, count).astype(np.float32),
        "vy": rng.uniform(-22.0, -7.0, count).astype(np.float32),
        "r": rng.uniform(1.2, 3.4, count).astype(np.float32),
        "a": rng.uniform(35, 115, count).astype(np.float32),
        "ph": rng.uniform(0, 2 * math.pi, count).astype(np.float32),
    }


def draw_dust_motes(frame: Image.Image, motes: dict, t: float):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    xs = (motes["x"] + motes["vx"] * t + 14.0 * np.sin(t * 0.45 + motes["ph"])) % W
    ys = (motes["y"] + motes["vy"] * t) % H
    twinkle = 0.55 + 0.45 * np.sin(t * 1.9 + motes["ph"])
    for i in range(len(xs)):
        x, y, r = float(xs[i]), float(ys[i]), float(motes["r"][i])
        alpha = int(motes["a"][i] * twinkle[i])
        d.ellipse([x - r, y - r, x + r, y + r], fill=(248, 218, 152, alpha))
    frame.alpha_composite(layer)


def render_camera_parallax(
    plate: Image.Image,
    plate_blur: Image.Image,
    dof_mask: Image.Image,
    shot: dict,
    u: float,
) -> Image.Image:
    """2.5D virtual camera (Dolly + Orbit) with subtle optical Depth-of-Field."""
    z0, z1, dx0, dx1, dy0, dy1 = CAMERA_MOVES.get(shot["move"], CAMERA_MOVES["dolly_in"])
    fx_base, fy_base = shot.get("focus", [0.5, 0.5])
    e = ease_sine(u)

    z_fg = z0 + (z1 - z0) * e
    z_bg = 1.0 + (z_fg - 1.0) * 0.52
    fx = min(0.75, max(0.25, fx_base + dx0 + (dx1 - dx0) * e))
    fy = min(0.75, max(0.25, fy_base + dy0 + (dy1 - dy0) * e))

    def crop_zoom(src: Image.Image, z: float, sx_off: float = 0.0) -> Image.Image:
        cw, ch = src.width / z, src.height / z
        cx = min(max((fx + sx_off) * src.width - cw / 2, 0), src.width - cw)
        cy = min(max(fy * src.height - ch / 2, 0), src.height - ch)
        box = (int(round(cx)), int(round(cy)), int(round(cx + cw)), int(round(cy + ch)))
        return src.crop(box).resize((W, H), Image.BILINEAR)

    fg_sharp = crop_zoom(plate, z_fg, sx_off=(e - 0.5) * 0.012)
    bg_soft  = crop_zoom(plate_blur, z_bg, sx_off=-(e - 0.5) * 0.008)
    return Image.composite(fg_sharp, bg_soft, dof_mask).convert("RGBA")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", default=str(_ROOT / "_work/master_mix.wav"))
    ap.add_argument("--subs", default=str(_ROOT / "_work/subtitles.json"))
    ap.add_argument("--out", default=str(_ROOT / "deliver/baa_secret_reel_1080x1920.mp4"))
    ap.add_argument("--crf", default="17")
    args = ap.parse_args()

    font_callig = str(_ROOT / "assets/fonts/Amiri-Bold.ttf")
    font_title  = str(_ROOT / "assets/fonts/Amiri-Bold.ttf")
    font_sub    = str(_ROOT / "assets/fonts/Tajawal-Bold.ttf")

    print("  • تجهيز اللوحات البصرية ومعالجة Chiaroscuro...", flush=True)
    raw_dir = _ROOT / "storyboard/raw"
    plates: dict[str, tuple[Image.Image, Image.Image]] = {}
    all_shots = []
    for sc in R.SCENES:
        for sh in sc["shots"]:
            sh_copy = dict(sh)
            sh_copy["scene"] = sc
            all_shots.append(sh_copy)
            iname = sh["img"]
            if iname not in plates:
                clean = V.retouch_raw_plate(iname, Image.open(raw_dir / f"{iname}.jpg"))
                blurred = clean.filter(ImageFilter.GaussianBlur(7))
                plates[iname] = (clean, blurred)

    print("  • تجهيز بطاقات الترجمة العربية المتزامنة...", flush=True)
    subs_raw = json.loads(Path(args.subs).read_text())
    subs = []
    for s in subs_raw:
        img = artext.render_subtitle_plate(s["text"], s["highlight"], font_sub, size=42, max_width=900)
        subs.append({**s, "_img": img})

    vignette, dof_mask = make_vignette_and_dof_mask()
    motes = init_dust_motes(55)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        FF, "-y",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-i", str(args.audio),
        "-c:v", "libx264", "-preset", "fast", "-crf", str(args.crf),
        "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.2",
        "-movflags", "+faststart",
        "-c:a", "aac", "-b:a", "192k", "-shortest",
        str(out_path),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    total_frames = int(round(R.TOTAL_DURATION * FPS))
    t0 = time.time()

    def compose_raw_shot(sh: dict, t_glob: float) -> Image.Image:
        p_sharp, p_blur = plates[sh["img"]]
        u = (t_glob - sh["start"]) / max(0.01, sh["end"] - sh["start"])
        frm = render_camera_parallax(p_sharp, p_blur, dof_mask, sh, u)
        V.render_scene_vfx(frm, sh["scene"], t_glob, font_callig, font_title)
        return frm

    print(f"  • بدء الرندر السينمائي ({total_frames} إطار · 1080×1920 · 30 FPS)...", flush=True)
    for f_idx in range(total_frames):
        t = f_idx / FPS

        # Find active shot & previous shot for smooth cinematic dissolve
        active_idx = 0
        for idx, sh in enumerate(all_shots):
            if sh["start"] <= t < sh["end"]:
                active_idx = idx
                break
        else:
            active_idx = len(all_shots) - 1

        cur_sh = all_shots[active_idx]
        frame = compose_raw_shot(cur_sh, t)

        # Smooth S-curve cinematic dissolve across shot transitions
        dt_shot = t - cur_sh["start"]
        if active_idx > 0 and 0.0 <= dt_shot < DISSOLVE_SEC:
            prev_sh = all_shots[active_idx - 1]
            prev_frame = compose_raw_shot(prev_sh, t)
            k = ease_sine(dt_shot / DISSOLVE_SEC)
            frame = Image.blend(prev_frame, frame, k)

        # Atmospheric floating dust motes & Chiaroscuro optical vignette
        draw_dust_motes(frame, motes, t)
        frame.alpha_composite(vignette)

        # Ornamental manuscript scene header
        V.draw_scene_banner(frame, cur_sh["scene"], t, font_title)

        # Synchronized Arabic subtitles (strictly non-overlapping, lower Reels safe zone)
        for sb in subs:
            if sb["start"] <= t <= sb["end"]:
                fin, fout = 0.18, 0.18
                alpha = 1.0
                dy = 0
                if t - sb["start"] < fin:
                    u_in = (t - sb["start"]) / fin
                    alpha = ease_sine(u_in)
                    dy = int(round((1.0 - alpha) * 8))
                if sb["end"] - t < fout:
                    alpha = min(alpha, ease_sine((sb["end"] - t) / fout))
                if alpha > 0.01:
                    s_img = sb["_img"]
                    if alpha < 0.995:
                        s_img = s_img.copy()
                        s_img.putalpha(s_img.getchannel("A").point(lambda p: int(p * alpha)))
                    sx = (W - s_img.width) // 2
                    sy = 1525 - s_img.height // 2 + dy
                    frame.alpha_composite(s_img, (sx, sy))
                break

        # Final 1.0s fade to velvet charcoal black
        if R.TOTAL_DURATION - t < 0.95:
            fade_out = 1.0 - ease_sine((R.TOTAL_DURATION - t) / 0.95)
            if fade_out > 0.01:
                blk = Image.new("RGBA", (W, H), (5, 4, 7, int(255 * fade_out)))
                frame.alpha_composite(blk)

        proc.stdin.write(np.asarray(frame.convert("RGB"), dtype=np.uint8).tobytes())

        if (f_idx + 1) % 300 == 0 or f_idx == total_frames - 1:
            el = time.time() - t0
            fps_rate = (f_idx + 1) / max(0.01, el)
            rem = (total_frames - f_idx - 1) / max(0.1, fps_rate)
            print(f"    [{f_idx+1:4d}/{total_frames}]  t={t:5.1f}s/{R.TOTAL_DURATION:.1f}s  "
                  f"speed={fps_rate:4.1f} fps  ETA={rem:4.1f}s", flush=True)

    proc.stdin.close()
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"FFmpeg exited with code {rc}")

    # Extract high-impact vertical poster frame from Scene 6 sovereign hero moment (t = 56.5s)
    poster_path = out_path.parent / "poster.jpg"
    subprocess.run(
        [FF, "-y", "-ss", "56.5", "-i", str(out_path), "-frames:v", "1", "-q:v", "2", str(poster_path)],
        capture_output=True, check=True,
    )
    size_mb = out_path.stat().st_size / (1024 * 1024)
    print(f"  ✓ اكتمل رندر الريلز النهائي: {out_path} ({size_mb:.1f} MB) + الغلاف: {poster_path}", flush=True)


if __name__ == "__main__":
    main()
