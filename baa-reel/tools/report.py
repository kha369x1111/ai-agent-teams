"""Generate Production Documentation & Interactive Web Timeline Data (`docs/timeline.js`)."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "project"))
import reel_spec as R  # noqa: E402


def main():
    docs = _ROOT / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    work = _ROOT / "_work"

    # Copy web fonts into docs/ for self-contained browser typography
    for fn in ("Amiri-Bold.ttf", "Amiri-Regular.ttf", "Tajawal-Bold.ttf", "Tajawal-Medium.ttf", "Tajawal-Regular.ttf"):
        src = _ROOT / "assets/fonts" / fn
        if src.exists():
            shutil.copy2(src, docs / fn)

    subs = []
    if (work / "subtitles.json").exists():
        subs = json.loads((work / "subtitles.json").read_text())

    # 1. Interactive timeline.js
    payload = {
        "title": "حرف الباء (ب) — ثوب الوجود وسر النقطة التكوينية",
        "academy": "أكاديمية مفتاح الأسرار السبعة",
        "series": "سلسلة الحروف الكوانتية",
        "duration": R.TOTAL_DURATION,
        "resolution": f"{R.W}×{R.H}",
        "fps": R.FPS,
        "scenes": [
            {
                "id": sc["id"],
                "num": sc["num"],
                "name": sc["name"],
                "start": sc["start"],
                "end": sc["end"],
                "on_screen_title": " — ".join(sc["on_screen_title"]),
                "narration": sc["narration"],
            }
            for sc in R.SCENES
        ],
        "subtitles": subs,
        "sfx": R.SFX_CUES,
        "publish": R.PUBLISH_METADATA,
    }
    (docs / "timeline.js").write_text(
        "window.BAA_REEL = " + json.dumps(payload, ensure_ascii=False, indent=2) + ";\n"
    )

    # 2. docs/visual-bible.md
    visual_bible = """# الدستور البصري والعلمي — حرف الباء (ب): ثوب الوجود وسر النقطة التكوينية

**المشروع:** أكاديمية مفتاح الأسرار السبعة — سلسلة الحروف الكوانتية  
**الصيغة النهائية:** Reels سينمائي عمودي `9:16` · الدقة `1080×1920` · `30 FPS` · المدة `73.8 ثانية`

---

## ١. الهويات البصرية الثلاث الحاكمة

1. **الهوية الأولى — المخطوطات السيادية:**
   - رقوق جلدية وورقية معتّقة، حبر فحمي عميق (`#0B0A0E`)، تذهيب معدني بارز (`#D4AC5C`)، برونز مطروق (`#8E6236`)، وإضاءة **Chiaroscuro** درامية مع أشعة ضوئية حجمية (Volumetric God-Rays).
2. **الهوية الثانية — سر النقطة التكوينية:**
   - فصل تشريحي متجهي (Vector Anatomy) لحرف **«ب»** عبر محرك `HarfBuzz` إلى عنصرين مستقلين: **صحن الباء** و**النقطة التكوينية** أسفله، بحيث تنبثق النقطة أولاً كمركز طاقة مضيء ثم ينبثق منها صحن الباء تدريجياً، وتبقى العلامة البصرية المتكررة للأكاديمية.
3. **الهوية الثالثة — الهندسة الكونية:**
   - هندسة إسلامية متحركة (المربع ذو الأربعة أركان، المثمّن، شمسة الاثني عشر والستة عشر ضلعاً، والنجمة السباعية لختم الأكاديمية)، وتكاثف `1,350` جزيئاً ذهبياً إلى هيئة الباء، وموجات ضوئية متداخلة مع مجسمات هندسية ثلاثية الأبعاد.

---

## ٢. الضوابط العلمية والتراثية الصارمة

- تُعرَض القيم العددية (`الباء = ٢`) والتأويلات الحرفية والخيميائية بوصفها **منظومات رمزية وتراثية تأملية**، لا بوصفها قوانين أو حقائق فيزيائية تجريبية.
- عدم نسبة أي قول نصّي إلى الشيخ محيي الدين بن عربي أو *الفتوحات المكية* بغير تحقيق موضعه الأصلي؛ النص المصوغ يلتزم بعبارة أمينة منضبطة: *«وفي تأويلات أهل الحروف...»* و*«هذه قراءة رمزية في أسرار الحروف»*.
- عدم المساواة بين التكاثف الموجي/الكمومي والتجسد المادي للحروف؛ استُخدم التجمع الموجي في المشهد الخامس بوصفه **استعارة بصرية تأملية** تفرّق صراحةً بين الرمز ولغة العلم المعاصر.
- منع نماذج توليد الصور من كتابة أي نص عربي داخل اللوحات الخلفية؛ جميع الحروف والعناوين والترجمات مرسومة متجهياً بدقة طباعية خالية من التشويه.
"""
    (docs / "visual-bible.md").write_text(visual_bible)

    # 3. docs/shotlist.md
    rows = []
    for sc in R.SCENES:
        shots_str = " + ".join(f"`{sh['img']}` ({sh['move']})" for sh in sc["shots"])
        rows.append(
            f"| {sc['id']} | {sc['start']:.1f}–{sc['end']:.1f} ث | {sc['name']} | "
            f"{' / '.join(sc['on_screen_title'])} | {shots_str} |\n"
            f"| | **التعليق:** | *{sc['narration']}* | **VFX:** `{sc['vfx_mode']}` | |"
        )
    shotlist_md = (
        "# دفتر المشاهد واللقطات (Shotlist) — ريلز حرف الباء (ب)\n\n"
        "| المشهد | التوقيت | العنوان الدرامي | النص على الشاشة | اللوحات وحركة الكاميرا |\n"
        "|---|---|---|---|---|\n"
        + "\n".join(rows)
        + "\n"
    )
    (docs / "shotlist.md").write_text(shotlist_md)

    # 4. docs/publish-kit.md
    pub = R.PUBLISH_METADATA
    publish_md = f"""# حزمة النشر والاستراتيجية الفيروسية — حرف الباء (ب)

## العنوان
{pub['title']}

## الوصف الجاهز للنشر
{pub['description']}

## الوسوم (Hashtags)
{'  '.join(pub['hashtags'])}

---

## قائمة التحقق الفيروسية المُنفَّذة في المونتاج
- **أول ثانيتين (0.0–2.0s):** ظلام مطلق يعقبه اشتعال خاطف للنقطة الذهبية وموجة صدمة ضوئية مع رنين برونزي عميق يوقف التمرير فوراً.
- **غياب المقدمات التقليدية:** دخول مباشر في قلب السر دون تحية أو تمهيد مدرسي.
- **إيقاع بصري متجدد:** `10` لوحات سينمائية متعاقبة مع تحريك ثلاثي الأبعاد وجزيئات وهندسة متحركة بمعدل `30 إطاراً/ثانية`.
- **ترجمة عربية متزامنة:** `28` بطاقة ترجمة مرتبطة بموجة الصوت مع تذهيب الكلمات المفتاحية المحورية في منطقة الأمان العمودية للريلز.
- **خاتمة تفاعلية:** سؤال ختامي مفتوح يدفع المشاهد للتأمل والتعليق والمشاركة: *«وأنت… ما السر الذي تراه في النقطة؟»*.
"""
    (docs / "publish-kit.md").write_text(publish_md)
    print("  ✓ اكتملت وثائق الإنتاج وملف timeline.js", flush=True)


if __name__ == "__main__":
    main()
