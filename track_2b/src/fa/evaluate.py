"""Measure the assistant on Swiss Statute QA (Hack Apertus 1B dataset, CDLA-Permissive-2.0).

    python -m fa.evaluate --live                 # ask every de/fr/it question, grade, write data/runs/<model>.jsonl
    python -m fa.evaluate                        # re-grade the recorded answers, no network

Grades with the dataset's own rule grader (numbers with units in four languages) and, for comparison
with the closed-book baseline, the same Apertus-70B judge. Withheld and not-found answers count as
not attempted. Also reported: retrieval recall (gold paragraph among the retrieved) and citation
accuracy (the cited paragraph is the gold one).
"""
import argparse
import concurrent.futures as cf
import json
import os
import pathlib

from . import answer, grade

ROOT = pathlib.Path(__file__).resolve().parents[2]
JUDGE = os.environ.get("JUDGE_NAME", "apertus-v1.5-70b")
DATA = ROOT / "data"


def load():
    meta = {}
    for line in (DATA / "swiss_statute_qa" / "metadata.jsonl").read_text().splitlines():
        m = json.loads(line)
        meta[m["item_id"]] = m
    rows = [json.loads(line) for line in (DATA / "swiss_statute_qa" / "eval.jsonl").read_text().splitlines()]
    return [r for r in rows if r["lang"] in ("de", "fr", "it")], meta


def as_item(row):
    return {"answer": {row["lang"]: row["answer"]}, "aliases": {row["lang"]: row["aliases"]},
            "canonical": {"value": row["canonical_value"], "unit": row["canonical_unit"]},
            "question": {row["lang"]: row["question"]}, "evidence": {row["lang"]: row["evidence"]},
            "superseded": {"value": row["superseded_value"]} if row.get("superseded_value") is not None else None}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--judge", action="store_true", help="also grade with the Apertus-70B judge (live)")
    a = ap.parse_args(argv)
    rows, meta = load()
    if a.limit:
        rows = rows[: a.limit]
    path = DATA / "runs" / f"{answer.MODEL}.jsonl"
    done = {}
    if path.exists():
        for line in path.read_text().splitlines():
            r = json.loads(line)
            done[r["id"]] = r
    todo = [r for r in rows if r["id"] not in done]
    if todo and not a.live:
        print(f"{len(todo)} questions have no recorded answer; run with --live")
    if a.live and todo:
        path.parent.mkdir(parents=True, exist_ok=True)
        def safe(r):
            try:
                return answer.ask(r["question"], r["lang"])
            except Exception as error:  # noqa: BLE001 - rate limits: leave it for the next --live run
                return {"error": repr(error)[:200]}
        with path.open("a") as f, cf.ThreadPoolExecutor(a.workers) as pool:
            for i, (row, res) in enumerate(zip(todo, pool.map(safe, todo)), 1):
                if "error" in res:
                    continue
                rec = {"id": row["id"], "item_id": row["item_id"], **res}
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                f.flush()
                done[row["id"]] = rec
                if i % 100 == 0:
                    print(f"{i}/{len(todo)}", flush=True)
    judged = {}
    jpath = DATA / "runs" / f"judge-{answer.MODEL}.jsonl"
    if jpath.exists():
        for line in jpath.read_text().splitlines():
            j = json.loads(line)
            judged[j["id"]] = j["label"]
    need = [r for r in rows if r["id"] in done and done[r["id"]]["status"] == "answered" and r["id"] not in judged]
    if need and a.live:
        def judge(row):
            body = grade.judge_body(as_item(row), row["lang"], done[row["id"]]["answer"], JUDGE)
            text = answer.chat(body["messages"], max_tokens=body["max_tokens"], model=JUDGE)
            return {"id": row["id"], "label": grade.judge_label(text), "raw": text}
        with jpath.open("a") as f, cf.ThreadPoolExecutor(a.workers) as pool:
            for j in pool.map(judge, need):
                f.write(json.dumps(j, ensure_ascii=False) + "\n")
                judged[j["id"]] = j["label"]
    graded = []
    for row in rows:
        rec = done.get(row["id"])
        if not rec:
            continue
        m = meta[row["item_id"]]
        gold = f"{m['act']}:{m['art_id']}:{m['paragraph'] - 1}"
        text = rec["answer"] if rec["status"] == "answered" else None
        rule = grade.rule_grade(as_item(row), row["lang"], text) if text else "not_attempted"
        label = (judged.get(row["id"]) or rule) if text else "not_attempted"
        graded.append({"id": row["id"], "lang": row["lang"], "status": rec["status"], "label": label, "rule": rule,
                       "retrieved_gold": gold in (rec.get("retrieved") or []),
                       "cited_gold": (rec.get("source") or {}).get("id") == gold,
                       "since_2021": row["since_2021"], "ms": rec.get("ms")})
    n = len(graded)
    if not n:
        return 1
    share = lambda f: round(sum(1 for g in graded if f(g)) / n, 4)  # noqa: E731
    summary = {"model": answer.MODEL, "n": n,
               "correct": share(lambda g: g["label"] == "correct"),
               "incorrect": share(lambda g: g["label"] == "incorrect"),
               "not_attempted": share(lambda g: g["label"] == "not_attempted"),
               "withheld_by_verifier": share(lambda g: g["status"] == "withheld"),
               "retrieval_recall": share(lambda g: g["retrieved_gold"]),
               "cites_gold_paragraph": share(lambda g: g["cited_gold"]),
               "median_ms": sorted(g["ms"] or 0 for g in graded)[n // 2]}
    summary["correct_by_rule"] = share(lambda g: g["rule"] == "correct")
    attempted = [g for g in graded if g["label"] != "not_attempted"]
    summary["wrong_when_attempted"] = round(sum(g["label"] == "incorrect" for g in attempted) / max(1, len(attempted)), 4)
    for lang in ("de", "fr", "it"):
        sub = [g for g in graded if g["lang"] == lang]
        summary[f"correct_{lang}"] = round(sum(g["label"] == "correct" for g in sub) / max(1, len(sub)), 4)
    out = DATA / "results" / f"{answer.MODEL}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"summary": summary, "graded": graded}, ensure_ascii=False, indent=0))
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
