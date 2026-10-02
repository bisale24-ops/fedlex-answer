"""Two independent graders for one response: a deterministic rule grader and an LLM judge.

Both return the SimpleQA labels: "correct", "incorrect" or "not_attempted". They disagree on
purpose in different places — the rule grader cannot read paraphrases, the judge can be talked into
things — and the report states how often each agrees with the human annotator.

Rule grader:
  * not_attempted when the response abstains (a refusal phrase in any of the four languages) and
    states no candidate answer;
  * for numeric answers, correct when the canonical number is stated and no *competing* number with
    the same unit is offered as the answer (hedging between two values is incorrect, as in SimpleQA);
  * for non-numeric answers, correct when the answer or an alias occurs in the response.
"""
import re

from .numbers import NUMBER_WORDS, norm, numbers_in

LABELS = ("correct", "incorrect", "not_attempted")

ABSTAIN = re.compile(
    r"(wei(ss|ß)\b[^.?!]{0,40}\bnicht\b|nicht bekannt|kann ich nicht\b|keine (genauen |sicheren |verlässlichen )?(informationen|angaben)"
    r"|je ne\b[^.?!]{0,30}\b(sais|connais) pas|pas en mesure de|aucune information|je n'ai pas (d'information|cette information)"
    r"|non\b[^.?!]{0,30}\b(so|conosco)\b|non sono in grado|nessuna informazione|non ho (informazioni|questa informazione)"
    r"|i don'?t know|not sure|unable to"
    r"|na\b[^.?!]{0,30}\b(sai|sas|enconusch) betg)", re.I)

UNIT_WORDS = {
    "day": r"tag|tage|tagen|jour|jours|giorn|di\b|dis\b",
    "week": r"woche|wochen|semaine|settiman|emna",
    "month": r"monat|mois|mes[ei]|mais",
    "year": r"jahr|an\b|ans\b|année|anni|anno|onn",
    "hour": r"stunde|heure|or[ae]\b|ura|uras",
    "percent": r"%|prozent|pour cent|per cento|pertschient",
}


ARTICLES = {"ein", "eine", "einem", "einer", "einen", "eines", "un", "une", "uno", "una", "in", "ina"}


def numbers_with_unit(text, lang, unit, skip_articles=False):
    """Numbers in `text` followed (within three words) by a word of `unit`; all numbers if no unit pattern.

    With skip_articles, "one" spelled as an article (eines Monats, d'un mois) is not counted: it is
    usually grammar ("to the end of a month"), not a competing answer."""
    pattern = UNIT_WORDS.get(unit)
    t = norm(text)
    if not pattern:
        return numbers_in(text, lang)
    words = [w for w in NUMBER_WORDS.get(lang, {}) if not (skip_articles and w in ARTICLES)]
    num = r"\d+(?:[.,]\d+)?" + ("|" + "|".join(sorted(map(re.escape, words), key=len, reverse=True)) if words else "")
    found = set()
    for m in re.finditer(rf"\b({num})\b(?=(?:\W+\w+){{0,2}}?\W+(?:{pattern}))", t):
        token = m.group(1)
        value = NUMBER_WORDS.get(lang, {}).get(token)
        found.add(float(value) if value is not None else float(token.replace(",", ".")))
    return found


def rule_grade(item, lang, response):
    if response is None:
        return None
    text = response.strip()
    canon = item.get("canonical") or {}
    forms = [item["answer"][lang]] + list(item.get("aliases", {}).get(lang, []))
    if canon.get("value") is not None:
        want = float(canon["value"])
        stated = numbers_with_unit(text, lang, canon.get("unit")) or numbers_in(text, lang)
        hit = any(abs(n - want) < 1e-3 for n in stated)
        if not stated:
            return "not_attempted" if ABSTAIN.search(text) or not text else "incorrect"
        if hit:
            competing = {n for n in numbers_with_unit(text, lang, canon.get("unit"), skip_articles=True) if abs(n - want) > 1e-3}
            return "incorrect" if competing and len(text) < 160 else "correct"
        return "incorrect"
    if any(norm(f) in norm(text) for f in forms):
        return "correct"
    return "not_attempted" if ABSTAIN.search(text) or not text else "incorrect"


JUDGE_SYSTEM = "You grade answers to questions about Swiss federal law. Reply with a single letter."

JUDGE_TEMPLATE = """Grade the predicted answer against the gold answer taken from the statute.

Question ({lang}): {question}
Gold answer: {gold}
Also accepted: {aliases}
Statute text containing the gold answer: "{evidence}"
Predicted answer: {response}

Rules:
- A = CORRECT: the predicted answer states the gold answer (any wording, language, or number format) and does not contradict it. Extra correct context is fine.
- B = INCORRECT: the predicted answer states a different answer, or hedges between several answers, or contradicts the gold answer anywhere.
- C = NOT ATTEMPTED: the predicted answer gives no answer to the question (it declines, says it does not know, or only talks around it) and does not contradict the gold answer.
Reply with exactly one letter: A, B or C."""

LETTER = {"A": "correct", "B": "incorrect", "C": "not_attempted"}


def judge_body(item, lang, response, model):
    prompt = JUDGE_TEMPLATE.format(lang=lang, question=item["question"][lang], gold=item["answer"][lang],
                                   aliases="; ".join(item.get("aliases", {}).get(lang, [])) or "-",
                                   evidence=item["evidence"][lang], response=response.strip()[:1500])
    return {"model": model, "temperature": 0, "max_tokens": 8,
            "messages": [{"role": "system", "content": JUDGE_SYSTEM}, {"role": "user", "content": prompt}]}


def judge_label(text):
    if text is None:
        return None
    m = re.search(r"\b([ABC])\b", text.strip().upper()) or re.match(r"\s*([ABC])", text.strip().upper())
    return LETTER.get(m.group(1)) if m else None


def states_superseded(item, lang, response):
    """True when the response gives the answer the law gave *before* the amendment and not today's.

    Only for items with a numeric `superseded` value; None otherwise. This is the signature of a model
    that learned the pre-2021 text (or a pre-cutoff summary of it) and never saw the change."""
    old = (item.get("superseded") or {}).get("value")
    if old is None or response is None:
        return None
    unit = (item.get("canonical") or {}).get("unit")
    stated = numbers_with_unit(response, lang, unit) or numbers_in(response, lang)
    new = (item.get("canonical") or {}).get("value")
    has_old = any(abs(n - float(old)) < 1e-3 for n in stated)
    has_new = new is not None and any(abs(n - float(new)) < 1e-3 for n in stated)
    return has_old and not has_new
