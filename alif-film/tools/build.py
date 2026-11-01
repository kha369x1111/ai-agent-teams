"""خط إنتاج «KALTRON — الألف» بأمر واحد.

    python3 tools/build.py all       # صوت + تركيب + غلاف + وثائق + صفحة عرض
    python3 tools/build.py plan      # جدول التوقيتات فقط
    python3 tools/build.py stills 3,22,55   # إطارات معاينة PNG
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw, ImageFilter  # noqa: E402

import artext  # noqa: E402
import spec  # noqa: E402
import audio  # noqa: E402
import frames  # noqa: E402
import plan as plan_mod  # noqa: E402

WORK = ROOT / "_work"
DELIVER = ROOT / "deliver"
DOCS = ROOT / "docs"


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def make_plan(tempo: float = 0.95, force: bool = False):
    WORK.mkdir(exist_ok=True)
    cache = WORK / "plan.json"
    voices = audio.prepare(spec, ROOT, WORK / "vo", tempo=tempo)
    p = plan_mod.build(spec, voices)
    cache.write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")
    (WORK / "timeline.md").write_text(plan_mod.summary(p), encoding="utf-8")
    return p, voices


def cmd_plan(args) -> None:
    p, voices = make_plan(args.tempo)
    print(plan_mod.summary(p))
    log(f"المدة الكلية {p['total']:.2f} ثانية")


def cmd_audio(args) -> Path:
    p, voices = make_plan(args.tempo)
    log("توليد الموسيقى والمؤثرات…")
    audio.score(p, p["total"], WORK)
    log("المزج والضغط…")
    out = audio.mix(p, voices, ROOT, WORK, WORK / "mix.wav", p["total"])
    log(f"الصوت جاهز: {out}")
    return out


def cmd_render(args) -> None:
    p, voices = make_plan(args.tempo)
    mixp = WORK / "mix.wav"
    if args.remix or not mixp.exists():
        mixp = cmd_audio(args)
    import imageio_ffmpeg

    comp = frames.Compositor(p, ROOT, WORK, spec)
    out = DELIVER / (args.out or "alif_1080x1920.mp4")

    def prog(i, n, el, eta):
        log(f"إطار {i}/{n} · {el:5.1f}s · متبقٍ ~{eta:5.0f}s")

    log("تركيب الإطارات والترميز…")
    frames.encode(comp, mixp, out, imageio_ffmpeg.get_ffmpeg_exe(),
                  start=args.start, end=args.end, progress=prog)
    log(f"الفيديو: {out}")


def cmd_stills(args) -> None:
    p, voices = make_plan(args.tempo)
    comp = frames.Compositor(p, ROOT, WORK, spec)
    WORK.joinpath("stills").mkdir(parents=True, exist_ok=True)
    for tok in args.times.split(","):
        t = float(tok)
        im = comp.frame(t)
        path = WORK / "stills" / f"t{t:06.1f}.png"
        im.save(path)
        log(f"{path}  ({t}s)")
    if args.sheet:
        make_sheet(sorted((WORK / "stills").glob("t*.png")))


def make_sheet(paths, out: Path | None = None) -> Path:
    if not paths:
        raise SystemExit("لا إطارات")
    w, h = 360, 640
    cols = min(4, len(paths))
    rows = (len(paths) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * w, rows * h), (0, 0, 0))
    for i, p in enumerate(paths):
        im = Image.open(p).convert("RGB").resize((w, h), Image.LANCZOS)
        sheet.paste(im, ((i % cols) * w, (i // cols) * h))
    out = out or WORK / "sheet.jpg"
    sheet.save(out, quality=88)
    log(f"لوحة المعاينة: {out}")
    return out


def cmd_cover(args) -> None:
    W, H = 1080, 1920
    bg = Image.open(ROOT / "storyboard/raw/cover.png").convert("RGB")
    s = max(W / bg.width, H / bg.height)
    bg = bg.resize((int(bg.width * s), int(bg.height * s)), Image.LANCZOS)
    bg = bg.crop(((bg.width - W) // 2, (bg.height - H) // 2,
                  (bg.width - W) // 2 + W, (bg.height - H) // 2 + H))
    im = bg.convert("RGBA")

    # تعميق الأسود أعلى وأسفل حتى تُقرأ النصوص فوق الزخرفة
    shade = Image.new("L", (1, H), 0)
    d = ImageDraw.Draw(shade)
    for y in range(H):
        v = 0
        if y < H * 0.42:
            v = int(226 * (1 - y / (H * 0.42)) ** 0.75)
        elif y > H * 0.72:
            v = int(236 * ((y - H * 0.72) / (H * 0.28)) ** 0.9)
        d.point((0, y), fill=v)
    layer = Image.new("RGBA", (W, H), (3, 3, 5, 255))
    layer.putalpha(shade.resize((W, H)))
    im = Image.alpha_composite(im, layer)

    # الألف: ضخم، في قلب الإطار
    glyph, ink = frames.build_glyph(str(ROOT / spec.FONT_AMIRI))
    target_ink = H * 0.50
    ink_h = (ink[3] - ink[1]) * glyph.height
    sc = target_ink / ink_h
    glyph = glyph.resize((int(glyph.width * sc), int(glyph.height * sc)), Image.LANCZOS)
    ink_cy = ((ink[1] + ink[3]) / 2) * glyph.height
    top = int(H * 0.495 - ink_cy)
    im.alpha_composite(glyph, ((W - glyph.width) // 2, top))

    badge = artext.render(spec.SERIES, str(ROOT / spec.FONT_TAJ_BOLD), 28, (236, 212, 172, 240),
                          max_width=W * 0.9)
    im.alpha_composite(badge, ((W - badge.width) // 2, int(H * 0.048)))

    main = artext.gold_image(spec.THUMBNAIL["main"], str(ROOT / spec.FONT_AMIRI), 138,
                             glow=26, pad_ratio=0.30)
    mw = int(W * 0.94)
    if main.width > mw:
        main = main.resize((mw, int(main.height * mw / main.width)), Image.LANCZOS)
    im.alpha_composite(main, ((W - main.width) // 2, int(H * 0.115)))

    sub = artext.render(spec.THUMBNAIL["sub"], str(ROOT / spec.FONT_AMIRI), 52,
                        (244, 230, 206, 245), stroke=3, stroke_color=(0, 0, 0, 200),
                        max_width=W * 0.86)
    im.alpha_composite(sub, ((W - sub.width) // 2, int(H * 0.245)))

    acad = artext.render(spec.ACADEMY, str(ROOT / spec.FONT_AMIRI), 50, (244, 224, 190, 245),
                         stroke=3, stroke_color=(0, 0, 0, 190), max_width=W * 0.9)
    im.alpha_composite(acad, ((W - acad.width) // 2, int(H * 0.878)))
    tag = artext.render("الألف (ا) — قطب الحروف", str(ROOT / spec.FONT_TAJ_BOLD), 34,
                        (214, 190, 154, 225), max_width=W * 0.9)
    im.alpha_composite(tag, ((W - tag.width) // 2, int(H * 0.932)))

    out = im.convert("RGB")
    DELIVER.mkdir(exist_ok=True)
    out.save(DELIVER / "cover.jpg", quality=92)
    out.resize((W // 2, H // 2), Image.LANCZOS).save(DELIVER / "cover_preview.jpg", quality=90)
    log("الغلاف: deliver/cover.jpg")


def cmd_docs(args) -> None:
    p, voices = make_plan(args.tempo)
    DOCS.mkdir(exist_ok=True)
    (DOCS / "timeline.md").write_text(plan_mod.summary(p), encoding="utf-8")

    rows = ["# الموجز الإنتاجي — KALTRON | الألف", "",
            f"**العنوان:** {spec.TITLE}", "", f"**الشعار:** {spec.MOTTO}", "",
            "| العنصر | المواصفات |", "|---|---|"]
    rows += [f"| {k} | {v} |" for k, v in spec.SPEC]
    rows += ["", "## المقاطع", ""]
    for sec in p["sections"]:
        rows += [f"### {sec['index']}. {sec['title']}  ·  {sec['start']:.1f}→{sec['end']:.1f}s",
                 "", f"*{sec['brief']}*", ""]
        for line in sec["lines"]:
            rows.append(f"- «{line}»")
        rows.append("")
        for tx in sec["texts"]:
            rows.append(f"- **على الشاشة:** {tx['text']}"
                        + (f" — {tx['sub']}" if tx.get("sub") else ""))
        rows.append("")
    rows += ["## الترجمة المتزامنة (من الإلقاء الفعلي)", ""]
    for cue in p["subtitles"]:
        rows.append(f"- {cue['start']:6.2f}–{cue['end']:6.2f}  {cue['text']}")
    rows += ["", "## الأمانة المعرفية", ""] + [f"- {x}" for x in spec.HONESTY]
    rows += ["", "## قواعد الإنتاج الثماني — حالة التنفيذ", "",
             "| القاعدة | التنفيذ |", "|---|---|",
             "| 1. شكل الألف صحيح | حرف Amiri الأصلي يُركَّب كمضلّعات HarfBuzz، لا يُولَّد ولا يُشوَّه |",
             "| 2. بلا وجوه مشوّهة | لقطة واحدة لشخص من الخلف، بلا وجه |",
             "| 3. بلا نصوص عشوائية في الصور | كل اللوحات خالية من الحروف (فحص بصري لكل لوحة) |",
             "| 4. النصوص في المونتاج | كل النصوص العربية تُرسم بالكود على الإطارات |",
             "| 5. لا ادّعاء علمي | تنبيهات صريحة داخل المقطع ٥ و٤ و٢ + بطاقة خاتمة |",
             "| 6. بلا مؤثرات كرتونية | درون كوني، إمباكتات، رنين معدني، أوتار داكنة |",
             "| 7. هوية الأكاديمية | شعار هندسي + الاسم في الخاتمة والغلاف |",
             "| 8. تصاعد درامي | صمت → خط نور → ذروة (٦) → استقرار (٧) |", ""]
    (DOCS / "production.md").write_text("\n".join(rows), encoding="utf-8")

    # منشور النشر + بيانات الغلاف
    (DELIVER / "post.md").write_text(
        "# منشور النشر\n\n" + spec.POST + "\n\n---\n\n## بيانات الغلاف\n\n"
        + f"**الرئيسي:** {spec.THUMBNAIL['main']}\n\n**الثانوي:** {spec.THUMBNAIL['sub']}\n\n"
        + f"**الشريط العلوي:** {spec.THUMBNAIL['badge']}\n\n## نص إلزامي للوصف\n\n{spec.DISCLAIMER}\n",
        encoding="utf-8")
    log("الوثائق: docs/production.md · docs/timeline.md · deliver/post.md")


COMMANDS = {"plan": cmd_plan, "audio": cmd_audio, "render": cmd_render,
            "stills": cmd_stills, "cover": cmd_cover, "docs": cmd_docs}


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="خط إنتاج الألف")
    ap.add_argument("cmd", choices=list(COMMANDS) + ["all"])
    ap.add_argument("--tempo", type=float, default=0.95, help="سرعة الإلقاء (<1 أبطأ)")
    ap.add_argument("--times", default="3,15,30,50,70,95,115,140,165,185",
                    help="توقيتات إطارات المعاينة بالثواني")
    ap.add_argument("--sheet", action="store_true")
    ap.add_argument("--remix", action="store_true")
    ap.add_argument("--out", default=None)
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--end", type=float, default=None)
    args = ap.parse_args(argv)
    if args.cmd == "all":
        cmd_audio(args)
        cmd_render(args)
        cmd_cover(args)
        cmd_docs(args)
    else:
        COMMANDS[args.cmd](args)


if __name__ == "__main__":
    main()
