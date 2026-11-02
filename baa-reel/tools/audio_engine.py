"""Sovereign Voiceover Mastering, Eastern Orchestral Score & Heritage SFX Engine.

Produces:
  • _work/voice_master.wav   — Deep Bass Baritone narration + stone-hall reverb + clause sync
  • _work/music_score.wav    — Epic Maqam Hijaz orchestral strings + slow deep drums + subtle Oud & Ney
  • _work/sfx_stem.wav       — Frame-accurate Nuqta metallic chime, Baa sub-pulse & parchment foley
  • _work/master_mix.wav     — Sidechain-ducked, -15.5 LUFS mastered 48 kHz stereo Reel soundtrack
  • _work/subtitles.json     — Exact waveform-locked Arabic subtitle cues
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
import wave
from pathlib import Path

import imageio_ffmpeg
import numpy as np
from scipy import signal

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "project"))
import reel_spec as R  # noqa: E402

FF = imageio_ffmpeg.get_ffmpeg_exe()
SR = 44100


def write_wav(path: Path, data: np.ndarray, sr: int = SR):
    d = np.clip(data, -1.0, 1.0)
    pcm = (d * 32767.0).astype("<i2")
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2 if d.ndim == 2 else 1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


def read_wav_mono(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as w:
        n, ch = w.getnframes(), w.getnchannels()
        raw = np.frombuffer(w.readframes(n), dtype="<i2").astype(np.float32) / 32768.0
    if ch > 1:
        raw = raw.reshape(-1, ch).mean(axis=1)
    return raw


def add_stereo(buf: np.ndarray, sig: np.ndarray, at_sec: float, pan: float = 0.0):
    i = int(round(at_sec * SR))
    if i < 0:
        sig = sig[-i:]
        i = 0
    if i >= len(buf) or len(sig) == 0:
        return
    j = min(len(buf), i + len(sig))
    seg = sig[: j - i]
    if seg.ndim == 2:
        buf[i:j] += seg
    else:
        angle = (pan + 1.0) * (math.pi / 4.0)
        buf[i:j, 0] += seg * math.cos(angle)
        buf[i:j, 1] += seg * math.sin(angle)


# --------------------------------------------------------------------------- #
# 1. Sovereign Voiceover Sculpting + Stone Hall Reverb + Clause Sync
# --------------------------------------------------------------------------- #
def _stone_hall_ir(rt60: float = 1.25) -> np.ndarray:
    """ Impulse response of an ancient vaulted stone chamber (early reflections + warm dark tail)."""
    n = int(rt60 * SR)
    t = np.arange(n, dtype=np.float32) / SR
    rng = np.random.default_rng(101)

    ir = np.zeros((n, 2), dtype=np.float32)
    # Distinct early stone wall reflections
    reflections = [
        (0.019, 0.34, -0.35),
        (0.031, 0.28, +0.40),
        (0.047, 0.22, -0.20),
        (0.068, 0.17, +0.25),
        (0.093, 0.13, -0.15),
    ]
    for delay_s, amp, pan in reflections:
        idx = int(delay_s * SR)
        if idx < n:
            ir[idx, 0] += amp * (0.5 - 0.5 * pan)
            ir[idx, 1] += amp * (0.5 + 0.5 * pan)

    # Diffuse exponentially decaying stone tail (damped above 2.4 kHz)
    decay = np.exp(-6.91 * t / rt60) * np.clip((t - 0.025) / 0.035, 0.0, 1.0)
    tail_l = rng.normal(0.0, 1.0, n).astype(np.float32) * decay * 0.022
    tail_r = rng.normal(0.0, 1.0, n).astype(np.float32) * decay * 0.022
    b, a = signal.butter(2, 2350.0 / (SR / 2), btype="low")
    ir[:, 0] += signal.lfilter(b, a, tail_l)
    ir[:, 1] += signal.lfilter(b, a, tail_r)
    return ir


def sculpt_clip_and_align(
    mp3_path: Path,
    target_dur: float,
    clauses: list[dict],
    work_dir: Path,
) -> tuple[np.ndarray, list[dict]]:
    """Trim excess TTS silences, apply Deep Bass Baritone warmth, and align clauses."""
    raw_wav = work_dir / f"_raw_{mp3_path.stem}.wav"
    subprocess.run(
        [FF, "-y", "-i", str(mp3_path), "-ar", str(SR), "-ac", "1", "-c:a", "pcm_s16le", str(raw_wav)],
        capture_output=True, check=True,
    )
    a = read_wav_mono(raw_wav)
    raw_wav.unlink(missing_ok=True)

    # Detect speech islands (15ms RMS window)
    win = int(0.015 * SR)
    rms = np.sqrt(np.convolve(a * a, np.ones(win, dtype=np.float32) / win, mode="same"))
    active = rms > 0.0065

    segs: list[list[int]] = []
    in_s = False
    st = 0
    for idx, val in enumerate(active):
        if val and not in_s:
            st = max(0, idx - int(0.025 * SR))
            in_s = True
        elif not val and in_s:
            segs.append([st, min(len(a), idx + int(0.035 * SR))])
            in_s = False
    if in_s:
        segs.append([st, len(a)])

    merged: list[list[int]] = []
    for s in segs:
        if merged and (s[0] - merged[-1][1]) / SR < 0.13:
            merged[-1][1] = max(merged[-1][1], s[1])
        elif (s[1] - s[0]) / SR > 0.04:
            merged.append(s)

    # Reconstruct sculpted waveform with measured dramatic pauses (max 0.34s internal pause)
    pieces = []
    island_spans = []  # (start_sample, end_sample) in sculpted timeline
    cursor = 0
    fade_n = int(0.012 * SR)
    for idx, (s0, s1) in enumerate(merged):
        chunk = a[s0:s1].copy()
        if len(chunk) > fade_n * 2:
            chunk[:fade_n] *= np.linspace(0, 1, fade_n, dtype=np.float32)
            chunk[-fade_n:] *= np.linspace(1, 0, fade_n, dtype=np.float32)
        pieces.append(chunk)
        island_spans.append((cursor, cursor + len(chunk)))
        cursor += len(chunk)
        if idx < len(merged) - 1:
            orig_gap = (merged[idx + 1][0] - s1) / SR
            pause_s = min(max(orig_gap, 0.14), 0.35)
            p_len = int(pause_s * SR)
            pieces.append(np.zeros(p_len, dtype=np.float32))
            cursor += p_len

    sculpted = np.concatenate(pieces) if pieces else a
    sculpt_dur = len(sculpted) / SR

    # Pitch-deepen by -0.95 semitones (Deep Bass Baritone) + gentle tempo fit into scene window
    pitch_ratio = 2.0 ** (-0.95 / 12.0)  # ~0.9466
    desired_speed = max(0.96, min(1.26, sculpt_dur / target_dur))
    atempo_val = desired_speed / pitch_ratio

    sc_in = work_dir / f"_sc_in_{mp3_path.stem}.wav"
    sc_out = work_dir / f"_sc_out_{mp3_path.stem}.wav"
    write_wav(sc_in, sculpted, SR)

    af_chain = (
        f"asetrate={int(round(SR * pitch_ratio))},"
        f"aresample={SR},"
        f"atempo={atempo_val:.4f},"
        "highpass=f=55,"
        "equalizer=f=108:t=q:w=0.9:g=3.4,"
        "equalizer=f=240:t=q:w=1.2:g=1.4,"
        "equalizer=f=3100:t=q:w=1.1:g=1.8"
    )
    subprocess.run(
        [FF, "-y", "-i", str(sc_in), "-filter:a", af_chain, "-ar", str(SR), "-ac", "1",
         "-c:a", "pcm_s16le", str(sc_out)],
        capture_output=True, check=True,
    )
    voiced = read_wav_mono(sc_out)
    sc_in.unlink(missing_ok=True)
    sc_out.unlink(missing_ok=True)

    # Subtle analog-warmth saturation for natural Raspy Baritone authority
    peak = np.max(np.abs(voiced)) + 1e-6
    voiced = np.tanh((voiced / peak) * 1.24) / np.tanh(1.24) * 0.88
    actual_dur = len(voiced) / SR
    time_scale = actual_dur / max(0.01, sculpt_dur)

    # Align text clauses proportionally to character weights & snapped to speech island boundaries
    weights = [max(3, len(c["text"])) for c in clauses]
    tot_w = sum(weights)
    aligned_clauses = []
    cur_t = 0.0
    for ci, c in enumerate(clauses):
        ideal_end = actual_dur * sum(weights[: ci + 1]) / tot_w
        # Snap ideal_end to nearest island end if close
        snapped_end = ideal_end
        if island_spans and ci < len(clauses) - 1:
            cand_ends = [sp[1] / SR * time_scale for sp in island_spans]
            nearest = min(cand_ends, key=lambda te: abs(te - ideal_end))
            if abs(nearest - ideal_end) < 0.38:
                snapped_end = nearest
        rem_clauses = len(clauses) - 1 - ci
        max_allowed = actual_dur - rem_clauses * 1.15
        if ci == len(clauses) - 1:
            snapped_end = actual_dur
        else:
            snapped_end = max(cur_t + 0.85, min(max_allowed, snapped_end))
        aligned_clauses.append({
            "rel_start": round(cur_t, 3),
            "rel_end": round(snapped_end, 3),
            "text": c["text"],
            "highlight": c["highlight"],
        })
        # Start next clause at next island start if available
        next_start = snapped_end
        if island_spans and ci < len(clauses) - 1:
            after = [sp[0] / SR * time_scale for sp in island_spans if sp[0] / SR * time_scale >= snapped_end - 0.05]
            if after and after[0] - snapped_end < 0.45:
                next_start = after[0]
        cur_t = next_start

    return voiced, aligned_clauses


def build_voice_master(work_dir: Path) -> tuple[Path, list[dict]]:
    total_n = int(R.TOTAL_DURATION * SR) + SR
    dry = np.zeros((total_n, 2), dtype=np.float32)
    subtitles = []

    lines_dir = _ROOT / "audio/lines"
    for sc in R.SCENES:
        mp3 = lines_dir / f"{sc['audio_id']}.mp3"
        voiced, cl_list = sculpt_clip_and_align(mp3, sc["target_vo_dur"], sc["clauses"], work_dir)
        vo_start = sc["start"] + sc["vo_offset"]
        add_stereo(dry, voiced, vo_start, pan=0.0)

        for cl in cl_list:
            subtitles.append({
                "scene_id": sc["id"],
                "start": round(vo_start + cl["rel_start"] - 0.06, 3),
                "end": round(min(sc["end"] - 0.08, vo_start + cl["rel_end"] + 0.14), 3),
                "text": cl["text"],
                "highlight": cl["highlight"],
            })

    # Ensure strictly non-overlapping subtitle windows
    for idx in range(len(subtitles) - 1):
        if subtitles[idx]["end"] > subtitles[idx + 1]["start"] - 0.05:
            subtitles[idx]["end"] = round(subtitles[idx + 1]["start"] - 0.05, 3)

    # Convolve with subtle ancient stone hall impulse response (14% wet)
    ir = _stone_hall_ir(rt60=1.22)
    wet_l = signal.fftconvolve(dry[:, 0], ir[:, 0])[:total_n]
    wet_r = signal.fftconvolve(dry[:, 1], ir[:, 1])[:total_n]
    master_vo = dry[: int(R.TOTAL_DURATION * SR)] * 0.92 + np.stack(
        [wet_l[: int(R.TOTAL_DURATION * SR)], wet_r[: int(R.TOTAL_DURATION * SR)]], axis=1
    ) * 0.24

    out_path = work_dir / "voice_master.wav"
    write_wav(out_path, master_vo, SR)
    return out_path, subtitles


# --------------------------------------------------------------------------- #
# 2. Original Epic Eastern Orchestral Score (Strings + Deep Drums + Oud + Ney)
# --------------------------------------------------------------------------- #
def _bowed_string(freq: float, dur: float, amp: float = 0.15) -> np.ndarray:
    """Rich orchestral cello/viola ensemble voice with warm wooden body resonance."""
    n = int(dur * SR)
    t = np.arange(n, dtype=np.float32) / SR
    sig = np.zeros(n, dtype=np.float32)
    # 3 detuned ensemble players, warm harmonic rolloff
    for det in (0.997, 1.000, 1.0035):
        f = freq * det
        vib = 1.0 + 0.0028 * np.sin(2 * math.pi * 4.4 * t) * np.clip((t - 0.4) / 0.8, 0, 1)
        phase = 2 * math.pi * np.cumsum(f * vib) / SR
        for h in range(1, 8):
            sig += (1.0 / (h ** 1.45)) * np.sin(h * phase)
    # Warm low-pass cello body filter
    b, a = signal.butter(2, min(0.45, (freq * 5.2) / (SR / 2)), btype="low")
    sig = signal.lfilter(b, a, sig)
    env = np.clip(t / min(1.3, dur * 0.32), 0, 1) * np.clip((dur - t) / min(1.5, dur * 0.35), 0, 1)
    return (sig / (np.max(np.abs(sig)) + 1e-6)) * env * amp


def _oud_pluck(freq: float, dur: float = 2.4, amp: float = 0.09) -> np.ndarray:
    """Karplus-Strong / modal plucked Arabic Oud note (warm gut-string decay)."""
    n = int(dur * SR)
    period = max(8, int(round(SR / freq)))
    rng = np.random.default_rng(int(freq * 100) % 9973)
    burst = rng.uniform(-1.0, 1.0, period).astype(np.float32)
    # Smooth initial plectrum strike so it feels warm and wooden, not harsh
    burst = np.convolve(burst, np.array([0.2, 0.6, 0.2], dtype=np.float32), mode="same")
    out = np.zeros(n, dtype=np.float32)
    out[:period] = burst
    damping = 0.9935
    for i in range(period, n):
        out[i] = damping * 0.5 * (out[i - period] + out[i - period + 1])
    # Oud wooden bowl body resonance around 210 Hz
    b, a = signal.iirpeak(215.0 / (SR / 2), Q=2.2)
    out = out * 0.75 + signal.lfilter(b, a, out) * 0.25
    return (out / (np.max(np.abs(out)) + 1e-6)) * amp


def _ney_breath(freq: float, dur: float = 3.6, amp: float = 0.055) -> np.ndarray:
    """Soulful breathy Arabic Ney flute note floating very softly in deep background."""
    n = int(dur * SR)
    t = np.arange(n, dtype=np.float32) / SR
    rng = np.random.default_rng(int(freq * 37) % 9973)
    vib = 1.0 + 0.005 * np.sin(2 * math.pi * 4.9 * t) * np.clip((t - 0.5) / 0.8, 0, 1)
    ph = 2 * math.pi * np.cumsum(freq * vib) / SR
    tone = 0.68 * np.sin(ph) + 0.24 * np.sin(2 * ph) + 0.12 * np.sin(3 * ph)
    # Breathy reed air bandpassed near 2*freq
    air = rng.normal(0.0, 1.0, n).astype(np.float32)
    b, a = signal.butter(2, [max(0.02, (freq * 1.5) / (SR / 2)), min(0.45, (freq * 2.8) / (SR / 2))], btype="band")
    air = signal.lfilter(b, a, air) * 0.28
    env = np.clip(t / 0.75, 0, 1) * np.clip((dur - t) / 0.95, 0, 1)
    sig = (tone + air) * env
    return (sig / (np.max(np.abs(sig)) + 1e-6)) * amp


def _deep_ceremonial_drum(amp: float = 0.34, sub: bool = True) -> np.ndarray:
    """Slow deep Eastern frame-drum / orchestral Daf-Taiko Duum."""
    dur = 1.35 if sub else 0.65
    n = int(dur * SR)
    t = np.arange(n, dtype=np.float32) / SR
    f0 = (82.0 * np.exp(-t * 14.0) + 46.0) if sub else (138.0 * np.exp(-t * 18.0) + 84.0)
    ph = 2 * math.pi * np.cumsum(f0) / SR
    body = np.sin(ph) * np.exp(-t / (0.34 if sub else 0.16))
    # Soft sheepskin palm transient (low-passed so never clicky)
    rng = np.random.default_rng(77)
    skin = rng.normal(0, 1, n).astype(np.float32) * np.exp(-t / 0.022)
    b, a = signal.butter(2, 420.0 / (SR / 2), btype="low")
    skin = signal.lfilter(b, a, skin) * 0.28
    sig = (body + skin) * np.clip(t / 0.005, 0, 1)
    return sig * amp


def compose_eastern_orchestral_score(work_dir: Path, total_dur: float) -> Path:
    """Compose 74s original epic Eastern orchestral score in Maqam Hijaz on D."""
    n = int(total_dur * SR) + SR * 2
    buf = np.zeros((n, 2), dtype=np.float32)

    # Frequencies in D Hijaz / D Nahawand:
    # D2=73.42, A2=110.0, D3=146.83, Eb3=155.56, F3=174.61, F#3=185.00, G3=196.00, A3=220.00, Bb3=233.08, C4=261.63, D4=293.66
    D2, G2, A2, Bb2, C3 = 73.42, 98.00, 110.00, 116.54, 130.81
    D3, Eb3, F3, Fs3, G3, A3, Bb3, C4, D4 = 146.83, 155.56, 174.61, 185.00, 196.00, 220.00, 233.08, 261.63, 293.66

    # Harmonic architecture across the 7 scenes (each bar ~ 5.0s at slow 48 BPM)
    bars = [
        # Scene 1 (0–7s): Primordial drone D2 + A2 -> Hijaz F#3 tension
        (0.3,  6.8,  [D2, A2, D3],         (A3, Eb3, Fs3, D3), None),
        # Scene 2 (7–17s): Ancient Manuscript — D Hijaz regal opening
        (7.0,  5.2,  [D2, A2, D3, Fs3],    (D3, Fs3, G3, A3),  A3),
        (12.0, 5.2,  [G2, D3, G3, Bb3],    (Bb3, A3, G3, Fs3), G3),
        # Scene 3 (17–28s): Secret of the Nuqta — mystical depth
        (17.0, 5.6,  [D2, A2, Eb3, A3],    (A3, Bb3, A3, Fs3), D4),
        (22.5, 5.7,  [Bb2, F3, Bb3, D4],   (D4, C4, Bb3, A3),  A3),
        # Scene 4 (28–39s): Alchemical Balance — grounded bronze cadence
        (28.0, 5.6,  [D2, A2, D3, A3],     (Fs3, G3, A3, Bb3), None),
        (33.5, 5.7,  [C3, G3, C4],         (A3, G3, F3, D3),   G3),
        # Scene 5 (39–51s): Cosmic Dimension — expansive Nahawand/Hijaz wonder
        (39.0, 6.2,  [D2, A2, F3, A3, D4], (D4, A3, F3, G3),   D4),
        (45.0, 6.2,  [A2, Eb3, G3, A3],    (Bb3, A3, G3, Fs3), A3),
        # Scene 6 (51–65s): Sovereign Proclamation — grandest epic orchestral swell
        (51.0, 7.0,  [D2, A2, D3, Fs3, A3, D4], (D3, A3, Bb3, A3), D4),
        (58.0, 7.2,  [G2, D3, G3, Bb3, D4],     (D4, C4, Bb3, A3), A3),
        # Scene 7 (65–74s): Closing Codex & Seven Secrets Resolution
        (65.0, 8.8,  [D2, A2, D3, Fs3, A3],     (A3, G3, Fs3, D3), D3),
    ]

    for b_start, b_dur, chord, oud_notes, ney_note in bars:
        # 1. Orchestral string section
        for idx, f in enumerate(chord):
            pan = -0.45 + 0.90 * (idx / max(1, len(chord) - 1))
            amp = 0.14 if f < 100 else 0.095
            add_stereo(buf, _bowed_string(f, b_dur + 0.9, amp=amp), b_start, pan=pan)

        # 2. Slow ceremonial deep drums (Duum at bar start, soft secondary beat mid-bar)
        if b_start >= 2.2:
            add_stereo(buf, _deep_ceremonial_drum(amp=0.30, sub=True), b_start, pan=0.0)
            if b_dur >= 5.2 and b_start < 67.0:
                add_stereo(buf, _deep_ceremonial_drum(amp=0.17, sub=False), b_start + b_dur * 0.52, pan=0.08)
                add_stereo(buf, _deep_ceremonial_drum(amp=0.21, sub=True), b_start + b_dur * 0.76, pan=-0.06)

        # 3. Very subtle contemplative Oud phrases in background (-22 dB)
        step_t = b_dur / (len(oud_notes) + 0.5)
        for oi, ofreq in enumerate(oud_notes):
            add_stereo(
                buf,
                _oud_pluck(ofreq, dur=2.3, amp=0.052),
                b_start + 0.65 + oi * step_t,
                pan=-0.28,
            )

        # 4. Very subtle breathy Ney in background (-25 dB)
        if ney_note is not None:
            add_stereo(
                buf,
                _ney_breath(ney_note * 2.0, dur=min(4.2, b_dur * 0.72), amp=0.036),
                b_start + b_dur * 0.24,
                pan=+0.30,
            )

    score = buf[: int(total_dur * SR)]
    # Spacious concert-hall stereo tail on orchestral score
    ir = _stone_hall_ir(rt60=1.85)
    wl = signal.fftconvolve(score[:, 0], ir[:, 0])[: len(score)]
    wr = signal.fftconvolve(score[:, 1], ir[:, 1])[: len(score)]
    score = score * 0.78 + np.stack([wl, wr], axis=1) * 0.34

    # Smooth fade-in and majestic final decay
    fi = int(0.8 * SR)
    fo = int(2.6 * SR)
    score[:fi] *= np.linspace(0, 1, fi, dtype=np.float32)[:, None]
    score[-fo:] *= np.linspace(1, 0, fo, dtype=np.float32)[:, None]
    score = score / (np.max(np.abs(score)) + 1e-6) * 0.72

    out_path = work_dir / "music_score.wav"
    write_wav(out_path, score, SR)
    return out_path


# --------------------------------------------------------------------------- #
# 3. Bespoke Synchronized Heritage & Cosmic SFX Stem
# --------------------------------------------------------------------------- #
def _sfx_nuqta_chime() -> np.ndarray:
    """Delicate antique bronze singing-bowl / metallic shimmer on Nuqta manifestation."""
    dur = 2.6
    n = int(dur * SR)
    t = np.arange(n, dtype=np.float32) / SR
    sig = (
        0.55 * np.sin(2 * math.pi * 587.33 * t) * np.exp(-t / 1.35)
        + 0.32 * np.sin(2 * math.pi * 1174.66 * t * 1.002) * np.exp(-t / 0.95)
        + 0.18 * np.sin(2 * math.pi * 1768.0 * t) * np.exp(-t / 0.65)
        + 0.10 * np.sin(2 * math.pi * 2637.0 * t) * np.exp(-t / 0.40)
    )
    sig *= np.clip(t / 0.008, 0, 1)
    return sig * 0.22


def _sfx_baa_pulse() -> np.ndarray:
    """Deep sovereign heartbeat pulse when حرف الباء appears."""
    dur = 1.65
    n = int(dur * SR)
    t = np.arange(n, dtype=np.float32) / SR
    freq = 92.0 * np.exp(-t * 9.5) + 41.0
    ph = 2 * math.pi * np.cumsum(freq) / SR
    sub = (np.sin(ph) + 0.32 * np.sin(2 * ph)) * np.exp(-t / 0.48)
    sub *= np.clip(t / 0.012, 0, 1)
    return sub * 0.38


def _sfx_parchment(close: bool = False) -> np.ndarray:
    """Organic vellum parchment unfurling / ancient codex closing foley."""
    dur = 1.45
    n = int(dur * SR)
    t = np.arange(n, dtype=np.float32) / SR
    rng = np.random.default_rng(303 if not close else 404)
    noise = rng.normal(0, 1, n).astype(np.float32)
    b, a = signal.butter(2, [450.0 / (SR / 2), 3400.0 / (SR / 2)], btype="band")
    rustle = signal.lfilter(b, a, noise)
    env = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 1.6 * np.exp(-t / 0.95)
    sig = rustle * env * 0.16
    if close:
        # Soft deep leather book-cover thud at closing moment
        thud_f = 95.0 * np.exp(-np.maximum(0, t - 0.35) * 18.0) + 48.0
        thud = np.sin(2 * math.pi * np.cumsum(thud_f) / SR) * np.exp(-np.maximum(0, t - 0.35) / 0.14)
        thud *= (t >= 0.35).astype(np.float32)
        sig += thud * 0.24
    return sig


def _sfx_sand_shimmer() -> np.ndarray:
    """Delicate golden alchemical dust shimmer."""
    dur = 3.2
    n = int(dur * SR)
    t = np.arange(n, dtype=np.float32) / SR
    rng = np.random.default_rng(505)
    n_noise = rng.normal(0, 1, n).astype(np.float32)
    b, a = signal.butter(2, [1600.0 / (SR / 2), 5200.0 / (SR / 2)], btype="band")
    grains = signal.lfilter(b, a, n_noise) * np.sin(np.pi * t / dur) ** 1.4
    harm = 0.08 * np.sin(2 * math.pi * 880.0 * t) * np.sin(np.pi * t / dur)
    return (grains * 0.10 + harm)


def _sfx_cosmic_swell() -> np.ndarray:
    """Warm celestial harmonic wave convergence swell."""
    dur = 3.4
    n = int(dur * SR)
    t = np.arange(n, dtype=np.float32) / SR
    env = np.sin(np.pi * t / dur) ** 1.5
    sig = (
        0.45 * np.sin(2 * math.pi * 146.83 * t)
        + 0.32 * np.sin(2 * math.pi * 220.00 * t * 1.002)
        + 0.22 * np.sin(2 * math.pi * 293.66 * t * 0.998)
    ) * env
    return sig * 0.18


def build_sfx_stem(work_dir: Path, total_dur: float) -> Path:
    n = int(total_dur * SR) + SR
    buf = np.zeros((n, 2), dtype=np.float32)
    bank = {
        "nuqta_chime":     _sfx_nuqta_chime(),
        "baa_sub_pulse":   _sfx_baa_pulse(),
        "parchment_open":  _sfx_parchment(close=False),
        "parchment_close": _sfx_parchment(close=True),
        "sand_shimmer":    _sfx_sand_shimmer(),
        "cosmic_swell":    _sfx_cosmic_swell(),
    }
    for cue in R.SFX_CUES:
        clip = bank[cue["type"]] * cue["gain"]
        pan = 0.12 if cue["type"] == "nuqta_chime" else (-0.10 if "parchment" in cue["type"] else 0.0)
        add_stereo(buf, clip, cue["time"], pan=pan)

    out_path = work_dir / "sfx_stem.wav"
    write_wav(out_path, buf[: int(total_dur * SR)], SR)
    return out_path


# --------------------------------------------------------------------------- #
# 4. Broadcast Sidechain Mix (-15.5 LUFS, Narrator Sovereign Clarity)
# --------------------------------------------------------------------------- #
def mix_master(voice_wav: Path, music_wav: Path, sfx_wav: Path, work_dir: Path) -> Path:
    out_wav = work_dir / "master_mix.wav"
    graph = (
        "[1:a]volume=0.52[m];"
        "[2:a]volume=0.82[fx];"
        "[m][fx]amix=inputs=2:normalize=0[bg];"
        "[bg][0:a]sidechaincompress=threshold=0.018:ratio=7.5:attack=22:release=480[duck];"
        "[duck]volume=1.22[bg2];"
        "[0:a]volume=1.18[vo];"
        "[bg2][vo]amix=inputs=2:normalize=0,"
        "loudnorm=I=-15.5:TP=-1.2:LRA=9.5,"
        "alimiter=limit=0.95[a]"
    )
    subprocess.run(
        [FF, "-y", "-i", str(voice_wav), "-i", str(music_wav), "-i", str(sfx_wav),
         "-filter_complex", graph, "-map", "[a]", "-ar", "48000", "-ac", "2",
         "-c:a", "pcm_s16le", str(out_wav)],
        capture_output=True, check=True,
    )
    return out_wav


def build_all_audio(work_dir: Path | None = None) -> dict:
    wdir = work_dir or (_ROOT / "_work")
    wdir.mkdir(parents=True, exist_ok=True)
    print("  [1/4] معالجة التعليق الصوتي (Deep Bass + صدى القاعات الحجرية + مزامنة الترجمة)...", flush=True)
    vo_wav, subtitles = build_voice_master(wdir)
    (wdir / "subtitles.json").write_text(json.dumps(subtitles, ensure_ascii=False, indent=2))

    print("  [2/4] تأليف الموسيقى الأوركسترالية الشرقية (مقام حجاز · طبول عميقة · عود · ناي)...", flush=True)
    music_wav = compose_eastern_orchestral_score(wdir, R.TOTAL_DURATION)

    print("  [3/4] توليد المؤثرات الصوتية التراثية والكونية المتزامنة...", flush=True)
    sfx_wav = build_sfx_stem(wdir, R.TOTAL_DURATION)

    print("  [4/4] المزج السينمائي النهائي (-15.5 LUFS + خفض تلقائي للموسيقى تحت الراوي)...", flush=True)
    mix_wav = mix_master(vo_wav, music_wav, sfx_wav, wdir)
    print(f"  ✓ اكتمل الصوت النهائي: {mix_wav} ({len(subtitles)} جملة ترجمة متزامنة)", flush=True)
    return {"mix": mix_wav, "subtitles": subtitles}


if __name__ == "__main__":
    build_all_audio()
