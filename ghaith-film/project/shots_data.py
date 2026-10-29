"""دفتر لقطات الفيلم — مصدر الحقيقة للتوقيت وحركة الكاميرا.

كل لقطة:
    id      معرّف (S00…S37)
    img     اسم الصورة في storyboard/raw بدون الامتداد (أو card لبطاقة مولّدة)
    move    حركة الكاميرا الافتراضية (انظر tools/render.py::MOVES)
    focus   نقطة التركيز (x, y) كنسبة من الصورة — تُثبّت إطار الكاميرا عليها
    lines   معرّفات الحوار: مدة اللقطة = pad[0] + مجموع مدد الأسطر + pad[1]
    dur     مدة ثابتة للقطات الصامتة
    song    True إذا كانت اللقطة داخل مقطع الأنشودة
    scene   اسم الفصل في صفحة العرض والوثائق

ملاحظة: وحدة Python بدل JSON لأن *.json مستثنى من حفظ مساحة العمل.
"""

FPS = 24
WIDTH = 1920
HEIGHT = 1080

SHOTS = [
    {"id": "S00", "card": "title", "dur": 6.0, "move": "hold_drift", "scene": "العنوان"},
    {"id": "S01", "img": "s01_livingroom", "move": "push_in", "lines": ["00_intro"],
     "pad": [0.8, 1.0], "focus": [0.42, 0.52], "scene": "١ · تجهيز القاعدة"},
    {"id": "S02", "img": "s02_gigi_dad", "move": "push_in", "lines": ["01_gigi"],
     "pad": [0.3, 0.5], "focus": [0.5, 0.55], "scene": "١ · تجهيز القاعدة"},
    {"id": "S03", "img": "s01_livingroom", "move": "diag", "lines": ["02_khaled"],
     "pad": [0.3, 0.6], "focus": [0.38, 0.55], "scene": "١ · تجهيز القاعدة"},
    {"id": "S04", "img": "s03_nana_worried", "move": "push_in", "lines": ["03_narrator"],
     "pad": [0.3, 0.6], "focus": [0.5, 0.45], "scene": "١ · تجهيز القاعدة"},
    {"id": "S05", "img": "s03_nana_worried", "move": "close_push", "lines": ["04_nana"],
     "pad": [0.3, 0.6], "focus": [0.52, 0.4], "scene": "١ · تجهيز القاعدة"},
    {"id": "S06", "img": "s04_candle_talk", "move": "push_in", "lines": ["05_khaled"],
     "pad": [0.3, 0.6], "focus": [0.46, 0.45], "scene": "١ · الشموع"},
    {"id": "S07", "img": "s04_candle_talk", "move": "close_push", "lines": ["06_nana"],
     "pad": [0.3, 0.6], "focus": [0.6, 0.45], "scene": "١ · الشموع"},
    {"id": "S08", "img": "s01_livingroom", "move": "pan_right", "lines": ["07_khaled"],
     "pad": [0.3, 0.7], "focus": [0.5, 0.52], "scene": "١ · فريق الحراسة"},
    {"id": "S09", "img": "s05_mission_cheer", "move": "push_in", "lines": ["08_susu"],
     "pad": [0.3, 0.5], "focus": [0.5, 0.5], "scene": "١ · فريق الحراسة"},
    {"id": "S10", "img": "s05_mission_cheer", "move": "pan_left", "lines": ["10_nana"],
     "pad": [0.25, 0.5], "focus": [0.55, 0.5], "scene": "١ · فريق الحراسة"},
    {"id": "S11", "img": "s02_gigi_dad", "move": "close_push", "lines": ["11_gigi"],
     "pad": [0.25, 0.5], "focus": [0.4, 0.55], "scene": "١ · فريق الحراسة"},
    {"id": "S12", "img": "s06_group_hug", "move": "pull_out", "lines": ["12_narrator"],
     "pad": [0.3, 0.6], "focus": [0.5, 0.5], "scene": "١ · فريق الحراسة"},
    {"id": "S13", "img": "s07_phone_rings", "move": "push_in", "dur": 3.4,
     "focus": [0.5, 0.5], "scene": "١ · الهاتف"},
    {"id": "S14", "img": "s08_workshop_table", "move": "push_in", "lines": ["13_narrator"],
     "pad": [0.4, 0.6], "focus": [0.5, 0.5], "scene": "٢ · ورشة الهدية"},
    {"id": "S15", "img": "s09_susu_drawing", "move": "push_in", "lines": ["14_susu"],
     "pad": [0.25, 0.5], "focus": [0.5, 0.5], "scene": "٢ · ورشة الهدية"},
    {"id": "S16", "img": "s10_nana_card", "move": "push_in", "lines": ["15_nana"],
     "pad": [0.25, 0.5], "focus": [0.5, 0.5], "scene": "٢ · ورشة الهدية"},
    {"id": "S17", "img": "s11_gigi_handprint", "move": "push_in", "lines": ["16_gigi"],
     "pad": [0.25, 0.5], "focus": [0.5, 0.5], "scene": "٢ · ورشة الهدية"},
    {"id": "S18", "img": "s11_gigi_handprint", "move": "close_push", "lines": ["17_narrator"],
     "pad": [0.25, 0.5], "focus": [0.5, 0.55], "scene": "٢ · ورشة الهدية"},
    {"id": "S19", "img": "s12_dad_ready", "move": "push_in", "lines": ["18_khaled"],
     "pad": [0.3, 0.6], "focus": [0.5, 0.5], "scene": "٢ · الاستعداد"},
    {"id": "S20", "img": "s13_hero_walk", "move": "tilt_up", "lines": ["19_narrator"],
     "pad": [0.3, 0.6], "focus": [0.5, 0.55], "scene": "٢ · الاستعداد"},
    {"id": "S21", "img": "s14_corridor", "move": "push_in", "lines": ["20_narrator"],
     "pad": [0.4, 0.6], "focus": [0.5, 0.5], "scene": "٣ · ممر المستشفى"},
    {"id": "S22", "img": "s14_corridor", "move": "close_push", "lines": ["21_girls"],
     "pad": [0.3, 0.6], "focus": [0.5, 0.5], "scene": "٣ · ممر المستشفى"},
    {"id": "S23", "img": "s15_mother_arms", "move": "push_in", "lines": ["22_sara"],
     "pad": [0.3, 0.6], "focus": [0.5, 0.45], "scene": "٣ · اللقاء"},
    {"id": "S24", "img": "s15_mother_arms", "move": "close_push", "lines": ["23_khaled"],
     "pad": [0.3, 0.6], "focus": [0.45, 0.45], "scene": "٣ · اللقاء"},
    {"id": "S25", "img": "s11_gigi_handprint", "move": "pan_right", "lines": ["24_narrator"],
     "pad": [0.3, 0.6], "focus": [0.5, 0.5], "scene": "٣ · الهدية"},
    {"id": "S26", "img": "s16_bassinet", "move": "push_in", "lines": ["25_susu"],
     "pad": [0.3, 0.6], "focus": [0.5, 0.5], "scene": "٣ · الهدية"},
    {"id": "S27", "img": "s17_baby_closeup", "move": "push_in", "lines": ["26_narrator"],
     "pad": [0.4, 0.7], "focus": [0.5, 0.45], "scene": "٣ · غيث"},
    {"id": "S28", "img": "s18_gigi_wow", "move": "push_in", "lines": ["27_gigi"],
     "pad": [0.25, 0.5], "focus": [0.5, 0.45], "scene": "٣ · غيث"},
    {"id": "S29", "img": "s19_nana_pinky", "move": "close_push", "lines": ["28_nana"],
     "pad": [0.3, 0.6], "focus": [0.5, 0.5], "scene": "٣ · غيث"},
    {"id": "S30", "img": "s20_sara_proud", "move": "push_in", "lines": ["29_sara"],
     "pad": [0.3, 0.6], "focus": [0.5, 0.45], "scene": "٣ · غيث"},
    {"id": "S31", "img": "s21_sisters_around", "move": "hold_drift", "dur": 8.0,
     "song": True, "focus": [0.5, 0.5], "scene": "٤ · النشيد"},
    {"id": "S32", "img": "s22_song_wide", "move": "pull_out", "dur": 8.0,
     "song": True, "focus": [0.5, 0.5], "scene": "٤ · النشيد"},
    {"id": "S33", "img": "s17_baby_closeup", "move": "close_push", "dur": 7.0,
     "song": True, "focus": [0.5, 0.45], "scene": "٤ · النشيد"},
    {"id": "S34", "img": "s21_sisters_around", "move": "push_in", "dur": 7.0,
     "song": True, "focus": [0.5, 0.5], "scene": "٤ · النشيد"},
    {"id": "S35", "img": "s22_song_wide", "move": "hold_drift", "lines": ["30_closing"],
     "pad": [1.0, 1.2], "focus": [0.5, 0.5], "scene": "٤ · الختام"},
    {"id": "S36", "img": "s24_photo_frame", "move": "push_in", "dur": 6.0,
     "focus": [0.5, 0.5], "scene": "٤ · الصورة"},
    {"id": "S37", "card": "end", "dur": 8.0, "move": "hold_drift", "scene": "النهاية"},
]


def shots_spec():
    return {"fps": FPS, "width": WIDTH, "height": HEIGHT, "shots": SHOTS}
