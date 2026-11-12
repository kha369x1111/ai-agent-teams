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


def main():
    ap = argparse.ArgumentParser(description="حزمة Image-to-Video للفيلم")
    ap.add_argument("--shots", nargs="*", help="معرّفات لقطات مثل S01 S14")
    ap.add_argument("--images", nargs="*", help="أسماء صور مثل s01_livingroom")
    ap.add_argument("--all", action="store_true", help="كل اللقطات التي لها صورة")
    ap.add_argument("--live", action="store_true", help="اللقطات التي فيها حوار فقط")
    ap.add_argument("--report", action="store_true", help="عرض فقط بدون كتابة")
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
