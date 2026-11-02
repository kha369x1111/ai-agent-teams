"""بناء الجدول الزمني: مقاطع ← لقطات ← نصوص ← ترجمة متزامنة.

كل التوقيتات مشتقة من الطول الفعلي للتعليق الصوتي بعد المعالجة، لا من أرقام
ثابتة، لذلك تتقارب الترجمة مع الإلقاء ولا تنزلق.
"""

from __future__ import annotations

def _lerp(a, b, u):
    return a + (b - a) * u


def build(spec, voices) -> dict:
    W, H, FPS = 1080, 1920, 30
    sections = []
    t = 0.0
    for i, sec in enumerate(spec.SECTIONS):
        vo = voices[sec["id"]]
        pad_in = 3.0 if i == 0 else (1.35 if i in (5, 6) else 1.15)
        pad_out = 2.1 if i < len(spec.SECTIONS) - 1 else 2.6
        dur = pad_in + vo.trimmed_s + pad_out
        start, end = t, t + dur
        vo_start = start + pad_in
        entry = {
            "id": sec["id"], "index": sec["index"], "title": sec["title"],
            "brief": sec["brief"], "start": start, "end": end, "dur": dur,
            "vo_start": vo_start, "vo_end": vo_start + vo.trimmed_s,
            "lines": list(sec["lines"]),
        }
        # لقطات المقطع
        plan_shots = spec.SHOT_PLAN[sec["id"]]
        st = start
        shots = []
        for j, s in enumerate(plan_shots):
            sd = dur * s["share"]
            shots.append({
                "section": sec["id"], "index": j, "start": st, "end": st + sd,
                "plate": s["plate"], "move": s["move"],
                "z0": s.get("z0", 1.0), "z1": s.get("z1", 1.08),
                "focus": s.get("focus", (0.5, 0.5)),
            })
            st += sd
        shots[-1]["end"] = end
        entry["shots"] = shots
        # النصوص على الشاشة (زمن نسبي داخل المقطع)
        texts = []
        for tx in sec.get("onscreen", []):
            at = tx["at"] * dur
            hold = max(1.6, tx["hold"] * dur)
            t0 = start + at
            t1 = min(end - 0.35, t0 + hold)
            texts.append({"text": tx["text"], "sub": tx.get("sub"), "style": tx["style"],
                          "start": t0, "end": t1})
        entry["texts"] = texts
        # الترجمة المتزامنة
        entry["subtitles"] = [{"text": line, "start": vo_start + a, "end": vo_start + b}
                              for line, a, b in vo.cues]
        sections.append(entry)
        t = end

    flat_shots = [s for sec in sections for s in sec["shots"]]
    outro_start = t
    outro_dur = 12.5
    total = t + outro_dur

    return {
        "w": W, "h": H, "fps": FPS, "total": total,
        "title": spec.TITLE, "motto": spec.MOTTO, "academy": spec.ACADEMY,
        "series": spec.SERIES, "outro": {"start": outro_start, "end": total,
                                         "dur": outro_dur},
        "sections": sections, "shots": flat_shots,
        "subtitles": [s for sec in sections for s in sec["subtitles"]],
    }


def summary(plan: dict) -> str:
    rows = ["#  الجدول الزمني", ""]
    rows.append(f"المدة الكلية: {int(plan['total']//60)}:{plan['total']%60:05.2f}  ·  "
                f"{plan['w']}×{plan['h']} · {plan['fps']} FPS")
    rows.append("")
    rows.append("| # | المقطع | البداية | النهاية | المدة | الأسطر | النصوص |")
    rows.append("|---|---|---|---|---|---|---|")
    for k, sec in enumerate(plan["sections"]):
        rows.append(f"| {sec['index']} | {sec['title']} | {sec['start']:6.2f} | "
                    f"{sec['end']:6.2f} | {sec['dur']:5.2f} | {len(sec['lines'])} | "
                    f"{len(sec['texts'])} |")
    rows.append("")
    rows.append("## اللقطات")
    rows.append("")
    rows.append("| اللوحة | البداية | النهاية | الحركة | تكبير |")
    rows.append("|---|---|---|---|---|")
    for s in plan["shots"]:
        rows.append(f"| {s['plate'] or '—'} | {s['start']:6.2f} | {s['end']:6.2f} | "
                    f"{s['move']} | {s['z0']:.2f}→{s['z1']:.2f} |")
    return "\n".join(rows)
