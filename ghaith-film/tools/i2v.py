"""حزمة Image-to-Video: تُحوّل فيلمك إلى «كود فيديو» جاهز لأي أداة تحريك.

الفكرة ببساطة:
  ١) نأخذ صور اللقطات (storyboard/raw) ومقاطعنا المجهّزة.
  ٢) نصدّر لكل لقطة: الصورة + برومبت حركة مكتوب بدقة (ما يتحرك، وما يجب أن يبقى ثابتًا)
     + مدتها + الصوت المرتبط بها.
  ٣) نصدّر أوامر جاهزة للصق في أي أداة (Kling / Luma Dream Machine / Runway Gen-4 /
     Pika / Veo / Hailuo) + ملف CSV + ملف JSON للـ API.
  ٤) حين ترجع المقاطع، ضعها في storyboard/clips/<اسم-الصورة>.mp4 وسيستخدمها الرندر تلقائيًا.

الاستخدام:
    python3 tools/i2v.py --all                      # كل اللقطات
    python3 tools/i2v.py --shots S01 S14 S31        # لقطات محددة
    python3 tools/i2v.py --live                     # اللقطات التي فيها حوار فقط
    python3 tools/i2v.py --report                   # ملخص فقط بدون كتابة ملفات
"""

from __future__ import annotations

import argparse
import csv
import math
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "project"))
sys.path.insert(0, str(ROOT / "script"))
sys.path.insert(0, str(ROOT / "tools"))

import shots_data  # noqa: E402
import lines_data  # noqa: E402

OUT = ROOT / "i2v"
CLIPS = ROOT / "storyboard/clips"

# مقاسات الأداة: أي نسبة يقبلها مزوّد الخدمة
ASPECT = "16:9"
RES = "1920x1080"

# وصف الشخصيات يُعاد في كل برومبت حتى لا تتغيّر الوجوه بين اللقطات
CAST = {
    "s01_livingroom": "father Khaled (short black hair, light beard, beige linen shirt), "
                      "Nana (8, dark braids, navy cardigan), Susu (5, yellow layered dress), "
                      "Gigi (3, messy top-knot, pastel pyjamas, brown teddy bear)",
    "s02_gigi_dad": "Gigi the 3-year-old (messy top-knot, pastel pyjamas, teddy bear) held by "
                    "her father Khaled (beard, beige linen shirt)",
    "s03_nana_worried": "Nana the 8-year-old (dark braids, navy cardigan, white paper crown with stars), "
                        "worried eyes, holding a small blanket",
    "s04_candle_talk": "father Khaled and Nana sitting on the floor beside three lit candles, "
                       "warm candle light on their faces",
    "s05_mission_cheer": "the two sisters Nana and Susu cheering together with raised hands, "
                         "paper crowns with stars",
    "s06_group_hug": "the whole family hugging: father Khaled, Nana, Susu and Gigi squeezed together",
    "s07_phone_rings": "a phone face-up on a wooden coffee table in a warm nursery, screen glowing, "
                       "soft baby toys around it",
    "s08_workshop_table": "children's hands drawing and cutting coloured paper crafts on a round table, "
                          "crayons and glue scattered around",
    "s09_susu_drawing": "Susu the 5-year-old (ponytails with yellow ribbons, yellow dress) drawing a "
                        "smiling blue cloud with a blue crayon",
    "s10_nana_card": "Nana the 8-year-old writing a greeting card on a pink desk, coloured pencils in a cup",
    "s11_gigi_handprint": "Gigi the 3-year-old pressing a painted handprint onto paper, paint on her cheek, "
                          "teddy bear beside her",
    "s12_dad_ready": "father Khaled ready to leave, holding a duffel bag in the doorway, the two older "
                     "girls in paper crowns looking up at him",
    "s13_hero_walk": "three sisters walking away from camera towards a bright doorway, holding hands, "
                     "paper crowns, warm backlight",
    "s14_corridor": "three sisters walking hand in hand down a hospital corridor, paper crowns, soft daylight",
    "s15_mother_arms": "mother Sara in a hospital bed holding all three daughters in a hug, newborn bassinet near",
    "s16_bassinet": "two girls leaning over a clear bassinet where the newborn Ghaith sleeps, swaddled in "
                    "a white blanket with blue stars",
    "s17_baby_closeup": "close-up of the sleeping newborn Ghaith, dark hair, rosy cheeks, white star blanket",
    "s18_gigi_wow": "Gigi the 3-year-old amazed, one finger on her chin, teddy bear in her arms, "
                    "bassinet in the foreground",
    "s19_nana_pinky": "close-up of Nana's small finger touching the newborn's tiny hand, both faces soft",
    "s20_sara_proud": "mother Sara smiling proudly, tired but glowing, beside the bassinet",
    "s21_sisters_around": "the three sisters and both parents around the bassinet singing together, sunset window",
    "s22_song_wide": "wide shot of the whole family singing around the bassinet, golden sunset window",
    "s24_photo_frame": "a framed family photograph on the wall: parents holding the newborn, three girls in "
                       "paper crowns around them",
}

# حركة الكاميرا المقترحة لكل نوع لقطة (تُترجم إلى نص للأداة)
CAM = {
    "push_in": "slow cinematic push-in, camera moves gently forward",
    "close_push": "slow close push towards the face, shallow depth of field",
    "pull_out": "slow pull-back revealing the room",
    "pan_right": "very slow pan to the right",
    "pan_left": "very slow pan to the left",
    "tilt_up": "slow tilt up following the girls",
    "diag": "slow diagonal drift forward-left",
    "hold_drift": "almost static camera with a very slow drift",
}

# أسماء المتحدثين بالإنجليزية + معنى الدور في الحركة
SPEAKER_EN = {
    "الراوي": ("narrator (voice-off, not on screen)", "narration"),
    "خالد": ("Khaled the father", "speak"),
    "سارة": ("Sara the mother", "speak"),
    "نانا": ("Nana the 8-year-old", "speak"),
    "سوسو": ("Susu the 5-year-old", "speak"),
    "جيجي": ("Gigi the 3-year-old", "speak"),
    "البنات": ("the three sisters in chorus", "speak"),
}

STYLE = ("Pixar/Disney style 3D children's animation, warm pastel palette, soft cinematic lighting, "
         "expressive faces, physically believable cloth and hair, 24 fps cinematic motion, "
         "no text, no watermark, no logo")


def load_timeline():
    """يبني الخط الزمني الحقيقي (نفس ما يستخدمه الرندر) بدون كتابة أي ملف."""
    from build import build_timeline  # noqa: WPS433
    return build_timeline()


def lines_map():
    return {l["id"]: l for l in lines_data.LINES}


def shot_rows(tl, ids=None, live_only=False):
    """يجمع صفًا لكل لقطة فيها صورة: صورة، مدة، حركة، حوار، برومبت."""
    lmap = lines_map()
    rows = []
    for s in tl["shots"]:
        if "img" not in s:
            continue                       # بطاقات العنوان/النهاية ليست صورًا
        if ids and s["id"] not in ids:
            continue
        shot_lines = [lmap[i] for i in s.get("lines", []) if i in lmap]
        if live_only and not shot_lines:
            continue
        img = s["img"]
        speaking = [l["speaker"] for l in shot_lines]
        rows.append({
            "shot": s["id"],
            "image": img,
            "image_path": f"storyboard/raw/{img}.jpg",
            "duration_s": round(s["dur"], 2),
            "camera": s.get("move", "push_in"),
            "scene": s.get("scene", ""),
            "song": bool(s.get("song")),
            "lines": [l["id"] for l in shot_lines],
            "speakers": speaking,
            "dialogue": " / ".join(l["text"] for l in shot_lines),
            "prompt": build_prompt(img, s, shot_lines),
        })
    return rows


def build_prompt(img: str, shot: dict, shot_lines: list) -> str:
    """برومبت واحد كامل: ماذا يتحرك + ماذا يبقى ثابتًا + الأسلوب."""
    who = CAST.get(img, "the characters in the reference image")
    cam = CAM.get(shot.get("move", "push_in"), CAM["push_in"])
    parts = [f"Animate this still image into a living shot of {who}."]

    if shot_lines:
        mapped = [SPEAKER_EN.get(l["speaker"], (l["speaker"], "speak")) for l in shot_lines]
        speakers = list(dict.fromkeys(n for n, _ in mapped))
        modes = {m for _, m in mapped}
        if modes == {"narration"}:
            parts.append("Narration plays over the shot: the characters do not mouth words — they listen "
                         "and react with blinking, breathing, small head turns and changing expressions.")
        else:
            parts.append(f"Speaking character: {', '.join(speakers)} — natural lip-sync on the line, "
                         f"small head nods, blinking, eyebrows and smile changing with the emotion; "
                         f"the others listen and react subtly (blink, tilt head, small smile).")
    if shot.get("song"):
        parts.append("Everyone sings together: mouths open and close on the melody, gentle swaying, "
                     "happy eyes, hands moving slightly.")
    if not shot_lines and not shot.get("song"):
        parts.append("Give the scene ambient life: soft breathing, blinking, hair and clothes moving "
                     "a little, dust motes and light shimmer.")

    parts.append("Body language: weight shifts, small gestures with hands, believable secondary motion "
                 "in hair, sleeves and fabric.")
    parts.append(f"Camera: {cam}.")
    parts.append("Keep exactly the same characters, faces, clothing, props, framing and lighting as the "
                 "reference image — do not redesign anything, no new people, no text on screen.")
    parts.append(STYLE + ".")
    return " ".join(parts)


def write_bundle(rows):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "clips").mkdir(exist_ok=True)

    # ١) JSON للـ API (Kling / Runway / Luma …)
    api = []
    for r in rows:
        api.append({
            "shot": r["shot"],
            "image": r["image_path"],
            "prompt": r["prompt"],
            "negative_prompt": ("extra limbs, deformed hands, face morphing, changing clothes, "
                                "warped background, flicker, text, watermark, extra people"),
            "duration": min(10, max(5, int(round(r["duration_s"])))),
            "aspect_ratio": ASPECT,
            "resolution": RES,
            "camera": r["camera"],
            "audio_line_ids": r["lines"],
        })
    (OUT / "requests.json").write_text(json.dumps(api, ensure_ascii=False, indent=2))

    # ٢) CSV لجدول أو Sheet
    with (OUT / "shotlist.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["shot", "image", "duration_s", "camera", "speakers", "dialogue", "prompt"])
        for r in rows:
            w.writerow([r["shot"], r["image"], r["duration_s"], r["camera"],
                        "، ".join(r["speakers"]), r["dialogue"], r["prompt"]])

    # ٣) ملف نصي: الصق سطرًا واحدًا في أي أداة
    with (OUT / "prompts.txt").open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(f"### {r['shot']} · {r['image']} · {r['duration_s']}s · {r['camera']}\n")
            f.write(r["prompt"] + "\n\n")
    return OUT


# --------------------------------------------------------------------------- #
#                        التقسيم إلى مقاطع ٥ ثوانٍ
# --------------------------------------------------------------------------- #
def split_rows(rows, max_seg: float = 5.0):
    """يقسّم كل لقطة إلى مقاطع لا تزيد عن max_seg ثانية (حدّ الأدوات المجانية)."""
    segs = []
    for r in rows:
        n = max(1, math.ceil(round(r["duration_s"], 2) / max_seg))
        dur = r["duration_s"] / n
        for i in range(n):
            segs.append({
                "file": f"{r['shot']}_{i + 1}",
                "shot": r["shot"],
                "segment": i + 1,
                "of": n,
                "image": r["image"],
                "image_path": r["image_path"],
                "t0": round(i * dur, 2),          # بداية المقطع داخل اللقطة
                "dur": round(dur, 2),
                "camera": r["camera"],
                "speakers": r["speakers"],
                "lines": r["lines"],
                "dialogue": r["dialogue"],
                "prompt": segment_prompt(r, i, n, dur),
            })
    return segs


def segment_prompt(row, idx: int, total: int, dur: float) -> str:
    """نفس برومبت اللقطة، لكن مع تحديد الجزء وحركة الكاميرا المناسبة له."""
    prompt = row["prompt"]
    if total > 1:
        phase = ["start of the move", "middle of the move", "end of the move"]
        ph = phase[min(idx, len(phase) - 1)] if total > 2 else (
            "beginning" if idx == 0 else "end")
        note = (f"This is segment {idx + 1} of {total} of the same continuous shot "
                f"({dur:.1f} seconds): keep the same framing progress — camera is at the {ph} "
                f"of the move. Do not cut, do not restart the framing.")
    else:
        note = f"The shot is {dur:.1f} seconds long."
    return f"{note} {prompt}"


def write_segments(segs, max_seg: float):
    d = OUT / "segments"
    d.mkdir(parents=True, exist_ok=True)
    up = OUT / "upload"
    up.mkdir(parents=True, exist_ok=True)

    # صور الرفع: نسخة واحدة لكل لقطة، باسم اللقطة (توفيرًا لرصيد الأدوات المجانية)
    shots = {}
    for s in segs:
        shots.setdefault(s["shot"], s)
    for shot, s in shots.items():
        dst = up / f"{shot}__{s['image']}.jpg"
        src = ROOT / s["image_path"]
        if src.exists() and not dst.exists():
            dst.write_bytes(src.read_bytes())

    # برومبتات: ملف لكل مقطع (سهولة النسخ) + ملف مجمّع
    lines_all = []
    for s in segs:
        (d / f"{s['file']}.txt").write_text(s["prompt"] + "\n", encoding="utf-8")
        lines_all.append(
            f"### {s['file']}  ·  {s['image']}  ·  {s['dur']}s  ·  جزء {s['segment']}/{s['of']}\n"
            f"{s['prompt']}\n")
    (OUT / "segments_prompts.txt").write_text("\n".join(lines_all), encoding="utf-8")

    with (OUT / "segments.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["file", "shot", "segment", "of", "image", "duration_s", "start_in_shot",
                    "camera", "speakers", "prompt"])
        for s in segs:
            w.writerow([s["file"], s["shot"], s["segment"], s["of"], s["image"], s["dur"],
                        s["t0"], s["camera"], "، ".join(s["speakers"]), s["prompt"]])

    (OUT / "segments.json").write_text(
        json.dumps({"max_segment_s": max_seg, "count": len(segs), "segments": segs},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    return d, up


# --------------------------------------------------------------------------- #
#                    صفحة متابعة الرفع (تعمل بدون إنترنت)
# --------------------------------------------------------------------------- #
WIZARD = """<!DOCTYPE html>
<html lang="ar" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>متابعة رفع المقاطع — فريق الحراسة السرّي</title>
<style>
:root{--ink:#2f2430;--muted:#8a7364;--line:#e9d9c8;--ok:#2c8a4e}
*{box-sizing:border-box}
body{margin:0;font-family:system-ui,"Segoe UI",Tahoma,sans-serif;color:var(--ink);
 background:linear-gradient(160deg,#fffaf5,#f6ece3);line-height:1.8}
.wrap{max-width:1000px;margin:0 auto;padding:22px}
h1{font-size:22px;margin:0 0 4px}
.sub{color:var(--muted);font-size:14px;margin-bottom:14px}
.bar{height:10px;background:#efe0d1;border-radius:99px;overflow:hidden;margin:10px 0 4px}
.bar>i{display:block;height:100%;width:0;background:linear-gradient(90deg,#f0a94b,#e07a3f);transition:.3s}
.stat{font-size:13px;color:var(--muted);display:flex;justify-content:space-between}
.card{background:#fff;border:1px solid var(--line);border-radius:18px;padding:16px;margin-top:16px;
 box-shadow:0 16px 40px -34px rgba(120,90,50,.8)}
.row{display:flex;gap:16px;flex-wrap:wrap}
.row>div{flex:1 1 420px;min-width:280px}
img{width:100%;border-radius:12px;display:block;background:#f6ece3}
.tag{display:inline-block;background:#fdf2e8;color:#7c5c3a;border-radius:8px;padding:2px 9px;
 font-size:12.5px;margin:0 0 6px 6px}
pre{background:#2b2230;color:#fbf0e6;border-radius:12px;padding:12px 14px;font-size:12.5px;
 direction:ltr;text-align:left;white-space:pre-wrap;max-height:210px;overflow:auto;margin:0 0 10px}
button{font:inherit;border:0;border-radius:11px;padding:9px 15px;cursor:pointer;background:#f2e2d2;color:#6b4b2e}
button.primary{background:#e07a3f;color:#fff}
button.done{background:#e8f6ec;color:var(--ok)}
.btns{display:flex;gap:8px;flex-wrap:wrap;margin-top:8px}
select{font:inherit;padding:7px 10px;border-radius:10px;border:1px solid var(--line);background:#fff}
.hint{font-size:13px;color:var(--muted);margin-top:12px}
.ok{outline:3px solid #bfe6cb;outline-offset:-3px}
</style></head><body><div class="wrap">
<h1>🎬 متابعة رفع المقاطع إلى أداة مجانية</h1>
<div class="sub">لكل مقطع: صورة ترفعها + برومبت تنسخه. علّم «تم» بعد ما ينزل المقطع،
وسمّ الملف بالاسم المعروض وضعه في مجلد <code>i2v/clips_returned/</code>.</div>
<div class="bar"><i id="fill"></i></div>
<div class="stat"><span id="cnt"></span><span id="pct"></span></div>
<div class="card"><div class="row">
  <div><img id="img" alt=""></div>
  <div>
    <div><span class="tag" id="name"></span><span class="tag" id="meta"></span></div>
    <pre id="prompt"></pre>
    <div class="btns">
      <button class="primary" id="copy">📋 انسخ البرومبت</button>
      <button id="open">🖼️ افتح الصورة</button>
      <button class="done" id="mark">✓ تم</button>
      <button id="prev">→ السابق</button>
      <button id="next">التالي ←</button>
      <button id="reset">↺ تصفير</button>
    </div>
    <div class="hint">الملف المطلوب: <b id="fname"></b> · ضعه في <code>i2v/clips_returned/</code>
      · وبعد الانتهاء: <code>python3 tools/i2v_assemble.py --render</code></div>
    <div class="hint" id="tools"></div>
  </div>
</div></div>
</div>
<script>
const SEGS = __DATA__;
let i = 0, done = {};
try { done = JSON.parse(localStorage.getItem("i2v_done")||"{}"); } catch(e) { done = {}; }
const $ = id => document.getElementById(id);
function save(){ try { localStorage.setItem("i2v_done", JSON.stringify(done)); } catch(e){} }
function render(){
  const s = SEGS[i];
  $("img").src = s.img;
  $("name").textContent = s.file;
  $("meta").textContent = `${s.dur}s · جزء ${s.seg}/${s.of} · ${s.shot}`;
  $("prompt").textContent = s.prompt;
  $("fname").textContent = s.file + ".mp4";
  $("img").className = done[s.file] ? "ok" : "";
  $("mark").textContent = done[s.file] ? "✓ تم (إلغاء)" : "✓ تم";
  const n = Object.keys(done).length;
  $("fill").style.width = (100*n/SEGS.length) + "%";
  $("cnt").textContent = `${n} من ${SEGS.length} مكتمل`;
  $("pct").textContent = Math.round(100*n/SEGS.length) + "%";
}
$("copy").onclick = async () => {
  try { await navigator.clipboard.writeText(SEGS[i].prompt); $("copy").textContent = "✓ نُسخ"; }
  catch(e) { const r=document.createRange(); r.selectNode($("prompt"));
    getSelection().removeAllRanges(); getSelection().addRange(r);
    $("copy").textContent = "حدّد النص وانسخه (Ctrl+C)"; }
  setTimeout(()=>$("copy").textContent="📋 انسخ البرومبت", 1400);
};
$("open").onclick = () => window.open(SEGS[i].img, "_blank");
$("mark").onclick = () => { const k = SEGS[i].file;
  if (done[k]) delete done[k]; else done[k] = 1; save(); render();
  if (done[k] && i < SEGS.length-1) { i++; render(); } };
$("next").onclick = () => { i = Math.min(SEGS.length-1, i+1); render(); };
$("prev").onclick = () => { i = Math.max(0, i-1); render(); };
$("reset").onclick = () => { if (confirm("تصفير كل العلامات؟")) { done = {}; save(); render(); } };
document.addEventListener("keydown", e => {
  if (e.key === "ArrowLeft") $("next").click();
  if (e.key === "ArrowRight") $("prev").click();
  if (e.key === "Enter") $("mark").click();
});
$("tools").textContent = "أدوات مجانية: Kling AI · Luma Dream Machine · Pika · Hailuo — اختر مدة 5 ثوان، نسبة 16:9.";
render();
</script></body></html>
"""


def write_wizard(segs):
    """صفحة HTML واحدة تعمل بالنقر المزدوج: صورة + برومبت + تتبّع الإنجاز."""
    data = [{"file": s["file"], "shot": s["shot"], "seg": s["segment"], "of": s["of"],
             "dur": s["dur"], "img": f"upload/{s['shot']}__{s['image']}.jpg",
             "prompt": s["prompt"]} for s in segs]
    html = WIZARD.replace("__DATA__", json.dumps(data, ensure_ascii=False))
    path = OUT / "متابعة-الرفع.html"
    path.write_text(html, encoding="utf-8")
    return path


def main():
    ap = argparse.ArgumentParser(description="حزمة Image-to-Video للفيلم")
    ap.add_argument("--shots", nargs="*", help="معرّفات لقطات مثل S01 S14")
    ap.add_argument("--images", nargs="*", help="أسماء صور مثل s01_livingroom")
    ap.add_argument("--all", action="store_true", help="كل اللقطات التي لها صورة")
    ap.add_argument("--live", action="store_true", help="اللقطات التي فيها حوار فقط")
    ap.add_argument("--report", action="store_true", help="عرض فقط بدون كتابة")
    ap.add_argument("--split", type=float, default=None, metavar="ثوان",
                    help="تقسيم اللقطات إلى مقاطع لا تزيد عن هذه المدة (مثال: 5)")
    ap.add_argument("--json", action="store_true", help="طباعة JSON على الشاشة")
    a = ap.parse_args()

    tl = load_timeline()
    ids = a.shots or None
    if a.images:
        ids = ids or []
        ids += [s["id"] for s in tl["shots"] if s.get("img") in set(a.images)]
    rows = shot_rows(tl, ids=ids, live_only=a.live or not (a.all or ids))

    if a.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return

    if not a.report:
        out = write_bundle(rows)
        print(f"→ {out.relative_to(ROOT)}/requests.json   ({len(rows)} لقطة)")
        print(f"→ {out.relative_to(ROOT)}/prompts.txt")
        print(f"→ {out.relative_to(ROOT)}/shotlist.csv")
        if a.split:
            segs = split_rows(rows, a.split)
            d, up = write_segments(segs, a.split)
            print(f"→ {d.relative_to(ROOT)}/  ({len(segs)} مقطعًا ≤ {a.split:g} ثوان)")
            print(f"→ {up.relative_to(ROOT)}/  ({len({x['shot'] for x in segs})} صورة للرفع)")
            print(f"→ {out.relative_to(ROOT)}/segments.csv · segments_prompts.txt · segments.json")
            wiz = write_wizard(segs)
            print(f"→ {wiz.relative_to(ROOT)}   (انقر مزدوجًا لمتابعة الرفع)")

    print(f"\n{'لقطة':6} {'صورة':22} {'مدة':>6}  حركة")
    total = 0
    for r in rows:
        total += r["duration_s"]
        print(f"{r['shot']:6} {r['image']:22} {r['duration_s']:6.2f}  {r['camera']}")
    print(f"\n{len(rows)} لقطة · {total/60:.2f} دقيقة")

    missing = [r["image"] for r in rows if not (ROOT / r["image_path"]).exists()]
    if missing:
        print("صور ناقصة:", ", ".join(missing))
    print("\nبعد التحميل من الأداة: ضع كل مقطع باسم storyboard/clips/<اسم-الصورة>.mp4")
    print("ثم: bash make_film.sh --live")


if __name__ == "__main__":
    main()
