# دليل تحريك الصور — من صورة ثابتة إلى لقطة حيّة

هذا هو الجواب العملي على سؤالك: **كيف أحرّك الصور؟** أمامك ثلاث طرق مرتّبة من الأسرع
إلى الأقوى، وكلها مدعومة بـكود جاهز في هذا المشروع.

| الطريقة | ما تحصل عليه | الوقت | الكود |
|---|---|---|---|
| ١. حركة كاميرا (موجودة أصلًا) | زوم/بان/تلت على الصورة | فوري | `tools/render.py` |
| ٢. 2.5D Parallax (داخل الرندر) | إحساس عمق فوري: طبقتان بسرعتين مختلفتين | بلا ملفات وسيطة | `--parallax 0.9` ✅ |
| ٢ب. 2.5D + غبار وإضاءة | نسخة أقوى مع نبض ضوء وذرّات متطايرة | ~٤٠ ثانية/لقطة | `tools/parallax.py` ✅ |
| ٣. Image-to-Video (خارجي) | الشخصيات نفسها تتحرك وتتكلم | يعتمد على الأداة | تستورد الناتج في `storyboard/clips/` |

---

## ١) حركة الكاميرا — جاهزة الآن

كل لقطة في `project/shots_data.py` لها `move`:

```python
{"id": "S01", "img": "s01_livingroom", "move": "push_in", "focus": [0.42, 0.52]}
```

الحركات المتاحة في `tools/render.py::MOVES`:
`push_in` · `pull_out` · `close_push` · `pan_right` · `pan_left` · `tilt_up` · `diag` · `hold_drift`

غيّر `move` أو `focus` ثم أعد الرندر — هذه أسرع طريقة لإعطاء إحساس بالحركة.

---

## ٢) تحريك حقيقي بعمق (2.5D)

### الطريقة الأسرع — داخل الرندر نفسه

```bash
python3 tools/render.py --timeline _work/timeline_full.json --audio _work/mix.wav \
                        --out deliver/ghaith_alhurras_1080p.mp4 --parallax 0.9
```

`--parallax` تقبل 0 (معطّل) حتى 1.5. يبني المحرك قناع عمق ناعمًا حول `focus`
ثم يركّب طبقتين (خلفية أبطأ + مقدمة أسرع) لكل إطار — فيلم كامل بلا أي ملفات وسيطة.
أو: `bash make_film.sh --animate`

### الطريقة الثانية — مقاطع محسوبة مسبقًا (غبار + حبيبات)

تُكتب المقاطع في `storyboard/clips/` ويلتقطها الرندر تلقائيًا

```bash
cd ghaith-film

# لقطات محددة
python3 tools/parallax.py --shots S01 S06 S21 --strength 1.0

# كل اللقطات التي لها صورة
python3 tools/parallax.py --all --strength 1.2
```

**ماذا تفعل الأداة؟**
1. تقرأ اللقطة من `storyboard/raw/<name>.png`.
2. تبني قناعًا بيضاويًا ناعمًا حول نقطة التركيز (`focus`) يفصل «المقدمة» عن «الخلفية».
3. تحرّك نسختين من الصورة بسرعتين واتجاهين مختلفين ثم تدمجهما بالقناع →
   **إحساس بالعمق** (parallax) لا تحصل عليه من زوم بسيط.
4. تضيف: نبض إضاءة خفيف، غبار/ذرّات ضوء متطايرة، حبيبات فيلم، وخفوت أطراف.
5. تكتب الناتج إلى `storyboard/clips/<name>.mp4`.

**ثم** `tools/render.py` يكتشف المقطع تلقائيًا ويستخدمه بدل الصورة:

```
animated shots: 2/38 (storyboard/clips)
```

لذلك لا تحتاج أي تعديل آخر: أعد بناء الفيلم فيُدمج التحريك مع الترجمات والصوت.

> نصيحة: ابدأ باللقطات القريبة من الوجوه (`close_push`) — الحركة فيها تُقرأ أكثر.

---

## ٣) تحريك الشخصيات فعليًا (Image-to-Video)

الصور جاهزة بدقة 1672×941 وبأسلوب متسق، وهي مثالية كإطار أول لأدوات تحويل الصورة إلى فيديو.
استخدم إحدى هذه (خارج هذا المستودع، لا تحتاج تثبيتًا هنا):

| الأداة | الاستخدام |
|---|---|
| **Runway Gen-4 / Gen-3** | «Image to Video» ثم وصف حركة قصيرة |
| **Luma Dream Machine / Ray 2** | تحريك لطيف للوجوه، جودة جيدة للأطفال |
| **Kling AI** | حركة شخصيات وأداء تعبيري |
| **Pika** | حركات كاميرا سريعة وتفاصيل صغيرة |
| **Veo / Sora (وصول محدود)** | أفضل تماسك للشخصية على مدى لقطة كاملة |

### برومبت الحركة (Motion Prompt) — قالب عام

```
Animate this Pixar-style 3D still. Subtle, warm, family-film motion:
- Camera: slow gentle push-in, slight handheld drift.
- {SUBJECT}: {ACTION}
- Keep character faces, clothes and lighting identical to the reference.
- No morphing, no new characters, no text. 24fps, cinematic, 4 seconds.

Negative: warping faces, extra fingers, flicker, jitter, color shift, camera shake.
```

أمثلة جاهزة لكل لقطة رئيسية:

| اللقطة | SUBJECT / ACTION |
|---|---|
| `s01_livingroom` | Father twists the screwdriver; the girl's measuring tape sways; Gigi tucks the teddy in; curtains breathe in the breeze |
| `s02_gigi_dad` | Gigi raises the teddy slightly and blinks; the father's smile widens; dust motes drift through the light |
| `s03_nana_worried` | Nana hugs the blanket tighter, swallows, blinks twice; a slow push-in on her eyes |
| `s04_candle_talk` | The three candles flicker; the father's eyebrow lifts; Nana's eyes glisten as she smiles |
| `s17_baby_closeup` | The newborn's eyes open slowly and his tiny fingers curl around the sister's finger |
| `s19_nana_pinky` | Nana's fingertip trembles slightly; a single tear forms and her smile grows |
| `s22_song_wide` | The family sways gently together; paper stars drift; the window light pulses warmly |

### كيف تُدخل الناتج؟

1. حمّل مقطع الفيديو من الأداة (mp4).
2. أعد تسميته بنفس اسم الصورة وضعه هنا:

```
storyboard/clips/s01_livingroom.mp4
storyboard/clips/s17_baby_closeup.mp4
...
```

3. أعد بناء الفيلم:
```bash
python3 tools/render.py --timeline _work/timeline_full.json \
                        --audio _work/mix.wav \
                        --out deliver/ghaith_alhurras_1080p.mp4
```

المحرك يقرأ المقاطع إطارًا بإطار، ويقصّها أو يمدّها على مدة اللقطة، ويضيف
التلاشي والترجمات والصوت كما هو. **المقاطع الخارجية تُستخدم أولًا**، ثم مقاطع
`parallax.py`، ثم الصور الثابتة — بهذا الترتيب.

---

## ٤) تحريك يدوي احترافي (Blender)

لو أردت تحريكًا ثلاثي الأبعاد كاملًا:

1. صدّر الصورة كمرجع خلفي في Blender (`Add ▸ Image ▸ Reference`).
2. ابنِ الشخصية بكرات (metaballs/basic meshes) أو استخدم **MB-Lab / Human Generator**.
3. استخدم **Rigify** للهيكل و**Mixamo** للحركة الجاهزة (مجاني).
4. صدّر PNG sequence أو MP4 إلى `storyboard/clips/` بنفس الأسماء.
5. أعد الرندر عبر `tools/render.py` (يدعم أي mp4 بنفس المقاس 1920×1080).

> تنبيه واقعي: إنتاج رسوم متحركة كاملة بإطارات مُحرَّكة يدويًا لفيلم ٤ دقائق يحتاج
> فريقًا وأسابيع عمل. المسار الموصى به للمشاريع الفردية هو الجمع بين (٢) و(٣).

---

## ٥) قائمة تحقّق سريعة

- [ ] هل اللقطة في `project/shots_data.py` ولها `img`؟
- [ ] هل الصورة موجودة في `storyboard/raw/`؟
- [ ] هل صوت الحوار موجود في `audio/lines/` أو `audio/lines_wav/`؟
- [ ] جرّب `python3 tools/build.py plan` — يجب ألا يظهر أي سطر في `MISSING AUDIO LINES`.
- [ ] بعد إضافة مقاطع: راقب سطر `animated shots: N/38` عند الرندر.
