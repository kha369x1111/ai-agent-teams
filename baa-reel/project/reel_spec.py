"""Master Production Specification — حرف الباء (ب): ثوب الوجود وسر النقطة التكوينية.

Project: أكاديمية مفتاح الأسرار السبعة (Academy of the Key of the Seven Secrets)
Series:  سلسلة الحروف الكوانتية (Quantum Letters Symbolic Heritage Series — Ep. 02: الباء)
Format:  Vertical Reels 9:16 · 1080×1920 · 30 FPS · ~73.5s Cinematic 4K-Graded Look
"""

from __future__ import annotations

W = 1080
H = 1920
FPS = 30
TOTAL_DURATION = 73.8

PALETTE = {
    "charcoal":        (11, 10, 14),
    "obsidian":        (18, 15, 20),
    "parchment_dark":  (58, 39, 24),
    "parchment_warm":  (94, 65, 39),
    "bronze":          (142, 98, 54),
    "gold_deep":       (178, 134, 62),
    "gold_antique":    (212, 172, 92),
    "gold_bright":     (244, 214, 142),
    "light_white":     (255, 251, 240),
}

# 7 Scenes strictly following the Master Production Prompt
SCENES = [
    {
        "id": "S01",
        "num": 1,
        "name": "الخطاف — انبثاق النقطة",
        "start": 0.0,
        "end": 7.0,
        "audio_id": "s01_hook",
        "vo_offset": 0.55,
        "target_vo_dur": 5.95,
        "on_screen_title": ["سر الباء… سر الظهور"],
        "narration": "قبل أن تتعدد الصور… وقبل أن تتشكل الكثرة… كانت هناك نقطة. ومنها يبدأ سر حرف الباء.",
        "clauses": [
            {"text": "قبل أن تتعدد الصور…", "highlight": ["الصور"]},
            {"text": "وقبل أن تتشكل الكثرة…", "highlight": ["الكثرة"]},
            {"text": "كانت هناك نقطة.", "highlight": ["نقطة"]},
            {"text": "ومنها يبدأ سر حرف الباء.", "highlight": ["سر", "الباء"]},
        ],
        "vfx_mode": "hook_nuqta_genesis",
        "shots": [
            {
                "id": "S01A",
                "img": "s01_primordial_point",
                "start": 0.0,
                "end": 3.6,
                "move": "dolly_in_fast",
                "focus": [0.50, 0.50],
            },
            {
                "id": "S01B",
                "img": "s01_energy_mandala",
                "start": 3.6,
                "end": 7.0,
                "move": "slow_orbit_in",
                "focus": [0.50, 0.49],
            },
        ],
    },
    {
        "id": "S02",
        "num": 2,
        "name": "الهوية الحرفية — العدد والرمز",
        "start": 7.0,
        "end": 17.0,
        "audio_id": "s02_identity",
        "vo_offset": 0.45,
        "target_vo_dur": 9.05,
        "on_screen_title": ["الباء = 2 | العدد والرمز"],
        "narration": "الباء… ثاني الحروف في ترتيب الأبجدية. قيمته العددية اثنان، وفي تأويلات أهل الحروف ارتبط ببداية التفرع وظهور الكثرة.",
        "clauses": [
            {"text": "الباء… ثاني الحروف في ترتيب الأبجدية.", "highlight": ["الباء", "ثاني"]},
            {"text": "قيمته العددية اثنان،", "highlight": ["اثنان"]},
            {"text": "وفي تأويلات أهل الحروف", "highlight": ["تأويلات"]},
            {"text": "ارتبط ببداية التفرع وظهور الكثرة.", "highlight": ["التفرع", "الكثرة"]},
        ],
        "vfx_mode": "manuscript_square_two",
        "shots": [
            {
                "id": "S02A",
                "img": "s02_ancient_manuscript",
                "start": 7.0,
                "end": 12.0,
                "move": "dolly_in",
                "focus": [0.50, 0.58],
            },
            {
                "id": "S02B",
                "img": "s02_fourfold_square",
                "start": 12.0,
                "end": 17.0,
                "move": "slow_orbit_right",
                "focus": [0.50, 0.51],
            },
        ],
    },
    {
        "id": "S03",
        "num": 3,
        "name": "سر النقطة — أصل الخط",
        "start": 17.0,
        "end": 28.0,
        "audio_id": "s03_nuqta",
        "vo_offset": 0.45,
        "target_vo_dur": 10.00,
        "on_screen_title": ["النقطة أصل الخط"],
        "narration": "أما النقطة… فهي سر التركيز وأصل الخط في الرمز العرفاني. موضع صغير… يحمل في التأويل معنى البداية، وأصل البناء.",
        "clauses": [
            {"text": "أما النقطة… فهي سر التركيز", "highlight": ["النقطة", "التركيز"]},
            {"text": "وأصل الخط في الرمز العرفاني.", "highlight": ["أصل", "الخط"]},
            {"text": "موضع صغير… يحمل في التأويل", "highlight": ["التأويل"]},
            {"text": "معنى البداية، وأصل البناء.", "highlight": ["البداية", "البناء"]},
        ],
        "vfx_mode": "macro_nuqta_filaments",
        "shots": [
            {
                "id": "S03A",
                "img": "s03_macro_nuqta",
                "start": 17.0,
                "end": 22.5,
                "move": "macro_dive",
                "focus": [0.50, 0.51],
            },
            {
                "id": "S03B",
                "img": "s03_cosmic_filaments",
                "start": 22.5,
                "end": 28.0,
                "move": "tilt_ascend",
                "focus": [0.50, 0.56],
            },
        ],
    },
    {
        "id": "S04",
        "num": 4,
        "name": "الميزان الخيميائي — التشكيل والتثبيت",
        "start": 28.0,
        "end": 39.0,
        "audio_id": "s04_alchemy",
        "vo_offset": 0.45,
        "target_vo_dur": 10.05,
        "on_screen_title": ["من المعنى إلى التشكيل"],
        "narration": "وفي الميزان الخيميائي الرمزي، تمثل الباء معنى التشكيل والتثبيت… انتقال المعنى من اللطافة إلى الصورة، ومن الفكرة إلى البناء.",
        "clauses": [
            {"text": "وفي الميزان الخيميائي الرمزي،", "highlight": ["الميزان", "الرمزي"]},
            {"text": "تمثل الباء معنى التشكيل والتثبيت…", "highlight": ["الباء", "التشكيل", "والتثبيت"]},
            {"text": "انتقال المعنى من اللطافة إلى الصورة،", "highlight": ["اللطافة", "الصورة"]},
            {"text": "ومن الفكرة إلى البناء.", "highlight": ["الفكرة", "البناء"]},
        ],
        "vfx_mode": "alchemical_particle_baa",
        "shots": [
            {
                "id": "S04A",
                "img": "s04_alchemical_mizan",
                "start": 28.0,
                "end": 39.0,
                "move": "slow_orbit_left",
                "focus": [0.47, 0.48],
            },
        ],
    },
    {
        "id": "S05",
        "num": 5,
        "name": "البعد الكوني — الرمز والتكوين",
        "start": 39.0,
        "end": 51.0,
        "audio_id": "s05_cosmic",
        "vo_offset": 0.50,
        "target_vo_dur": 10.85,
        "on_screen_title": ["الرمز والتكوين"],
        "narration": "هنا يلتقي الرمز بلغة العلم المعاصر… لا بوصفهما حقيقة واحدة، بل بوصفهما طريقتين مختلفتين للتأمل في التكوين والمادة.",
        "clauses": [
            {"text": "هنا يلتقي الرمز بلغة العلم المعاصر…", "highlight": ["الرمز", "العلم"]},
            {"text": "لا بوصفهما حقيقة واحدة،", "highlight": ["حقيقة"]},
            {"text": "بل بوصفهما طريقتين مختلفتين", "highlight": ["طريقتين"]},
            {"text": "للتأمل في التكوين والمادة.", "highlight": ["للتأمل", "التكوين", "والمادة"]},
        ],
        "vfx_mode": "cosmic_waves_polyhedra",
        "shots": [
            {
                "id": "S05A",
                "img": "s05_cosmic_waves",
                "start": 39.0,
                "end": 51.0,
                "move": "dolly_in",
                "focus": [0.50, 0.50],
            },
        ],
    },
    {
        "id": "S06",
        "num": 6,
        "name": "البيان السيادي — الاحتواء والسند",
        "start": 51.0,
        "end": 65.0,
        "audio_id": "s06_sovereign",
        "vo_offset": 0.45,
        "target_vo_dur": 13.00,
        "on_screen_title": ["القوة الحقيقية… في الاحتواء"],
        "narration": "رسالة الباء إليك… أن القوة ليست في التسلط، بل في الاحتواء. كن سنداً، ووعاءً للمبادرات، ثابتاً في أصلك، متواضعاً في مقامك، عظيماً في أثرك.",
        "clauses": [
            {"text": "رسالة الباء إليك…", "highlight": ["رسالة", "الباء"]},
            {"text": "أن القوة ليست في التسلط، بل في الاحتواء.", "highlight": ["القوة", "الاحتواء"]},
            {"text": "كن سنداً، ووعاءً للمبادرات،", "highlight": ["سنداً", "ووعاءً"]},
            {"text": "ثابتاً في أصلك، متواضعاً في مقامك،", "highlight": ["ثابتاً", "متواضعاً"]},
            {"text": "عظيماً في أثرك.", "highlight": ["عظيماً", "أثرك"]},
        ],
        "vfx_mode": "sovereign_arabesque_baa",
        "shots": [
            {
                "id": "S06A",
                "img": "s06_sovereign_manuscript",
                "start": 51.0,
                "end": 65.0,
                "move": "sovereign_push",
                "focus": [0.50, 0.47],
            },
        ],
    },
    {
        "id": "S07",
        "num": 7,
        "name": "الخاتمة — أكاديمية مفتاح الأسرار السبعة",
        "start": 65.0,
        "end": TOTAL_DURATION,
        "audio_id": "s07_finale",
        "vo_offset": 0.40,
        "target_vo_dur": 8.15,
        "on_screen_title": [
            "أكاديمية مفتاح الأسرار السبعة",
            "تابع سلسلة الحروف الكوانتية",
        ],
        "narration": "هذه قراءة رمزية في أسرار الحروف… من أكاديمية مفتاح الأسرار السبعة. وأنت… ما السر الذي تراه في النقطة؟",
        "clauses": [
            {"text": "هذه قراءة رمزية في أسرار الحروف…", "highlight": ["قراءة", "رمزية"]},
            {"text": "من أكاديمية مفتاح الأسرار السبعة.", "highlight": ["مفتاح", "الأسرار", "السبعة"]},
            {"text": "وأنت… ما السر الذي تراه في النقطة؟", "highlight": ["السر", "النقطة؟"]},
        ],
        "vfx_mode": "closing_academy_seal",
        "shots": [
            {
                "id": "S07A",
                "img": "s07_closing_codex",
                "start": 65.0,
                "end": TOTAL_DURATION,
                "move": "pull_out_seal",
                "focus": [0.50, 0.54],
            },
        ],
    },
]

# Sound Design Cue Sheet (exact frame-locked SFX triggers)
SFX_CUES = [
    {"time": 0.42,  "type": "nuqta_chime",     "gain": 0.72, "note": "انبثاق النقطة الذهبية في الظلام المطلق"},
    {"time": 2.35,  "type": "baa_sub_pulse",   "gain": 0.85, "note": "ظهور حرف الباء من النقطة التكوينية"},
    {"time": 7.00,  "type": "parchment_open",  "gain": 0.65, "note": "انفتاح المخطوطة العربية القديمة"},
    {"time": 9.80,  "type": "baa_sub_pulse",   "gain": 0.62, "note": "تجلّي العدد ٢ والهندسة المربعة"},
    {"time": 12.10, "type": "nuqta_chime",     "gain": 0.48, "note": "إضاءة أركان المربع الأربعة"},
    {"time": 17.05, "type": "baa_sub_pulse",   "gain": 0.70, "note": "التقريب السينمائي نحو النقطة"},
    {"time": 18.20, "type": "nuqta_chime",     "gain": 0.78, "note": "رنين النقطة بوصفها سر التركيز"},
    {"time": 22.50, "type": "cosmic_swell",    "gain": 0.60, "note": "تفرع الخطوط الذهبية نحو الفضاء"},
    {"time": 28.05, "type": "sand_shimmer",    "gain": 0.68, "note": "تجمع التراب الذهبي في الميزان الخيميائي"},
    {"time": 34.40, "type": "baa_sub_pulse",   "gain": 0.74, "note": "تكاثف الجزيئات في هيئة حرف الباء"},
    {"time": 39.05, "type": "cosmic_swell",    "gain": 0.72, "note": "التقاء الموجات الضوئية في البعد الكوني"},
    {"time": 51.00, "type": "parchment_open",  "gain": 0.58, "note": "تقليب الرق الملكي في البيان السيادي"},
    {"time": 51.60, "type": "baa_sub_pulse",   "gain": 0.88, "note": "ظهور الباء الضخم فوق المخطوطة"},
    {"time": 53.20, "type": "nuqta_chime",     "gain": 0.62, "note": "توهج النقطة والزخارف الهندسية"},
    {"time": 65.05, "type": "parchment_close", "gain": 0.70, "note": "إغلاق المخطوطة العتيقة ببطء"},
    {"time": 67.20, "type": "baa_sub_pulse",   "gain": 0.76, "note": "ثبات حرف الباء وشعار الأكاديمية"},
    {"time": 67.35, "type": "nuqta_chime",     "gain": 0.68, "note": "رنين ختم مفتاح الأسرار السبعة"},
]

PUBLISH_METADATA = {
    "title": "سر حرف الباء… لماذا تبدأ الحكاية من النقطة؟",
    "description": (
        "في تراث علم الحروف، لا يُقرأ الحرف بوصفه صوتاً فحسب، بل بوصفه رمزاً يحمل طبقات من التأويل والمعنى.\n\n"
        "الباء، ونقطتها، وسر ظهور الكثرة… قراءة تراثية رمزية من أكاديمية مفتاح الأسرار السبعة.\n\n"
        "هل ترى في النقطة مجرد علامة كتابية، أم رمزاً لبداية البناء؟"
    ),
    "hashtags": [
        "#أكاديمية_مفتاح_الأسرار_السبعة",
        "#حرف_الباء",
        "#سر_النقطة",
        "#علم_الحروف",
        "#الفتوحات_المكية",
        "#المخطوطات_العربية",
        "#أسرار_الحروف",
    ],
}
