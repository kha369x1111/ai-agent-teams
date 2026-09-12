#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
محرك طاولة التداول المؤسسية — Institutional Trading Desk Orchestrator
======================================================================
جلسة يومية (الوضع الافتراضي):
    طلب → بيانات → 4 محللين بالتوازي (ماكرو/فني/تدفقات/كمي)
        → بوابة مدير المخاطر (1) → مخصص المراكز → بوابة الالتزام (2)
        → نشرة الطاولة → التنفيذ الورقي والسجل.

مراجعة أسبوعية (--mode review):
    طلب → جمع السجلات → مقاييس الأداء → لجنة المخاطر والالتزام → تقرير المراجعة.

قواعد ذهبية (خطوط حمراء مضمّنة في البوابات):
- طاولة تحليل وتخطيط تعليمي، ليست توصيات استثمارية — ولا تنفيذًا حقيقيًا للأموال.
- فصل صلاحيات: من يحلل لا يحدد الحجم، من يحدد الحجم لا ينفذ، وكلمة المخاطر فوق الجميع.
- لا مخرج قبل بوابتين إلزاميتين: مدير المخاطر ثم الالتزام.
- أي مخرج بلا «إخلاء مسؤولية» أو بلا سيناريوهات واحتمالات ترفضه البوابة آليًا.

التشغيل:
    python3 trading_orchestrator.py jobs/desk_2026-09-12             # جلسة يومية (وضع الطيار)
    python3 trading_orchestrator.py jobs/desk_2026-09-12 --api       # تشغيل كامل عبر LLM
    python3 trading_orchestrator.py jobs/review_w38 --mode review    # مراجعة أسبوعية
"""
import argparse, json, os, sys, urllib.request
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
AGENTS = BASE / "agents"

# ─── الجلسة اليومية ─────────────────────────────────────────────────────────
# (الملف، العناصر الإلزامية للبوابة، بطاقة الوكيل)
PHASES_DAILY = {
    "request": {"label": "طلب الجلسة", "next": "data", "files": [
        ("00_request.md", ["# طلب", "الأصول", "الحدود"], None)]},
    "data": {"label": "جمع البيانات", "next": "analysis", "files": [
        ("01_data.md", ["http", "المصدر"], "t02_market_data.md")]},
    "analysis": {"label": "التحليل (4 محللين بالتوازي)", "next": "risk", "files": [
        ("02a_macro.md", ["سيولة", "http"], "t03_macro_strategist.md"),
        ("02b_technical.md", ["دعم", "مقاومة", "إبطال"], "t04_technical_analyst.md"),
        ("02c_flows.md", ["تموضع", "معنويات"], "t05_flows_analyst.md"),
        ("02d_quant.md", ["تقلب", "ارتباط", "VaR"], "t06_quant_analyst.md")]},
    "risk": {"label": "بوابة مدير المخاطر (إلزامية 1)", "next": "sizing", "files": [
        ("03_risk.md", ["إخلاء مسؤولية", "سيناريو", "وقف", "احتمال"], "t07_risk_manager.md")]},
    "sizing": {"label": "مخصص المراكز", "next": "compliance", "files": [
        ("04_sizing.md", ["حجم المركز", "وقف", "R"], "t08_position_sizer.md")]},
    "compliance": {"label": "بوابة الالتزام (إلزامية 2)", "next": "brief", "files": [
        ("05_compliance.md", ["إخلاء مسؤولية", "الحدود", "قرار"], "t09_compliance.md")]},
    "brief": {"label": "نشرة الطاولة اليومية", "next": "journal", "files": [
        ("06_desk_brief.md", ["إخلاء مسؤولية", "مستوى المخاطرة", "خطة"], "t10_desk_writer.md")]},
    "journal": {"label": "التنفيذ الورقي والسجل", "next": None, "files": [
        ("07_journal.md", ["أمر", "وقف", "سجل"], "t11_execution_journal.md")]},
}

# ─── المراجعة الأسبوعية ─────────────────────────────────────────────────────
PHASES_REVIEW = {
    "request": {"label": "طلب المراجعة", "next": "journals", "files": [
        ("00_request.md", ["# طلب", "مراجعة"], None)]},
    "journals": {"label": "جمع سجلات الجلسات", "next": "metrics", "files": [
        ("01_journals.md", ["سجل"], "t12_performance_analyst.md")]},
    "metrics": {"label": "مقاييس الأداء", "next": "committee", "files": [
        ("02_metrics.md", ["معدل الربح", "التراجع", "R"], "t12_performance_analyst.md")]},
    "committee": {"label": "لجنة المخاطر والالتزام", "next": "report", "files": [
        ("03_committee.md", ["الحدود", "قرار"], "t07_risk_manager.md")]},
    "report": {"label": "تقرير المراجعة والدروس", "next": None, "files": [
        ("04_review_report.md", ["إخلاء مسؤولية", "درس"], "t10_desk_writer.md")]},
}


def ts():
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")


def load_status(job):
    p = job / "status.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"phase": "request", "mode": "daily", "history": [], "created": ts()}


def save_status(job, status):
    (job / "status.json").write_text(
        json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")


def context_for(job, phase, fname, mode):
    """ما يُسمح لكل وكيل برؤيته — فصل صلاحيات، واستقلالية المحللين."""
    parts = []

    def add(name, f):
        p = job / f
        if p.exists():
            parts.append(f"===== {name} | {f} =====\n" + p.read_text(encoding="utf-8"))

    add("الطلب", "00_request.md")
    if mode == "daily":
        if phase in ("analysis", "risk", "sizing", "compliance", "brief", "journal"):
            add("البيانات المعتمدة", "01_data.md")
        if phase == "analysis":
            pass  # المحللون لا يرون عمل بعضهم → استقلالية
        if phase in ("risk", "sizing", "compliance", "brief", "journal"):
            add("تحليل الماكرو", "02a_macro.md")
            add("التحليل الفني", "02b_technical.md")
            add("التدفقات والتموضع", "02c_flows.md")
            add("التحليل الكمي", "02d_quant.md")
        if phase in ("sizing", "compliance", "brief", "journal"):
            add("قرار بوابة المخاطر", "03_risk.md")
        if phase in ("compliance", "brief", "journal"):
            add("الأحجام المعتمدة", "04_sizing.md")
        if phase in ("brief", "journal"):
            add("قرار بوابة الالتزام", "05_compliance.md")
        if phase == "journal":
            add("نشرة الطاولة", "06_desk_brief.md")
    else:  # review
        if phase in ("metrics", "committee", "report"):
            add("السجلات المجمعة", "01_journals.md")
        if phase in ("committee", "report"):
            add("مقاييس الأداء", "02_metrics.md")
    return "\n\n".join(parts)


def llm_generate(system, user):
    base = (os.environ.get("LLM_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
    key = os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")
    model = os.environ.get("LLM_MODEL", "gpt-4o-mini")
    if not key:
        sys.exit("✖ وضع --api يتطلب مفتاحًا في LLM_API_KEY")
    payload = {"model": model, "temperature": 0.4,
               "messages": [{"role": "system", "content": system},
                            {"role": "user", "content": user}]}
    req = urllib.request.Request(base + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read().decode("utf-8"))["choices"][0]["message"]["content"]


def run(job_dir, use_api, mode):
    if use_api and not (os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")):
        sys.exit("✖ وضع --api يتطلب مفتاحًا في متغير LLM_API_KEY")
    job = Path(job_dir)
    job.mkdir(parents=True, exist_ok=True)
    phases = PHASES_DAILY if mode == "daily" else PHASES_REVIEW
    status = load_status(job)
    # إن كانت المهمة جديدة، ثبّت وضعها؛ وإن كانت قائمة بوضع مختلف فأعد الضبط صراحة
    if not status["history"]:
        status["mode"] = mode
    elif status.get("mode") != mode:
        sys.exit(f"✖ المهمة بدأت بوضع «{status.get('mode')}» — لا تخلط الأوضاع في مهمة واحدة.")
    save_status(job, status)

    print("=" * 64)
    print("  طاولة التداول المؤسسية — محرك التنسيق")
    print(f"  المهمة: {job.name} · الوضع: {'جلسة يومية' if mode == 'daily' else 'مراجعة أسبوعية'}")
    print("=" * 64)

    for _ in range(24):
        phase = status["phase"]
        if phase == "done":
            final = "07_journal.md" if mode == "daily" else "04_review_report.md"
            print(f"\n🎉 الجلسة مكتملة وكل البوابات معتمدة — المخرج النهائي: {final}")
            return 0
        spec = phases[phase]
        pending, all_passed = [], True
        for fname, markers, agent_file in spec["files"]:
            fpath = job / fname
            if not fpath.exists():
                pending.append((fname, agent_file))
                all_passed = False
                continue
            text = fpath.read_text(encoding="utf-8")
            missing = [m for m in markers if m not in text]
            if missing:
                print(f"\n⚠ بوابة «{spec['label']}» رفضت {fname} — ينقصه: {missing}")
                pending.append((fname, agent_file))
                all_passed = False

        if all_passed:
            files = ", ".join(f for f, _, _ in spec["files"])
            status["history"].append({"phase": phase, "state": "passed",
                                      "files": files, "ts": ts()})
            if spec["next"] is None:
                status["phase"] = "done"
                save_status(job, status)
                print(f"✔ {spec['label']}: معتمد.")
                print("\n🎉 الجلسة مكتملة وكل البوابات معتمدة.")
                return 0
            status["phase"] = spec["next"]
            save_status(job, status)
            print(f"✔ {spec['label']}: معتمد — التالي: {phases[status['phase']]['label']}.")
            continue

        # تعيين الملفات الناقصة (في analysis تُعيَّن الأربعة دفعة واحدة = توازٍ)
        for fname, agent_file in pending:
            status["history"].append({"phase": phase, "state": "assigned",
                                      "file": fname, "ts": ts()})
            card = ""
            if agent_file:
                card = (AGENTS / agent_file).read_text(encoding="utf-8")
            prompt = (f"أنت وكيل في طاولة تداول مؤسسية. بطاقة دورك:\n\n{card}\n\n"
                      f"━━━━ السياق ━━━━\n{context_for(job, phase, fname, mode)}\n\n"
                      f"أنتج الملف {fname} كاملًا بالعربية (Markdown). كل رقم بمصدره. "
                      f"تذكّر: تحليل وتخطيط تعليمي لا توصيات، ولا تنفيذًا حقيقيًا للأموال.")
            if use_api and agent_file:
                print(f"\n🤖 الوكيل يعمل على {fname} ...")
                (job / fname).write_text(llm_generate(card, prompt), encoding="utf-8")
            else:
                print(f"\n▶ {spec['label']} → المطلوب: {fname}")
                print("-" * 60)
                print(prompt if not agent_file else
                      f"بطاقة الوكيل: agents/{agent_file}\n(شغّل الوكيل بالبطاقة أعلاه وأنتج {fname})")
                print("-" * 60)
        save_status(job, status)
        if not use_api:
            print("\n⏸ أنتج الملف/الملفات الناقصة ثم أعد التشغيل — البوابة ستتحقق.")
            return 0
    return 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="محرك طاولة التداول المؤسسية")
    ap.add_argument("job", help="مجلد المهمة (مثال jobs/desk_2026-09-12)")
    ap.add_argument("--api", action="store_true", help="تشغيل الوكلاء تلقائيًا عبر LLM")
    ap.add_argument("--mode", choices=["daily", "review"], default="daily",
                    help="daily: جلسة يومية | review: مراجعة أسبوعية")
    args = ap.parse_args()
    sys.exit(run(args.job, args.api, args.mode))
