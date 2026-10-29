"""Generate production documents + web player data from the timeline.

    python3 tools/report.py
writes:
    docs/shotlist.md      جدول اللقطات الكامل
    docs/timeline.js      بيانات لصفحة العرض (فصول، حوار، أنشودة)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).parent))
import build as B  # noqa: E402


def mmss(t: float) -> str:
    m, s = divmod(t, 60)
    return f"{int(m):02d}:{s:05.2f}"


def main():
    tl = B.build_timeline()
    lines = B.lines_data.lines_by_id()
    song_shots = {s["id"] for s in tl["shots"] if s.get("song")}

    # audio per shot for the table
    per_shot_lines = {}
    for ev in tl["audio"]:
        for s in tl["shots"]:
            if s["start"] - 0.01 <= ev["start"] < s["start"] + s["dur"]:
                per_shot_lines.setdefault(s["id"], []).append(ev["line"])
                break

    out = ["# دفتر لقطات الفيلم — فريق الحراسة السرّي: مرحباً بك يا غيث", "",
           f"المدة الإجمالية: **{tl['total']/60:.2f} دقيقة** ({tl['total']:.1f} ثانية) · "
           f"{tl['fps']} إطار/ثانية · {tl['width']}×{tl['height']}", "",
           "| # | اللقطة | البداية | المدة | حركة الكاميرا | الصورة | الحوار |",
           "|---|---|---|---|---|---|---|"]

    for s in tl["shots"]:
        spoken = " · ".join(lines[x]["speaker"] for x in per_shot_lines.get(s["id"], []))
        img = s.get("img") or f"بطاقة ({s.get('card')})"
        out.append(f"| {s['id']} | {s.get('scene','')} | {mmss(s['start'])} | {s['dur']:.1f}s | "
                   f"`{s.get('move','')}` | `{img}` | {spoken or '—'} |")

    out += ["", "## الحوار الكامل بترتيب الزمن", "",
            "| التوقيت | المتحدث | النص |", "|---|---|---|"]
    for ev in tl["audio"]:
        l = lines[ev["line"]]
        out.append(f"| {mmss(ev['start'])} | {l['speaker']} | {l['text']} |")

    out += ["", "## ملاحظات المونتاج", "",
            f"- الانتقالات: تلاشٍ ناعم بين اللقطات ({0.55:.2f} ثانية) وزوم بطيء (Ken Burns) داخل كل لقطة.",
            "- الترجمة: نص عربي مشكول داخل لوحة داكنة شفافة أسفل الإطار (نمط أفلام الأطفال).",
            f"- الأنشودة: تبدأ عند {mmss(tl['song']['start'])} ومدتها التقديرية {tl['song']['dur']:.1f} ثانية، "
            f"وتُعرض كلماتها كاريوكي في اللقطات: {', '.join(sorted(song_shots))}.",
            "- الصوت: تعليق صوتي في الوسط، موسيقى خافتة تُخفَّض تلقائيًا (ducking) عند الكلام، "
            "ثم تطبيع الجهارة إلى −16 LUFS.",
            ""]

    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs/shotlist.md").write_text("\n".join(out), encoding="utf-8")

    # ---- web data ---------------------------------------------------------- #
    chapters = []
    for s in tl["shots"]:
        if not chapters or chapters[-1]["scene"] != s.get("scene"):
            chapters.append({"scene": s.get("scene", ""), "start": s["start"]})
    data = {
        "title": "فريق الحراسة السرّي: مرحباً بك يا غيث",
        "duration": tl["total"],
        "chapters": chapters,
        "dialogue": [{"start": ev["start"], "speaker": lines[ev["line"]]["speaker"],
                      "text": lines[ev["line"]]["text"], "kind": lines[ev["line"]]["kind"]}
                     for ev in tl["audio"]],
        "song_start": tl["song"]["start"],
        "lyrics": B.lines_data.SONG_LYRICS,
        "shots": [{"id": s["id"], "start": s["start"], "dur": s["dur"],
                   "img": f"storyboard/raw/{s['img']}.png" if s.get("img") and
                          (ROOT / "storyboard/raw" / f"{s['img']}.png").exists() else None,
                   "scene": s.get("scene", "")} for s in tl["shots"]],
    }
    (ROOT / "docs/timeline.js").write_text(
        "window.GHAITH = " + json.dumps(data, ensure_ascii=False, indent=1) + ";\n",
        encoding="utf-8")
    print(f"docs ok · {len(tl['shots'])} shots · {tl['total']:.1f}s")


if __name__ == "__main__":
    main()
