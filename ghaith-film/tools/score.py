"""Procedural score for the Ghaith short film.

Generates a warm, gentle bed (pad + music-box arpeggio + soft bass) with an
optional rhythmic layer for the anthem.  Pure numpy -> 44.1 kHz stereo WAV.

Usage:
    python3 score.py --plan plan.json --out music.wav --duration 285
    plan.json = [{"start": 0, "dur": 40, "mode": "soft", "key": 0}, ...]
"""

from __future__ import annotations

import argparse
import json
import wave

import numpy as np

SR = 44100
rng = np.random.default_rng(7)

# C major / A minor family — warm and safe for children's content
MAJOR = {
    "Fmaj7": [53, 57, 60, 64],
    "Cmaj7": [48, 55, 59, 64],
    "Dm7": [50, 57, 60, 65],
    "G7": [55, 59, 62, 65],
    "Am7": [45, 52, 55, 60],
    "Em7": [52, 55, 59, 62],
}
PROGRESSION = ["Fmaj7", "Cmaj7", "Dm7", "G7", "Am7", "Fmaj7", "Cmaj7", "G7"]


def midi_hz(m):
    return 440.0 * 2 ** ((m - 69) / 12.0)


def env(n, attack, decay, sustain, release, sr=SR):
    a = max(1, int(attack * sr))
    d = max(1, int(decay * sr))
    r = max(1, int(release * sr))
    s = max(1, n - a - d - r)
    return np.concatenate([
        np.linspace(0, 1, a, endpoint=False),
        np.linspace(1, sustain, d, endpoint=False),
        np.full(s, sustain),
        np.linspace(sustain, 0, r),
    ])[:n]


def music_box(freq, dur, amp=0.3):
    n = int(dur * SR)
    t = np.arange(n) / SR
    sig = np.zeros(n)
    for h, g, dcy in ((1, 1.0, 1.4), (2, 0.42, 0.8), (3, 0.18, 0.5), (4.02, 0.08, 0.35)):
        sig += g * np.sin(2 * np.pi * freq * h * t) * np.exp(-t / dcy)
    sig *= np.minimum(1, t / 0.004)  # tiny attack to avoid clicks
    return sig * amp


def pad_note(freq, dur, amp=0.16):
    n = int(dur * SR)
    t = np.arange(n) / SR
    sig = (np.sin(2 * np.pi * freq * t)
           + 0.5 * np.sin(2 * np.pi * freq * 1.003 * t)
           + 0.25 * np.sin(2 * np.pi * (freq * 2) * t))
    e = np.minimum(1, t / 1.4) * np.minimum(1, (dur - t) / 1.2).clip(0, 1)
    return sig * e * amp


def bass_note(freq, dur, amp=0.22):
    n = int(dur * SR)
    t = np.arange(n) / SR
    sig = np.sin(2 * np.pi * freq * t) + 0.25 * np.sin(2 * np.pi * freq * 2 * t)
    e = np.minimum(1, t / 0.02) * np.exp(-t / (dur * 0.7))
    return sig * e * amp


def kick(amp=0.5):
    n = int(0.28 * SR)
    t = np.arange(n) / SR
    f = 110 * np.exp(-t * 22) + 48
    sig = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.09)
    return sig * amp


def shaker(amp=0.10):
    n = int(0.09 * SR)
    t = np.arange(n) / SR
    noise = rng.normal(0, 1, n)
    noise = np.diff(np.concatenate([[0], noise]))  # crude high-pass
    return noise * np.exp(-t / 0.025) * amp


def clap(amp=0.16):
    n = int(0.16 * SR)
    t = np.arange(n) / SR
    noise = rng.normal(0, 1, n) * np.exp(-t / 0.035)
    return noise * amp


def add(buf, sig, at, pan=0.0):
    i = int(at * SR)
    if i < 0:            # notes scheduled slightly before t=0 -> trim the head
        sig = sig[-i:]
        i = 0
    if i >= len(buf) or len(sig) == 0:
        return
    j = min(len(buf), i + len(sig))
    seg = sig[: j - i]
    l = np.sqrt((1 - pan) / 2) if pan > 0 else np.sqrt(1 / 2)
    r = np.sqrt((1 + pan) / 2) if pan > 0 else np.sqrt(1 / 2)
    buf[i:j, 0] += seg * (l * 1.41)
    buf[i:j, 1] += seg * (r * 1.41)


def render_segment(dur, mode="soft", key=0, seed=0):
    n = int(dur * SR) + SR
    buf = np.zeros((n, 2))
    r = np.random.default_rng(seed)

    if mode == "song":
        bpm, arp_gain, pad_gain = 96, 0.30, 0.13
    elif mode == "warm":
        bpm, arp_gain, pad_gain = 72, 0.26, 0.16
    else:
        bpm, arp_gain, pad_gain = 64, 0.24, 0.17

    beat = 60 / bpm
    bar = beat * 4
    t = 0.0
    ci = key
    while t < dur:
        chord = PROGRESSION[ci % len(PROGRESSION)]
        notes = MAJOR[chord]
        # pad + bass for the bar
        for k, m in enumerate(notes):
            add(buf, pad_note(midi_hz(m), bar * 1.05, pad_gain / len(notes) * 2.2),
                t, pan=(-0.35 + 0.7 * k / 3))
        add(buf, bass_note(midi_hz(notes[0] - 12), bar, 0.20), t)

        # music-box arpeggio (eighth notes)
        pattern = [0, 1, 2, 3, 2, 1, 3, 2] if mode != "song" else [0, 2, 1, 3, 0, 2, 3, 1]
        for i, idx in enumerate(pattern):
            if mode == "soft" and i == 6 and r.random() < 0.5:
                continue
            note = notes[idx % len(notes)] + 24
            jitter = r.uniform(-0.012, 0.012)
            add(buf, music_box(midi_hz(note), 1.6, arp_gain * r.uniform(0.7, 1.0)),
                t + i * beat / 2 + jitter, pan=r.uniform(-0.4, 0.4))

        # simple melodic answer every other bar
        if ci % 2 == 1:
            mel = [notes[3] + 12, notes[2] + 12, notes[1] + 12, notes[2] + 12]
            for i, m in enumerate(mel):
                add(buf, music_box(midi_hz(m + 12), 1.4, arp_gain * 0.55),
                    t + 1.5 * beat + i * beat, pan=0.15)

        if mode == "song":
            for b in range(4):
                bt = t + b * beat
                if b in (0, 2):
                    add(buf, kick(0.35), bt)
                if b in (1, 3):
                    add(buf, clap(0.13), bt)
                for h in (0, 1.5, 2, 3.5):
                    add(buf, shaker(0.05), t + h * beat)

        t += bar
        ci += 1

    seg = buf[: int(dur * SR)]
    # gentle echoes for space
    for dly, g in ((0.28, 0.24), (0.53, 0.14)):
        d = int(dly * SR)
        if len(seg) > d:
            seg[d:] += seg[:-d] * g
    return seg


def render_plan(plan, total):
    out = np.zeros((int(total * SR), 2))
    for s in plan:
        seg = render_segment(s["dur"], s.get("mode", "soft"), s.get("key", 0), s.get("seed", 0))
        i = int(s["start"] * SR)
        j = min(len(out), i + len(seg))
        if i < len(out):
            out[i:j] += seg[: j - i]
    # global fades
    fi = int(2.5 * SR)
    out[:fi] *= np.linspace(0, 1, fi)[:, None]
    fo = int(4.0 * SR)
    out[-fo:] *= np.linspace(1, 0, fo)[:, None]
    peak = np.max(np.abs(out)) or 1.0
    return out / peak * 0.85


def write_wav(path, data):
    d = np.clip(data, -1, 1)
    pcm = (d * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--duration", type=float, required=True)
    a = ap.parse_args()
    plan = json.load(open(a.plan))
    write_wav(a.out, render_plan(plan, a.duration))
    print(f"music -> {a.out} ({a.duration:.1f}s)")


if __name__ == "__main__":
    main()
