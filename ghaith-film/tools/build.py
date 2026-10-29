"""Assembly pipeline for «فريق الحراسة السرّي: مرحباً بك يا غيث».

    python3 tools/build.py plan            # compute timeline + print shot table
    python3 tools/build.py all             # full render

Steps: cards -> shot clips (Ken Burns) -> concat -> captions/lyrics overlay
       -> music score + voice placement + ducking -> final mux.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

_ROOT = Path(__file__).resolve().parent.parent
for _p in (_ROOT / "tools", _ROOT / "script", _ROOT / "project"):
    sys.path.insert(0, str(_p))

import artext  # noqa: E402
import imageio_ffmpeg  # noqa: E402
import lines_data  # noqa: E402
import shots_data  # noqa: E402

ROOT = _ROOT
FONT_B = str(ROOT / "assets/fonts/Tajawal-Bold.ttf")
FONT_M = str(ROOT / "assets/fonts/Tajawal-Medium.ttf")
FONT_R = str(ROOT / "assets/fonts/Tajawal-Regular.ttf")
FONT_BLACK = str(ROOT / "assets/fonts/Tajawal-Black.ttf")

BUILD = ROOT / "_work"
OUT = ROOT / "deliver"
SHOTS_DIR = BUILD / "shots"
CAP_DIR = BUILD / "caps"
CARD_DIR = BUILD / "cards"
RAW = ROOT / "storyboard/raw"
LINES_DIR = ROOT / "audio/lines"
LINES_WAV = ROOT / "audio/lines_wav"
CHARS_PER_SEC = 9.6

FF = imageio_ffmpeg.get_ffmpeg_exe()
W, H = 1920, 1080
FPS = 24
UPSCALE = (3840, 2160)
SONG_TEMPO = 0.85


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def run(cmd, quiet=True):
    if not quiet:
        print(" ".join(str(c) for c in cmd))
    p = subprocess.run([str(c) for c in cmd], capture_output=True, text=True)
    if p.returncode != 0:
        print(p.stderr[-3000:])
        raise RuntimeError(f"command failed: {cmd[:3]}")
    return p


def probe_duration(path: Path) -> float:
    if not path.exists():
        return -1.0
    p = subprocess.run([FF, "-i", str(path)], capture_output=True, text=True)
    for tok in p.stderr.split():
        if tok.startswith("Duration:"):
            break
    import re
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.?\d*)", p.stderr)
    if not m:
        return -1.0
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def load_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as w:
        n, ch, sw = w.getnframes(), w.getnchannels(), w.getsampwidth()
        data = w.readframes(n)
    assert sw == 2
    a = np.frombuffer(data, dtype="<i2").astype(np.float32) / 32768.0
    if ch == 1:
        a = np.stack([a, a], axis=1)
    else:
        a = a.reshape(-1, ch)[:, :2]
    return a


def save_wav(path: Path, data: np.ndarray):
    d = np.clip(data, -1, 1)
    pcm = (d * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(pcm.tobytes())


def to_wav(src: Path, dst: Path, afilter: str | None = None):
    cmd = [FF, "-y", "-i", str(src)]
    if afilter:
        cmd += ["-filter:a", afilter]
    cmd += ["-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", str(dst)]
    run(cmd)


# --------------------------------------------------------------------------- #
# timeline
# --------------------------------------------------------------------------- #
def line_audio(lid: str, text: str) -> tuple[Path | None, float]:
    """Localise a line's audio: split wav > single mp3 > length estimate."""
    for p in (LINES_WAV / f"{lid}.wav", LINES_DIR / f"{lid}.mp3"):
        if p.exists():
            d = probe_duration(p)
            if d > 0:
                return p, d
    return None, max(1.6, len(text) / CHARS_PER_SEC + 0.55)


def build_timeline():
    spec = shots_data.shots_spec()
    lines = lines_data.lines_by_id()
    lyrics = lines_data.SONG_LYRICS

    durations, missing, sources = {}, [], {}
    for lid, l in lines.items():
        p, d = line_audio(lid, l["text"])
        if p is None:
            missing.append(lid)
        sources[lid] = str(p) if p else None
        durations[lid] = d

    shots, t = [], 0.0
    audio_events, captions = [], []
    for sh in spec["shots"]:
        pad = sh.get("pad", [0.3, 0.5])
        if "lines" in sh:
            dur = pad[0] + sum(durations[l] for l in sh["lines"]) + pad[1]
        else:
            dur = float(sh["dur"])
        rec = dict(sh)
        rec["start"], rec["dur"] = round(t, 3), round(dur, 3)
        shots.append(rec)

        cursor = t + pad[0]
        for lid in sh.get("lines", []):
            audio_events.append({"line": lid, "start": round(cursor, 3), "dur": durations[lid],
                                 "src": sources[lid]})
            l = lines[lid]
            captions.append({
                "start": round(cursor - 0.15, 3),
                "dur": round(durations[lid] + 0.35, 3),
                "text": l["text"],
                "speaker": l["speaker"],
                "kind": l["kind"],
            })
            cursor += durations[lid]
        t += dur

    total = round(t, 3)

    # ---- song block -------------------------------------------------------- #
    song_shots = [s for s in shots if s.get("song")]
    song_line = "09_song"
    song_src, song_dur = line_audio(song_line, lines[song_line]["text"])
    song_dur = song_dur / SONG_TEMPO
    if song_shots:
        song_start = song_shots[0]["start"]
        window = sum(s["dur"] for s in song_shots)
        if song_dur > window:              # keep the anthem inside its visual block
            song_dur = window - 0.4
        audio_events.append({"line": song_line, "start": song_start, "dur": round(song_dur, 3),
                             "tempo": SONG_TEMPO, "src": str(song_src) if song_src else None})
        # karaoke captions
        weights = [max(4, len(x)) for x in lyrics]
        tot = sum(weights)
        lead = 0.15
        cur = song_start + lead
        span = song_dur - lead - 0.2
        for txt, wgt in zip(lyrics, weights):
            d = span * wgt / tot
            captions.append({"start": round(cur, 3), "dur": round(d, 3), "text": txt,
                             "speaker": "البنات", "kind": "song"})
            cur += d

    captions.sort(key=lambda c: c["start"])
    for c in captions:
        c["end"] = round(c["start"] + c["dur"], 3)

    return {
        "fps": FPS, "width": W, "height": H, "total": total,
        "shots": shots, "audio": audio_events, "captions": captions,
        "song": {"start": song_shots[0]["start"] if song_shots else 0,
                 "dur": round(song_dur, 3),
                 "end": round((song_shots[0]["start"] + song_dur) if song_shots else 0, 3)},
        "missing_lines": missing,
    }


# --------------------------------------------------------------------------- #
# cards
# --------------------------------------------------------------------------- #
def _grad(w, h, top, bottom):
    g = np.linspace(0, 1, h)[:, None, None]
    a = np.array(top, dtype=np.float32)[None, None, :]
    b = np.array(bottom, dtype=np.float32)[None, None, :]
    img = (a * (1 - g) + b * g)
    return np.repeat(img, w, axis=1).astype(np.uint8)


def _star(draw, cx, cy, r, fill, points=5, inner=0.44, rot=-math.pi / 2):
    pts = []
    for i in range(points * 2):
        ang = rot + i * math.pi / points
        rad = r if i % 2 == 0 else r * inner
        pts.append((cx + rad * math.cos(ang), cy + rad * math.sin(ang)))
    draw.polygon(pts, fill=fill)


def _bokeh(img: Image.Image, n=26, seed=3):
    rng = np.random.default_rng(seed)
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for _ in range(n):
        r = rng.uniform(30, 150)
        x, y = rng.uniform(0, W), rng.uniform(0, H)
        a = int(rng.uniform(10, 34))
        col = (255, 250, 235, a) if rng.random() > 0.4 else (255, 214, 170, a)
        d.ellipse([x - r, y - r, x + r, y + r], fill=col)
    layer = layer.filter(ImageFilter.GaussianBlur(38))
    return Image.alpha_composite(img.convert("RGBA"), layer)


def make_title_card():
    base = Image.fromarray(_grad(W, H, (255, 224, 189), (255, 249, 240))).convert("RGBA")
    img = _bokeh(base, 30, seed=5)
    d = ImageDraw.Draw(img)
    rng = np.random.default_rng(11)
    for _ in range(22):
        x, y = rng.uniform(60, W - 60), rng.uniform(60, H - 60)
        _star(d, x, y, rng.uniform(6, 16), (255, 255, 255, 120))

    artext.draw_text(img, (W / 2, H * 0.37), "فريق الحراسة السرّي", FONT_BLACK, 132,
                     (120, 66, 30, 255), anchor="mm", shadow=6)
    d.rounded_rectangle([W / 2 - 300, H * 0.475, W / 2 + 300, H * 0.482], radius=4,
                        fill=(214, 150, 90, 255))
    artext.draw_text(img, (W / 2, H * 0.575), "مرحباً بك يا غيث", FONT_B, 96,
                     (176, 104, 48, 255), anchor="mm")
    artext.draw_text(img, (W / 2, H * 0.695), "قصة عائلية قصيرة للأطفال", FONT_M, 44,
                     (140, 96, 62, 220), anchor="mm")
    artext.draw_text(img, (W / 2, H * 0.755), "خالد · سارة · نانا · سوسو · جيجي · غيث",
                     FONT_R, 36, (150, 105, 70, 200), anchor="mm")
    img.convert("RGB").save(CARD_DIR / "title.png")
    return CARD_DIR / "title.png"


def make_end_card():
    base = Image.fromarray(_grad(W, H, (48, 40, 62), (26, 24, 38))).convert("RGBA")
    img = _bokeh(base, 24, seed=9)
    d = ImageDraw.Draw(img)
    rng = np.random.default_rng(4)
    for _ in range(34):
        x, y = rng.uniform(40, W - 40), rng.uniform(40, H - 40)
        _star(d, x, y, rng.uniform(4, 13), (255, 238, 190, int(rng.uniform(60, 170))))

    # little crescent moon
    d.ellipse([W - 360, 90, W - 240, 210], fill=(255, 240, 200, 235))
    d.ellipse([W - 340, 78, W - 208, 200], fill=(38, 33, 50, 255))

    artext.draw_text(img, (W / 2, H * 0.31), "النهاية", FONT_BLACK, 128, (255, 238, 198, 255),
                     anchor="mm")
    artext.draw_text(img, (W / 2, H * 0.455), "فريق الحراسة السرّي", FONT_B, 70,
                     (255, 255, 255, 240), anchor="mm")
    artext.draw_text(img, (W / 2, H * 0.54), "«الحبّ لا ينقسم… الحبّ يكبر»", FONT_M, 46,
                     (255, 214, 160, 235), anchor="mm")
    artext.draw_text(img, (W / 2, H * 0.665), "فكرة وسيناريو: عائلة غيث", FONT_R, 34,
                     (225, 220, 230, 190), anchor="mm")
    artext.draw_text(img, (W / 2, H * 0.723), "رسوم ثلاثية الأبعاد: توليد صور بالذكاء الاصطناعي",
                     FONT_R, 34, (225, 220, 230, 190), anchor="mm")
    artext.draw_text(img, (W / 2, H * 0.781), "موسيقى وتركيب: خط إنتاج الفيلم في هذا المستودع",
                     FONT_R, 34, (225, 220, 230, 190), anchor="mm")
    artext.draw_text(img, (W / 2, H * 0.86), "٢٠٢٦", FONT_M, 34, (200, 195, 205, 160), anchor="mm")
    img.convert("RGB").save(CARD_DIR / "end.png")
    return CARD_DIR / "end.png"


# --------------------------------------------------------------------------- #
# captions
# --------------------------------------------------------------------------- #
def make_caption(cap: dict, idx: int) -> dict:
    kind = cap["kind"]
    if kind == "song":
        text, size, color = cap["text"], 62, (255, 240, 205, 255)
        maxw, font = 1500, FONT_B
    else:
        speaker = cap["speaker"]
        prefix = f"{speaker}: " if kind == "dialogue" else ""
        text = prefix + cap["text"]
        size = 44
        color = (255, 246, 226, 255) if kind == "dialogue" else (232, 240, 255, 255)
        maxw, font = 1420, FONT_M

    timg = artext.render(text, font, size, color, max_width=maxw, line_gap=0.40, align="center")
    padx, pady = 46, 26
    plate = Image.new("RGBA", (timg.width + padx * 2, timg.height + pady * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(plate)
    d.rounded_rectangle([0, 0, plate.width - 1, plate.height - 1], radius=28,
                        fill=(18, 16, 30, 138))
    plate = plate.filter(ImageFilter.GaussianBlur(0.6))
    plate.alpha_composite(timg, (padx, pady))

    # crop to content
    bbox = plate.getbbox()
    plate = plate.crop(bbox)
    x = (W - plate.width) // 2
    y = H - 300 - plate.height   # keep the bottom clear for player controls
    path = CAP_DIR / f"cap_{idx:03d}.png"
    plate.save(path)
    return {"path": str(path), "x": int(x), "y": int(y),
            "start": cap["start"], "end": cap["end"]}


# --------------------------------------------------------------------------- #
# shot rendering
# --------------------------------------------------------------------------- #
MOVES = {
    # name: (z0, z1, fx0, fx1, fy0, fy1)
    "push_in":     (1.00, 1.13, 0.50, 0.50, 0.50, 0.50),
    "pull_out":    (1.14, 1.00, 0.50, 0.50, 0.50, 0.50),
    "close_push":  (1.18, 1.34, 0.50, 0.50, 0.50, 0.50),
    "pan_right":   (1.14, 1.14, 0.32, 0.68, 0.50, 0.50),
    "pan_left":    (1.14, 1.14, 0.68, 0.32, 0.50, 0.50),
    "tilt_up":     (1.18, 1.18, 0.50, 0.50, 0.72, 0.34),
    "diag":        (1.04, 1.20, 0.36, 0.62, 0.60, 0.42),
    "hold_drift":  (1.06, 1.10, 0.50, 0.50, 0.50, 0.50),
}


def shot_source(sh: dict) -> Path:
    if "card" in sh:
        return CARD_DIR / f"{sh['card']}.png"
    return RAW / f"{sh['img']}.png"


def render_shot(sh: dict) -> Path:
    src = shot_source(sh)
    out = SHOTS_DIR / f"{sh['id']}.mp4"
    if not src.exists():
        print(f"  !! missing image for {sh['id']}: {src.name} — using title card")
        src = CARD_DIR / "title.png"

    n = max(2, int(round(sh["dur"] * FPS)))
    z0, z1, fx0, fx1, fy0, fy1 = MOVES.get(sh.get("move", "push_in"), MOVES["push_in"])
    if "focus" in sh:
        focal = sh["focus"]
        # bias the framing toward the requested focal point
        fx0 = fx1 = float(focal[0])
        fy0 = fy1 = float(focal[1])

    z = f"{z0}+({z1}-{z0})*on/{n}"
    fx = f"{fx0}+({fx1}-{fx0})*on/{n}"
    fy = f"{fy0}+({fy1}-{fy0})*on/{n}"
    x = f"clip(({fx})*iw-iw/zoom/2,0,iw-iw/zoom)"
    y = f"clip(({fy})*ih-ih/zoom/2,0,ih-ih/zoom)"

    vf = (
        f"scale={UPSCALE[0]}:{UPSCALE[1]}:flags=lanczos,"
        f"zoompan=z='{z}':x='{x}':y='{y}':d=1:s={W}x{H}:fps={FPS},"
        "eq=saturation=1.06:contrast=1.02:brightness=0.006,"
        "vignette=PI/7,format=yuv420p"
    )
    cmd = [FF, "-y", "-loop", "1", "-framerate", str(FPS), "-t", f"{sh['dur']:.3f}",
           "-i", str(src), "-filter_complex", vf, "-an",
           "-c:v", "libx264", "-preset", "medium", "-crf", "17",
           "-pix_fmt", "yuv420p", "-r", str(FPS), str(out)]
    run(cmd)
    return out


# --------------------------------------------------------------------------- #
# pipeline steps
# --------------------------------------------------------------------------- #
def step_cards():
    CARD_DIR.mkdir(parents=True, exist_ok=True)
    make_title_card()
    make_end_card()
    print("cards ok")


def step_shots(timeline):
    SHOTS_DIR.mkdir(parents=True, exist_ok=True)
    clips = []
    for sh in timeline["shots"]:
        out = render_shot(sh)
        clips.append(out)
        print(f"  shot {sh['id']} {sh['dur']:5.2f}s  -> {out.name}")
    return clips


def step_concat(clips, timeline):
    lst = BUILD / "concat.txt"
    lst.write_text("\n".join(f"file '{c.resolve()}'" for c in clips))
    out = BUILD / "master_silent.mp4"
    run([FF, "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
         "-c", "copy", str(out)])
    print(f"concat ok -> {out} ({probe_duration(out):.1f}s)")
    return out


def step_captions(timeline, captions, src_video):
    CAP_DIR.mkdir(parents=True, exist_ok=True)
    inputs, filters, overlays = ["-i", str(src_video)], [], []
    for i, c in enumerate(captions):
        inputs += ["-loop", "1", "-framerate", str(FPS), "-t", f"{timeline['total']:.3f}",
                   "-i", c["path"]]
        k = i + 1
        fin = max(0.01, c["start"] + 0.28)
        fout = max(fin + 0.05, c["end"] - 0.22)
        filters.append(
            f"[{k}:v]format=rgba,fade=t=in:st={c['start']:.3f}:d=0.28:alpha=1,"
            f"fade=t=out:st={fout:.3f}:d=0.22:alpha=1[c{k}]"
        )
        overlays.append(f"[v{k-1}][c{k}]overlay=x={c['x']}:y={c['y']}:"
                        f"enable='between(t,{c['start']:.3f},{c['end']:.3f})'[v{k}]")

    total = timeline["total"]
    head = (f"[0:v]fade=t=in:st=0:d=1.1:color=white,"
            f"fade=t=out:st={total-1.6:.3f}:d=1.6:color=white[v0]")
    graph = ";".join([head] + filters + overlays)
    out = BUILD / "master_caps.mp4"
    run([FF, "-y", *inputs, "-filter_complex", graph, "-map", f"[v{len(captions)}]",
         "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
         "-pix_fmt", "yuv420p", "-r", str(FPS), str(out)])
    print(f"captions ok -> {out}")
    return out


def step_audio(timeline):
    total = timeline["total"]
    n = int(total * 44100) + 44100
    voice = np.zeros((n, 2), dtype=np.float32)
    for ev in timeline["audio"]:
        if not ev.get("src"):
            continue
        src = Path(ev["src"])
        if not src.exists():
            continue
        tmp = BUILD / f"tmp_{ev['line']}.wav"
        af = f"atempo={ev['tempo']}" if ev.get("tempo") else None
        to_wav(src, tmp, af)
        clip = load_wav(tmp)
        # gentle per-line fade to avoid clicks
        f = int(0.012 * 44100)
        clip[:f] *= np.linspace(0, 1, f)[:, None]
        clip[-f:] *= np.linspace(1, 0, f)[:, None]
        i = int(ev["start"] * 44100)
        j = min(n, i + len(clip))
        voice[i:j] += clip[: j - i]
        tmp.unlink(missing_ok=True)
    save_wav(BUILD / "voice.wav", voice)

    plan = [{"start": 0, "dur": total, "mode": "warm", "key": 0, "seed": 1}]
    if timeline["song"]["dur"] > 0:
        plan.append({"start": timeline["song"]["start"], "dur": timeline["song"]["dur"] + 1.5,
                     "mode": "perc", "key": 0, "seed": 5})
    (BUILD / "music_plan.json").write_text(json.dumps(plan))
    run([sys.executable, str(ROOT / "tools/score.py"), "--plan", str(BUILD / "music_plan.json"),
         "--out", str(BUILD / "music.wav"), "--duration", f"{total:.2f}"])
    print("voice + music stems ok")
    return BUILD / "voice.wav", BUILD / "music.wav"


def step_mix(voice, music, total):
    out = BUILD / "mix.wav"
    graph = (
        "[1:a]volume=0.62[m];"
        "[m][0:a]sidechaincompress=threshold=0.02:ratio=9:attack=25:release=420[duck];"
        "[duck]volume=1.45[m2];"
        "[m2][0:a]amix=inputs=2:normalize=0,"
        "loudnorm=I=-16:TP=-1.5:LRA=11,alimiter=limit=0.95[a]"
    )
    run([FF, "-y", "-i", str(voice), "-i", str(music), "-filter_complex", graph,
         "-map", "[a]", "-ar", "48000", "-ac", "2", str(out)])
    print(f"mix ok -> {out}")
    return out


def step_mux(video, audio):
    OUT.mkdir(parents=True, exist_ok=True)
    final = OUT / "ghaith_alhurras_1080p.mp4"
    run([FF, "-y", "-i", str(video), "-i", str(audio),
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
         "-movflags", "+faststart", "-shortest", str(final)])
    # poster
    poster = OUT / "poster.jpg"
    run([FF, "-y", "-ss", "6", "-i", str(final), "-frames:v", "1", "-q:v", "2", str(poster)])
    print(f"final -> {final}  ({probe_duration(final):.1f}s)")
    return final


# --------------------------------------------------------------------------- #
def print_plan(tl):
    print(f"{'shot':5} {'start':>7} {'dur':>6}  scene / lines")
    for s in tl["shots"]:
        print(f"{s['id']:5} {s['start']:7.2f} {s['dur']:6.2f}  {s.get('scene','')}"
              f"  {'·'.join(s.get('lines', []))}")
    print(f"TOTAL {tl['total']:.1f}s  ({tl['total']/60:.2f} min)")
    if tl["missing_lines"]:
        print("MISSING AUDIO LINES:", ", ".join(tl["missing_lines"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["plan", "cards", "shots", "all"])
    ap.add_argument("--from-captions", action="store_true")
    a = ap.parse_args()

    BUILD.mkdir(exist_ok=True)
    tl = build_timeline()
    (BUILD / "timeline.json").write_text(json.dumps(tl, ensure_ascii=False, indent=1))
    print_plan(tl)

    if a.step == "plan":
        return
    if a.step == "cards":
        step_cards()
        return

    if a.step == "shots":
        step_cards()
        step_shots(tl)
        return

    step_cards()
    clips = step_shots(tl)
    silent = step_concat(clips, tl)
    caps = [make_caption(c, i) for i, c in enumerate(tl["captions"])]
    (BUILD / "captions.json").write_text(json.dumps(caps, indent=1))
    video = step_captions(tl, caps, silent)
    voice, music = step_audio(tl)
    mix = step_mix(voice, music, tl["total"])
    step_mux(video, mix)


if __name__ == "__main__":
    main()
