# الإنتاج — فريق الحراسة السرّي: مرحباً بك يا غيث

مشروع فيلم قصير ثلاثي الأبعاد (٤:٤٩ دقيقة) بخط أنابيب كامل داخل المستودع:
صور مولّدة بأسلوب Pixar، تعليق صوتي عربي، موسيقى وأنشودة، ترجمات عربية، وتركيب سينمائي.

**البداية:** [`ghaith-film/README.md`](ghaith-film/README.md) · **المشاهدة:** `ghaith-film/index.html`
· **الملف النهائي:** `ghaith-film/out/ghaith_alhurras_1080p.mp4`

| الوثيقة | المحتوى |
|---|---|
| [`docs/character-bible.md`](ghaith-film/docs/character-bible.md) | دستور الشخصيات ولوحة الألوان وقواعد السرد |
| [`docs/shotlist.md`](ghaith-film/docs/shotlist.md) | ٣٨ لقطة + الحوار الكامل بالتوقيت |
| [`docs/prompts.md`](ghaith-film/docs/prompts.md) | حزمة البرومبتات الإنجليزية لكل لقطة |
| [`script/lines.json`](ghaith-film/script/lines.json) | الحوار والأنشودة (نص + مجموعات الصوت) |

## هيكل خط الإنتاج

```
ghaith-film/
├── index.html              صفحة العرض التفاعلية (مشغّل + فصول + حوار + كلمات)
├── project/shots.json      دفتر اللقطات: الصورة، حركة الكاميرا، الحوار، المدة
├── script/lines.json       الحوار + كلمات الأنشودة + مجموعات المقاطع الصوتية
├── storyboard/raw/         صور اللقطات (١٦:٩)
├── audio/lines/            مقاطع التعليق الصوتي
├── assets/fonts/           خطوط Tajawal وAmiri (OFL)
├── tools/
│   ├── artext.py           تشكيل ورسم النص العربي (HarfBuzz + Pillow)
│   ├── score.py            توليد الموسيقى إجرائياً (numpy → WAV)
│   ├── voice_groups.py     تقسيم المقاطع الجماعية إلى أسطر منفصلة
│   ├── build.py            الجدول الزمني، البطاقات، الترجمات، المزج الصوتي
│   ├── render.py           التركيب إطاراً بإطار + الكاميرا + التلاشي + الترميز
│   └── report.py           توليد وثائق الإنتاج وبيانات صفحة العرض
├── build/                  وسائط وسيطة (غير مُتتبَّعة)
└── out/                    الفيلم النهائي والغلاف
```
