"""الصوت: معالجة التعليق الصوتي، ثم موسيقى سينمائية إجرائية ومؤثرات، ثم مزج.

الفكرة: لا نستخدم مكتبات صوت ثقيلة. كل شيء numpy + ffmpeg، وخطوة واحدة:
    audio.prepare(spec)   -> تقطيع الصمت، EQ، ضغط، طبقة أوكتاف منخفضة، تحليل الكلام
    audio.score(plan, vo) -> درون كوني + أوتار داكنة + إمباكتات + رنين معدني + هواء
    audio.mix(...)        -> ducking حسب غلاف الصوت، reverb، limiter، loudnorm
"""

from __future__ import annotations

import subprocess
import wave
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

SR = 44100
rng = np.random.default_rng(11)

VO_GAIN = 0.92
MUSIC_GAIN = 0.62
SFX_GAIN = 0.72
DUCK_DB = -8.0

CHORDS = {
    "Dm": [38, 57, 62, 65],
    "Bb": [34, 58, 62, 65],
    "Gm": [31, 55, 58, 62],
    "Am": [33, 57, 60, 64],
    "A": [33, 57, 61, 64],
    "F": [29, 57, 60, 65],
    "Dm_low": [26, 38, 57, 62],
}
# مسار الهارموني: من الفراغ إلى الذروة ثم الاستقرار
SECTION_CHORDS = ["Dm_low", "Bb", "Gm", "A", "Dm", "Bb", "Dm"]
SECTION_INTENSITY = [0.55, 0.62, 0.72, 0.80, 0.74, 1.00, 0.86]


# --------------------------------------------------------------------------- #
# أدوات
# --------------------------------------------------------------------------- #
def hz(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12.0)


def _ffmpeg() -> str:
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    p = subprocess.run([str(c) for c in cmd], capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError("ffmpeg failed: " + p.stderr[-2000:])
    return p


def read_wav(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as w:
        n, ch, sr, sw = w.getnframes(), w.getnchannels(), w.getframerate(), w.getsampwidth()
        raw = w.readframes(n)
    if sw != 2:
        raise ValueError("expected 16-bit wav")
    x = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    if ch > 1:
        x = x.reshape(-1, ch)
    return x, sr


def write_wav(path: Path, x: np.ndarray, sr: int = SR) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    y = np.clip(x, -1.0, 1.0)
    data = (y * 32767).astype("<i2").tobytes()
    ch = 1 if y.ndim == 1 else y.shape[1]
    with wave.open(str(path), "wb") as w:
        w.setnchannels(ch)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(data)


def mono(x: np.ndarray) -> np.ndarray:
    return x.mean(axis=1) if x.ndim > 1 else x


def db(x: float) -> float:
    return 20 * np.log10(max(x, 1e-12))


# --------------------------------------------------------------------------- #
# فلاتر بسيطة (FIR) — كافية لصناعة الموسيقى والمؤثرات
# --------------------------------------------------------------------------- #
def _sinc_kernel(cut: float, taps: int = 161) -> np.ndarray:
    """cut: نسبة إلى معدل العينات (0..0.5)."""
    n = np.arange(taps) - (taps - 1) / 2
    k = 2 * cut * np.sinc(2 * cut * n) * np.hanning(taps)
    return k / k.sum()


def lowpass(x: np.ndarray, cut_hz: float, taps: int = 161) -> np.ndarray:
    return np.convolve(x, _sinc_kernel(cut_hz / SR, taps), mode="same")


def highpass(x: np.ndarray, cut_hz: float, taps: int = 161) -> np.ndarray:
    return x - lowpass(x, cut_hz, taps)


def reverb(x: np.ndarray, wet: float = 0.16, decay: float = 1.4, pre: float = 0.03,
           bright: float = 5200.0) -> np.ndarray:
    """ارتداد واسع مُصنَّع: ضجيج متلاشٍ كاستجابة نبضية، ثم التفاف FFT."""
    n_ir = int(decay * SR)
    t = np.arange(n_ir) / SR
    ir = rng.normal(0, 1, n_ir) * np.exp(-t * (4.2 / decay))
    ir = lowpass(ir, bright, 121)
    ir[: int(pre * SR)] = 0
    ir /= np.max(np.abs(ir)) + 1e-9
    n = len(x) + n_ir
    size = 1 << int(np.ceil(np.log2(n)))
    X = np.fft.rfft(x, size)
    H = np.fft.rfft(ir, size)
    y = np.fft.irfft(X * H, size)[: len(x)]
    return x * (1 - wet) + y * wet / (np.max(np.abs(y)) + 1e-9) * np.max(np.abs(x) + 1e-9)


# --------------------------------------------------------------------------- #
# معالجة التعليق الصوتي
# --------------------------------------------------------------------------- #
VO_CHAIN = (
    "highpass=f=68,"
    "equalizer=f=105:t=q:w=1.1:g=4.2,"      # صدر/جسامة
    "equalizer=f=320:t=q:w=1.0:g=-3.0,"     # إزالة الطين
    "equalizer=f=2900:t=q:w=1.3:g=2.2,"     # وضوح الحروف
    "equalizer=f=6800:t=q:w=1.0:g=-1.5,"
    "acompressor=threshold=0.10:ratio=3.2:attack=12:release=190:makeup=1.6,"
    "alimiter=limit=0.94,"
    "atempo={tempo}"
)


@dataclass
class Segment:
    start: float
    end: float


@dataclass
class Voice:
    samples: np.ndarray = field(default_factory=lambda: np.zeros(0, np.float32))
    speech: list[Segment] = field(default_factory=list)
    cues: list[tuple[str, float, float]] = field(default_factory=list)
    trimmed_s: float = 0.0


def _speech_segments(x: np.ndarray, thr_db: float = -34.0, min_gap: float = 0.24,
                     min_len: float = 0.10) -> list[Segment]:
    hop, win = int(0.01 * SR), int(0.02 * SR)
    n = max(1, (len(x) - win) // hop)
    frames = np.lib.stride_tricks.sliding_window_view(x, win)[::hop][:n]
    rms = np.sqrt((frames ** 2).mean(axis=1) + 1e-12)
    loud = 20 * np.log10(rms + 1e-12)
    speech_thr = max(thr_db, float(np.percentile(loud, 92)) - 26.0)
    mask = loud > speech_thr
    segs: list[Segment] = []
    i = 0
    while i < len(mask):
        if mask[i]:
            j = i
            while j + 1 < len(mask) and mask[j + 1]:
                j += 1
            segs.append(Segment(i * 0.01, (j + 1) * 0.01 + win / SR))
            i = j + 1
        else:
            i += 1
    # دمج الفجوات القصيرة
    merged: list[Segment] = []
    for s in segs:
        if merged and s.start - merged[-1].end < min_gap:
            merged[-1].end = s.end
        else:
            merged.append(s)
    return [s for s in merged if s.end - s.start >= min_len]


def _cap_pauses(x: np.ndarray, segs: list[Segment], max_gap: float = 0.42,
                head: float = 0.05, tail: float = 0.08) -> tuple[np.ndarray, list[Segment]]:
    """قصّ الصمت الزائد مع إعادة بناء الجدول الزمني للفواصل."""
    if not segs:
        return x, segs
    out = [np.zeros(int(head * SR), np.float32)]
    t = head
    new: list[Segment] = []
    for i, s in enumerate(segs):
        a, b = int(s.start * SR), int(s.end * SR)
        out.append(x[a:b])
        new.append(Segment(t, t + (b - a) / SR))
        t += (b - a) / SR
        if i + 1 < len(segs):
            gap = min(max_gap, segs[i + 1].start - s.end)
            out.append(np.zeros(int(gap * SR), np.float32))
            t += gap
    out.append(np.zeros(int(tail * SR), np.float32))
    return np.concatenate(out), new


def assign_cues(lines: list[str], segs: list[Segment]) -> list[tuple[float, float]]:
    """يعطي كل سطر نطاقًا زمنيًا خاصًا به، بلا تكرار ولا تراكب.

    1) تُجمَّع المقاطع الصوتية المتقاربة (فجوة ≤ 0.40s) في مجموعات كلامية.
    2) إذا كانت المجموعات أقل من الأسطر: تُوزَّع الأسطر عليها بنسبة مدة كل مجموعة،
       ثم تُقسم مدة كل مجموعة بين أسطرها بنسبة عدد حروف السطر.
    3) إذا كانت أكثر: تُدمج أقصر الفجوات حتى يتساوى العدد.
    """
    n = len(lines)
    if not segs:
        return [(0.0, 0.0)] * n
    groups = [[i, i] for i in range(len(segs))]
    merged = [groups[0]]
    for g in groups[1:]:
        if segs[g[0]].start - segs[merged[-1][1]].end <= 0.40:
            merged[-1] = [merged[-1][0], g[1]]
        else:
            merged.append(g)
    groups = merged
    while len(groups) > n:
        gaps = [segs[groups[i + 1][0]].start - segs[groups[i][1]].end
                for i in range(len(groups) - 1)]
        k = int(np.argmin(gaps))
        groups[k] = [groups[k][0], groups[k + 1][1]]
        del groups[k + 1]

    spans = [(segs[g[0]].start, segs[g[1]].end) for g in groups]
    if len(groups) == n:
        return spans
    # عدد الأسطر أكبر من المجموعات: نوزّعها بحسب المدة، ثم نقسم كل مجموعة
    counts = [1] * len(groups)
    for _ in range(n - len(groups)):
        ratios = [(spans[i][1] - spans[i][0]) / counts[i] for i in range(len(groups))]
        counts[int(np.argmax(ratios))] += 1
    out: list[tuple[float, float]] = []
    li = 0
    for (a, b), k in zip(spans, counts):
        chunk = lines[li:li + k]
        li += k
        weights = np.array([max(4, len(c)) for c in chunk], dtype=np.float64)
        weights /= weights.sum()
        cursor = a
        for w in weights[:-1]:
            out.append((cursor, cursor + (b - a) * w))
            cursor += (b - a) * w
        out.append((cursor, b))
    return out


def prepare(spec, root: Path, work: Path, tempo: float = 0.95) -> dict[str, Voice]:
    """يُنتج لكل مقطع صوتًا مُعالجًا + توقيتات أسطره (للترجمة المتزامنة)."""
    work.mkdir(parents=True, exist_ok=True)
    ff = _ffmpeg()
    out: dict[str, Voice] = {}
    for sec in spec.SECTIONS:
        src = root / sec["vo"]
        dry = work / f"{sec['id']}_dry.wav"
        sub = work / f"{sec['id']}_sub.wav"
        run([ff, "-y", "-i", src, "-af", VO_CHAIN.format(tempo=tempo),
             "-ac", "1", "-ar", str(SR), str(dry)])
        # طبقة الجسامة: أوكتاف أقل بثلاث درجات نصفية (تشبه مضاعفة التراك في الإعلانات)
        run([ff, "-y", "-i", src,
             "-af", ("highpass=f=55,lowpass=f=2400,asetrate=44100*0.8409,aresample=44100,"
                     "atempo=1.1892,volume=0.30"),
             "-ac", "1", "-ar", str(SR), str(sub)])

        x, _ = read_wav(dry)
        x = mono(x)
        s, _ = read_wav(sub)
        s = mono(s)
        n = min(len(x), len(s))
        body = x[:n] * 1.0
        body[: int(0.018 * SR)] += s[: int(0.018 * SR)] * 0.0
        mixv = body + np.concatenate([np.zeros(int(0.018 * SR), np.float32),
                                      s[: n - int(0.018 * SR)]]) * 0.30
        mixv /= np.max(np.abs(mixv)) + 1e-9
        mixv *= 0.9

        segs = _speech_segments(mixv, min_gap=0.18)
        capped, newsegs = _cap_pauses(mixv, segs, max_gap=0.44)
        voice = Voice(samples=capped.astype(np.float32), speech=newsegs)
        for line, (a, b) in zip(sec["lines"], assign_cues(sec["lines"], newsegs)):
            voice.cues.append((line, a, max(b, a + 0.35)))
        voice.trimmed_s = len(capped) / SR
        out[sec["id"]] = voice
    return out


# --------------------------------------------------------------------------- #
# الآلات الإجرائية
# --------------------------------------------------------------------------- #
def _env_ad(n: int, attack: float, decay: float, curve: float = 2.2) -> np.ndarray:
    t = np.arange(n) / SR
    a = np.clip(t / max(attack, 1e-4), 0, 1)
    d = np.exp(-np.clip(t - attack, 0, None) * curve / max(decay, 1e-4))
    return (a * d).astype(np.float32)


def pad(freqs, dur: float, amp: float, attack: float = 2.6, release: float = 3.2,
        bright: float = 2400.0) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n) / SR
    sig = np.zeros(n, np.float32)
    for f in freqs:
        for det, g in ((1.0, 1.0), (1.0035, 0.7), (0.9965, 0.7)):
            vib = 1 + 0.0016 * np.sin(2 * np.pi * (0.13 + rng.random() * 0.1) * t)
            sig += g * np.sin(2 * np.pi * f * det * vib * t).astype(np.float32)
        sig += 0.22 * np.sin(2 * np.pi * f * 2 * t).astype(np.float32)
    sig = lowpass(sig / (len(freqs) * 2.4), bright, 241)
    e = np.minimum(1, t / attack) * np.minimum(1, np.clip((dur - t) / release, 0, 1))
    return (sig * e * amp).astype(np.float32)


def strings(freqs, dur: float, amp: float, attack: float = 1.6, release: float = 2.4) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n) / SR
    sig = np.zeros(n, np.float32)
    for f in freqs:
        for h in range(1, 9):
            if f * h > 5200:
                break
            sig += (1.0 / h ** 1.25) * np.sin(
                2 * np.pi * f * h * (1 + 0.0022 * np.sin(2 * np.pi * 4.6 * t + h)) * t
            ).astype(np.float32)
    sig = lowpass(sig / (len(freqs) * 2.0), 4200, 241)
    e = np.minimum(1, t / attack) * np.minimum(1, np.clip((dur - t) / release, 0, 1))
    return (sig * e * amp).astype(np.float32)


def boom(amp: float = 1.0, dur: float = 2.6) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 74 * np.exp(-t * 2.6) + 29
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 1.35)
    click = rng.normal(0, 1, n) * np.exp(-t * 38) * 0.5
    rumble = lowpass(rng.normal(0, 1, n), 120, 201) * np.exp(-t * 0.9) * 0.7
    sig = (body + click + rumble).astype(np.float32)
    sig /= np.max(np.abs(sig)) + 1e-9
    return (sig * amp).astype(np.float32)


def metallic(base: float = 146.8, amp: float = 0.3, dur: float = 3.4) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n) / SR
    sig = np.zeros(n, np.float32)
    for ratio, g, dec in ((1.0, 1.0, 1.5), (2.76, 0.55, 1.0), (5.40, 0.32, 0.7), (8.93, 0.18, 0.45)):
        sig += g * np.sin(2 * np.pi * base * ratio * t) * np.exp(-t / dec)
    sig += highpass(rng.normal(0, 1, n), 2600, 121) * np.exp(-t * 7) * 0.25
    sig /= np.max(np.abs(sig)) + 1e-9
    return (sig * amp).astype(np.float32)


def taiko(amp: float = 0.55) -> np.ndarray:
    n = int(1.1 * SR)
    t = np.arange(n) / SR
    f = 120 * np.exp(-t * 9) + 52
    sig = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 3.4)
    sig += lowpass(rng.normal(0, 1, n), 900, 121) * np.exp(-t * 16) * 0.6
    sig /= np.max(np.abs(sig)) + 1e-9
    return (sig * amp).astype(np.float32)


def riser(dur: float = 3.2, amp: float = 0.35) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n) / SR
    noise = rng.normal(0, 1, n)
    sig = np.zeros(n, np.float32)
    # مسح ترددي صاعد عبر تضييق/توسيع تمرير
    for i in range(0, n, int(0.05 * SR)):
        j = min(n, i + int(0.05 * SR))
        cut = 260 + 6800 * (i / n) ** 2
        sig[i:j] = lowpass(noise[i:j], cut, 121)
    sweep = np.sin(2 * np.pi * np.cumsum(np.linspace(90, 420, n)) / SR) * 0.4
    e = (t / dur) ** 2.2
    sig = (sig * 0.8 + sweep) * e
    sig /= np.max(np.abs(sig)) + 1e-9
    return (sig * amp).astype(np.float32)


def whoosh(dur: float = 1.1, amp: float = 0.3) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n) / SR
    noise = rng.normal(0, 1, n)
    sig = np.zeros(n, np.float32)
    for i in range(0, n, int(0.03 * SR)):
        j = min(n, i + int(0.03 * SR))
        p = i / n
        cut = 900 + 5200 * np.sin(np.pi * p) ** 2
        sig[i:j] = highpass(lowpass(noise[i:j], cut, 121), 500, 61)
    e = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 1.6
    sig *= e
    sig /= np.max(np.abs(sig)) + 1e-9
    return (sig * amp).astype(np.float32)


def shimmer(dur: float = 4.0, amp: float = 0.16) -> np.ndarray:
    n = int(dur * SR)
    sig = np.zeros(n, np.float32)
    count = max(3, int(dur * 2.5))
    for _ in range(count):
        f = float(rng.choice([880, 1174.7, 1396.9, 1760, 2093, 2637]))
        start = int(rng.uniform(0, max(0.0, dur - 1.6)) * SR)
        n2 = min(n - start, int(2.2 * SR))
        if n2 <= 0:
            continue
        t = np.arange(n2) / SR
        bell = np.sin(2 * np.pi * f * t) * np.exp(-t * 2.4) * 0.6
        bell += np.sin(2 * np.pi * f * 2.01 * t) * np.exp(-t * 4.2) * 0.2
        sig[start:start + n2] += bell.astype(np.float32)
    sig /= np.max(np.abs(sig)) + 1e-9
    return (sig * amp).astype(np.float32)


def heartbeat() -> np.ndarray:
    n = int(1.4 * SR)
    out = np.zeros(n, np.float32)
    for off, g in ((0.0, 1.0), (0.31, 0.62)):
        b = boom(g * 0.9, 1.0)
        i = int(off * SR)
        m = min(len(b), n - i)
        out[i:i + m] += b[:m]
    return out


# --------------------------------------------------------------------------- #
# الموسيقى + المؤثرات على خط الزمن
# --------------------------------------------------------------------------- #
def score(plan: dict, total: float, work: Path) -> tuple[Path, Path]:
    n = int(total * SR) + SR
    music = np.zeros(n, np.float32)
    sfx = np.zeros(n, np.float32)

    def add(bus: np.ndarray, sig: np.ndarray, at: float, gain: float = 1.0) -> None:
        i = int(max(0.0, at) * SR)
        m = min(len(sig), n - i)
        if m > 0:
            bus[i:i + m] += sig[:m] * gain

    secs = plan["sections"]
    for k, sec in enumerate(secs):
        t0, t1 = sec["start"], sec["end"]
        dur = t1 - t0
        chord = CHORDS[SECTION_CHORDS[k % len(SECTION_CHORDS)]]
        inten = SECTION_INTENSITY[k % len(SECTION_INTENSITY)]
        freqs = [hz(m) for m in chord]
        add(music, pad(freqs, dur + 1.2, 0.30 * inten, attack=2.8, release=3.4, bright=2100), t0)
        add(music, strings(freqs[1:], dur + 0.8, 0.16 * inten, attack=2.2, release=2.6), t0 + 0.4)
        # درون منخفض مستمر
        add(music, pad([hz(chord[0] - 12), hz(chord[0])], dur + 1.0, 0.20 * inten,
                       attack=1.2, release=2.0, bright=420), t0)
        # إمباكت عند بداية كل مقطع
        add(sfx, boom(0.85 * (0.6 + inten * 0.6)), t0)
        add(sfx, metallic(hz(chord[0] + 24), 0.22 * inten), t0 + 0.05)
        # نبضات إيقاعية في المقاطع الأكثر كثافة
        if k >= 3:
            beat = 1.25 if inten < 0.9 else 0.95
            tt = t0 + 1.2
            while tt < t1 - 1.0:
                add(sfx, taiko(0.20 * inten), tt)
                tt += beat
        # رنين معدني متفرق
        for _ in range(2):
            add(sfx, metallic(hz(chord[2] + 12), 0.10 * inten, 3.0),
                t0 + rng.uniform(0.2, max(0.4, dur - 1.0)))
    # السماء/النجوم في مقطع الفلك، واللمعان في الخاتمة
    if len(secs) > 2:
        add(sfx, shimmer(min(8.0, secs[2]["end"] - secs[2]["start"]), 0.20),
            secs[2]["start"] + 0.4)
    if len(secs) > 5:
        add(sfx, shimmer(6.0, 0.22), secs[6]["start"] + 0.3 if len(secs) > 6 else 0)
    # تصعيدان: قبل السر العرفاني وقبل الخاتمة
    for k in (5, 6):
        if len(secs) > k:
            add(sfx, riser(3.6, 0.34), max(0.0, secs[k]["start"] - 3.6))
    # صوت الافتتاح: نبضتان من أعماق الكون
    add(sfx, heartbeat(), 0.25)
    add(sfx, boom(1.0, 3.4), 2.9)
    # هواء خفيف مع تغيّر اللوحات (Light Sweep)
    for sh in plan["shots"][1:]:
        add(sfx, whoosh(1.0, 0.20), sh["start"] - 0.45)
    # تلاشٍ أخير
    add(sfx, boom(0.9, 3.8), max(0.0, total - 3.2))

    # ستيريو بسيط مع اتساع
    def stereo(x: np.ndarray, width: float = 0.0) -> np.ndarray:
        if width <= 0:
            return np.stack([x, x], axis=1)
        d = int(width * SR)
        r = np.concatenate([np.zeros(d, np.float32), x[:-d]]) if d else x
        return np.stack([x * 0.96 + r * 0.12, r * 0.96 + x * 0.12], axis=1)

    m_music = stereo(music, 0.014)
    m_sfx = stereo(sfx, 0.006)
    music_p = work / "music.wav"
    sfx_p = work / "sfx.wav"
    write_wav(music_p, np.clip(m_music, -1, 1), SR)
    write_wav(sfx_p, np.clip(m_sfx, -1, 1), SR)
    return music_p, sfx_p


def mix(plan: dict, voices: dict, root: Path, work: Path, out_wav: Path,
        total: float) -> Path:
    """يجمع التعليق الصوتي + الموسيقى + المؤثرات، يخفض الموسيقى تحت الكلام، ثم loudnorm."""
    n = int(total * SR) + int(0.5 * SR)
    vo = np.zeros(n, np.float32)
    for sec in plan["sections"]:
        v = voices[sec["id"]]
        i = int(sec["vo_start"] * SR)
        m = min(len(v.samples), n - i)
        if m > 0:
            vo[i:i + m] += v.samples[:m]
    vo = reverb(vo, wet=0.15, decay=1.5, pre=0.035, bright=4800)
    vo /= np.max(np.abs(vo)) + 1e-9

    music, _ = read_wav(work / "music.wav")
    sfxv, _ = read_wav(work / "sfx.wav")
    music = mono(music) if music.ndim == 1 else music
    if music.ndim == 2:
        music = music[:, :2]
    if sfxv.ndim == 1:
        sfxv = np.stack([sfxv, sfxv], axis=1)

    def fit(x: np.ndarray) -> np.ndarray:
        if x.shape[0] >= n:
            return x[:n]
        return np.pad(x, ((0, n - x.shape[0]), (0, 0)))

    music = fit(music.astype(np.float32))
    sfxv = fit(sfxv.astype(np.float32))

    # غلاف الصوت لخفض الموسيقى (ducking) بنعومة
    hop = int(0.01 * SR)
    frames = np.lib.stride_tricks.sliding_window_view(vo, hop * 2)[::hop]
    env = np.sqrt((frames ** 2).mean(axis=1) + 1e-12)
    thr = np.percentile(env, 80) * 0.55
    active = (env > thr).astype(np.float32)
    # تنعيم هجومي/انحلالي
    sm = np.zeros_like(active)
    a_att, a_rel = 0.28, 0.045
    acc = 0.0
    for i, v in enumerate(active):
        acc += (v - acc) * (a_att if v > acc else a_rel)
        sm[i] = acc
    gain = 10 ** (DUCK_DB / 20 * np.interp(np.arange(n), np.arange(len(sm)) * hop, sm))
    duck = gain[:, None] if music.ndim == 2 else gain

    vo_st = np.stack([vo, vo], axis=1) * VO_GAIN
    mixv = vo_st + music * duck * MUSIC_GAIN + sfxv * SFX_GAIN
    mixv = np.tanh(mixv * 0.9) * 1.02
    mixv /= np.max(np.abs(mixv)) + 1e-9
    mixv *= 0.94
    raw = work / "mix_raw.wav"
    write_wav(raw, mixv, SR)

    ff = _ffmpeg()
    run([ff, "-y", "-i", raw,
         "-af", "loudnorm=I=-15:TP=-1.5:LRA=11:linear=true,alimiter=limit=0.95",
         "-ar", "48000", "-ac", "2", str(out_wav)])
    return out_wav


def duration_of(path: Path) -> float:
    x, sr = read_wav(path)
    return len(x) / sr
