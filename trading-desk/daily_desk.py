#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
المشغّل اليومي لطاولة التداول المؤسسية.
========================================
1) ينشئ مجلد مهمة بتاريخ اليوم ويضع طلب الجلسة (من القالب).
2) يشغّل محرك الطاولة (وضع --api تلقائيًا إن وُجد المفتاح، أو وضع الطيار المساعد).
3) سجل تشغيل في logs/.

الاستخدام:
    python3 daily_desk.py                  # جلسة اليوم (api إن وُجد المفتاح)
    python3 daily_desk.py --date 2026-09-12
    python3 daily_desk.py --manual         # وضع الطيار المساعد (بلا API)
    python3 daily_desk.py --mode review    # مهمة مراجعة أسبوعية بدل الجلسة اليومية
"""
import argparse, datetime, subprocess, sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
JOBS = BASE / "jobs"
LOGS = BASE / "logs"
TEMPLATES = BASE / "briefs"


def log(msg):
    print(f"[{datetime.datetime.now():%H:%M:%S}] {msg}")


def make_request(job: Path, date_str: str, mode: str):
    job.mkdir(parents=True, exist_ok=True)
    req = job / "00_request.md"
    if req.exists():
        log("طلب الجلسة موجود مسبقًا.")
        return
    template = TEMPLATES / ("template_request_review.md" if mode == "review"
                            else "template_request_daily.md")
    text = template.read_text(encoding="utf-8").replace("{{DATE}}", date_str)
    req.write_text(text, encoding="utf-8")
    log("أُنشئ طلب الجلسة من القالب.")


def run_team(job: Path, use_api: bool, mode: str) -> bool:
    cmd = [sys.executable, str(BASE / "trading_orchestrator.py"), str(job), "--mode", mode]
    if use_api:
        cmd.append("--api")
    r = subprocess.run(cmd)
    return r.returncode == 0


def main():
    ap = argparse.ArgumentParser(description="المشغّل اليومي لطاولة التداول")
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    ap.add_argument("--manual", action="store_true", help="وضع الطيار المساعد (بلا API)")
    ap.add_argument("--mode", choices=["daily", "review"], default="daily")
    args = ap.parse_args()

    LOGS.mkdir(exist_ok=True)
    prefix = "desk" if args.mode == "daily" else "review"
    job = JOBS / f"{prefix}_{args.date}"
    make_request(job, args.date, args.mode)

    has_key = bool(__import__("os").environ.get("LLM_API_KEY")
                    or __import__("os").environ.get("OPENAI_API_KEY"))
    use_api = has_key and not args.manual
    log(("تشغيل وضع --api" if use_api else "تشغيل وضع الطيار المساعد (بلا API)")
        + f" — المهمة: {job.name}")
    ok = run_team(job, use_api, args.mode)
    with open(LOGS / f"{args.date}.log", "a", encoding="utf-8") as f:
        f.write(f"{datetime.datetime.now().isoformat()} | {job.name} | "
                f"{'مكتملة' if ok else 'قيد الإنجاز (أعد التشغيل بعد تعبئة الملفات)'}\n")
    log("انتهى التشغيل." + ("" if ok else " — أعد التشغيل بعد إنتاج الملفات الناقصة."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
