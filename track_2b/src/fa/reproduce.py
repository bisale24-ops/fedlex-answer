"""Re-grade the recorded evaluation and check every published number, without calling a model.

    python -m fa.reproduce              # exit 0 only if all numbers in data/results/expected.json match
    python -m fa.reproduce --freeze     # (maintainers) write expected.json from the recorded runs
"""
import importlib
import json
import os
import sys

from .evaluate import DATA

MODELS = ("apertus-v1.5-70b", "apertus-v1.5-8b")
KEYS = ("n", "correct", "incorrect", "not_attempted", "withheld_by_verifier", "retrieval_recall",
        "cites_gold_paragraph", "correct_by_rule", "wrong_when_attempted")


def numbers():
    got = {}
    for model in MODELS:
        if not (DATA / "runs" / f"{model}.jsonl").exists():
            continue
        os.environ["LLM_NAME"] = model
        from . import answer, evaluate
        importlib.reload(answer)
        importlib.reload(evaluate)
        evaluate.main([])
        summary = json.loads((DATA / "results" / f"{model}.json").read_text())["summary"]
        for k in KEYS:
            got[f"{model}/{k}"] = summary[k]
        from . import out_of_scope
        importlib.reload(out_of_scope)
        if (DATA / "runs" / f"out_of_scope-{model}.jsonl").exists():
            oos = out_of_scope.main([])
            got[f"{model}/out_of_scope/assistant_answered"] = oos["assistant_answered"]
            got[f"{model}/out_of_scope/closed_book_gave_a_figure"] = oos["closed_book_gave_a_figure"]
    return got


def main(argv):
    got = numbers()
    path = DATA / "results" / "expected.json"
    if "--freeze" in argv:
        path.write_text(json.dumps(got, indent=1, sort_keys=True))
        print(f"froze {len(got)} numbers -> {path}")
        return 0
    want = json.loads(path.read_text())
    bad = [k for k in want if got.get(k) != want[k]]
    for k in bad:
        print(f"MISMATCH {k}: expected {want[k]}, got {got.get(k)}")
    print(f"{len(want) - len(bad)}/{len(want)} published numbers reproduced")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
