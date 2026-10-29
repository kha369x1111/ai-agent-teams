"""Split multi-line voice takes into per-line WAVs.

Some dialogue lines are generated as one take containing several sentences
(separated by « ... »).  This tool finds the N-1 longest silences and cuts the
take into N parts, writing audio/lines_wav/<line_id>.wav for each.

    python3 tools/voice_groups.py --group G1 --lines 10_nana 11_gigi 12_narrator
    python3 tools/voice_groups.py --auto       # every group in script/lines.json
    python3 tools/voice_groups.py --estimate   # write estimated durations only
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import imageio_ffmpeg  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FF = imageio_ffmpeg.get_ffmpeg_exe()
GROUPS = ROOT / "audio/groups"
OUTW = ROOT / "audio/lines_wav"
SR = 44100


def decode(path: Path) -> np.ndarray:
    tmp = Path("/tmp/_decode.wav")
    subprocess.run([FF, "-y", "-i", str(path), "-ar", str(SR), "-ac", "1",
                    "-c:a", "pcm_s16le", str(tmp)], capture_output=True, check=True)
    with wave.open(str(tmp), "rb") as w:
        a = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32) / 32768
    return a


def write(path: Path, a: np.ndarray):
    pcm = (np.clip(a, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def silence_spans(a: np.ndarray, win: int = 441, thresh_db: float = -34.0):
    """Return list of (start, end) sample indices of silence."""
    n = len(a) // win
    rms = np.sqrt((a[: n * win].reshape(n, win) ** 2).mean(axis=1) + 1e-12)
    db = 20 * np.log10(rms + 1e-12)
    quiet = db < thresh_db
    spans, i = [], 0
    while i < n:
        if quiet[i]:
            j = i
            while j < n and quiet[j]:
                j += 1
            spans.append((i * win, j * win))
            i = j
        else:
            i += 1
    return spans


def split_take(a: np.ndarray, parts: int, weights=None, min_gap=0.14):
    """Cut `a` into `parts` chunks.

    If `weights` (relative text length per part) is given, cut at the silence
    gap closest to each proportional target — this follows sentence pauses far
    more reliably than picking the globally longest gaps.
    """
    spans = [(s, e) for s, e in silence_spans(a) if (e - s) / SR >= min_gap]
    # ignore leading / trailing silence
    spans = [(s, e) for s, e in spans if e < len(a) - 0.15 * SR and s > 0.15 * SR]
    mids = [(s + e) // 2 for s, e in spans]

    cuts = []
    if weights and len(weights) == parts and sum(weights) > 0 and len(mids) >= parts - 1:
        total_w = sum(weights)
        acc = 0.0
        used = set()
        for w in weights[:-1]:
            acc += w
            target = len(a) * acc / total_w
            best, best_d = None, None
            for k, m in enumerate(mids):
                if k in used:
                    continue
                d = abs(m - target)
                if best_d is None or d < best_d:
                    best, best_d, best_k = m, d, k
            if best is not None:
                cuts.append(best)
                used.add(best_k)
        cuts.sort()
    if len(cuts) != parts - 1:
        spans_sorted = sorted(spans, key=lambda se: se[1] - se[0], reverse=True)
        cuts = sorted(((s + e) // 2) for s, e in spans_sorted[: parts - 1])
    bounds = [0] + cuts + [len(a)]
    chunks = [a[bounds[i]: bounds[i + 1]] for i in range(len(bounds) - 1)]
    if len(chunks) != parts or any(len(c) < 0.12 * SR for c in chunks):
        # fallback: proportional split by chunk length is meaningless, split evenly
        step = len(a) // parts
        chunks = [a[i * step:(i + 1) * step] for i in range(parts)]
    out = []
    for c in chunks:
        # trim edges
        env = np.abs(c)
        keep = np.where(env > env.max() * 0.02)[0]
        if len(keep):
            c = c[max(0, keep[0] - int(0.02 * SR)): keep[-1] + int(0.05 * SR)]
        out.append(c)
    return out


def line_texts(line_ids: list[str]) -> list[int]:
    """Relative weights (character counts) for each line id."""
    sys.path.insert(0, str(ROOT / "script"))
    import lines_data
    by_id = lines_data.lines_by_id()
    return [len(by_id[i]["text"]) if i in by_id else 1 for i in line_ids]


def handle(group_id: str, line_ids: list[str], report: bool = True):
    src = GROUPS / f"{group_id}.mp3"
    if not src.exists():
        alt = ROOT / "audio/lines" / f"{line_ids[0]}.mp3"
        if len(line_ids) == 1 and alt.exists():
            src = alt
        else:
            print(f"  ! missing take for {group_id} ({src.name})")
            return False
    a = decode(src)
    chunks = split_take(a, len(line_ids), weights=line_texts(line_ids))
    OUTW.mkdir(parents=True, exist_ok=True)
    for lid, c in zip(line_ids, chunks):
        write(OUTW / f"{lid}.wav", c)
        if report:
            print(f"  {lid:14s} {len(c)/SR:5.2f}s")
    return True


def auto():
    sys.path.insert(0, str(ROOT / "script"))
    import lines_data
    ok = True
    for g in lines_data.GROUPS:
        print(f"group {g['id']}: {' · '.join(g['lines'])}")
        ok &= handle(g["id"], g["lines"])
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--group")
    ap.add_argument("--lines", nargs="*")
    ap.add_argument("--auto", action="store_true")
    a = ap.parse_args()
    if a.auto:
        sys.exit(0 if auto() else 1)
    if not a.group or not a.lines:
        ap.error("need --group and --lines, or --auto")
    sys.exit(0 if handle(a.group, a.lines) else 1)


if __name__ == "__main__":
    main()
