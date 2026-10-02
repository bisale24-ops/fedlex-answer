"""Does the assistant say "not in the law" when the 16 acts do not hold the answer?

data/out_of_scope/questions.jsonl: 15 questions in de/fr/it whose answers live in cantonal or municipal
law, federal ordinances or other acts (the `where` field says which). Every one should end as
not_found or withheld; an `answered` is a false answer. Closed-book Apertus is asked the same questions
for comparison: there, any concrete figure is a guess about a source it was not given.

    python -m fa.out_of_scope --live          # writes data/runs/out_of_scope-<model>.jsonl
"""
import argparse
import json

from . import answer
from .evaluate import DATA
from .numbers import numbers_in

CLOSED = {"de": "Beantworte die Frage kurz. Wenn du es nicht sicher weisst, sag, dass du es nicht weisst.",
          "fr": "Réponds brièvement. Si tu ne le sais pas avec certitude, dis que tu ne le sais pas.",
          "it": "Rispondi brevemente. Se non lo sai con certezza, di' che non lo sai."}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    a = ap.parse_args(argv)
    path = DATA / "runs" / f"out_of_scope-{answer.MODEL}.jsonl"
    rows = []
    if path.exists():
        rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    elif a.live:
        for line in (DATA / "out_of_scope" / "questions.jsonl").read_text().splitlines():
            q = json.loads(line)
            for lang in ("de", "fr", "it"):
                r = answer.ask(q[lang], lang)
                r.pop("raw", None)
                closed = answer.chat([{"role": "system", "content": CLOSED[lang]}, {"role": "user", "content": q[lang]}])
                rows.append({"id": f"{q['id']}-{lang}", "where": q["where"], "assistant": r, "closed_book": closed})
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    n = len(rows)
    answered = sum(1 for r in rows if r["assistant"]["status"] == "answered")
    closed_figure = sum(1 for r in rows if numbers_in(r["closed_book"], r["id"][-2:]))
    summary = {"prompts": n, "assistant_answered": answered, "assistant_declined": n - answered,
               "closed_book_gave_a_figure": closed_figure}
    print(json.dumps(summary, indent=1))
    out = DATA / "results" / f"out_of_scope-{answer.MODEL}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=1))
    for r in rows:
        if r["assistant"]["status"] == "answered":
            print("ANSWERED:", r["id"], r["assistant"]["answer"], (r["assistant"]["source"] or {}).get("citation"))
    return summary


if __name__ == "__main__":
    main()
