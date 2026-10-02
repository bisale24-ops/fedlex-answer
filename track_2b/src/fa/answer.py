"""Answer a question about Swiss federal law from the statute text, with the paragraph it comes from.

Three steps, each one able to say "not in the law" instead of guessing:
  1. retrieve   the k best paragraphs in the question's language (fa.index, BM25);
  2. answer     Apertus reads only those paragraphs and replies "ANSWER: … / SOURCE: P<n>" or NOT_FOUND;
  3. verify     every number in the answer must be stated in the cited paragraph (digits or words); if
                not, the answer is withheld. A cited id outside the retrieved set is withheld too.

The model never answers from memory: closed-book Apertus 70B is wrong on 52% of these questions
(Swiss Statute QA), and the verifier is what turns a fluent wrong number into a refusal.
"""
import json
import os
import pathlib
import re
import time
import unicodedata
import urllib.error
import urllib.request

from .index import Index
from .numbers import numbers_in

BASE = os.environ.get("LLM_BASE_URL", "https://hackapertus.livemap.sh/v1").rstrip("/")
MODEL = os.environ.get("LLM_NAME", "apertus-v1.5-70b")
K = int(os.environ.get("FA_TOP_K", "8"))
UA = "fedlex-answer/0.1 (+https://github.com/bisale24-ops/fedlex-answer)"

SYSTEM = {
    "de": ("Du beantwortest Fragen zum schweizerischen Bundesrecht ausschliesslich anhand der nummerierten "
           "Gesetzesabsätze P1, P2, … Antworte genau in drei Zeilen:\nSOURCE: <P-Nummer des Absatzes, der die Antwort enthält>\n"
           "QUOTE: <die kürzesten Wörter aus diesem Absatz, wörtlich kopiert, die genau den gefragten Fall regeln>\nANSWER: <kurze Antwort, wenige Wörter>\nSteht die Antwort in keinem Absatz, "
           "antworte nur: NOT_FOUND"),
    "fr": ("Tu réponds aux questions sur le droit fédéral suisse uniquement à partir des alinéas numérotés "
           "P1, P2, … Réponds exactement en trois lignes :\nSOURCE: <numéro P de l'alinéa qui contient la réponse>\n"
           "QUOTE: <les mots les plus courts de cet alinéa, copiés mot pour mot, qui règlent exactement le cas demandé>\nANSWER: <réponse brève, quelques mots>\nSi aucun alinéa ne contient la réponse, "
           "réponds seulement : NOT_FOUND"),
    "it": ("Rispondi alle domande sul diritto federale svizzero solo in base ai capoversi numerati P1, P2, … "
           "Rispondi esattamente in tre righe:\nSOURCE: <numero P del capoverso che contiene la risposta>\n"
           "QUOTE: <le parole più brevi di questo capoverso, copiate alla lettera, che regolano esattamente il caso chiesto>\nANSWER: <risposta breve, poche parole>\nSe nessun capoverso contiene la "
           "risposta, rispondi solo: NOT_FOUND"),
}
SYSTEM["rm"] = SYSTEM["de"]

_INDEX = {}


def index(lang):
    if lang not in _INDEX:
        _INDEX[lang] = Index.load(lang if lang in ("de", "fr", "it") else "de")
    return _INDEX[lang]


def api_key():
    key = os.environ.get("LLM_API_KEY", "").strip()
    if key:
        return key
    path = pathlib.Path.home() / ".config" / "cscs.key"
    return path.read_text().strip() if path.exists() else ""


def chat(messages, max_tokens=160, transport=None, model=None):
    body = {"model": model or MODEL, "temperature": 0, "max_tokens": max_tokens, "messages": messages}
    if transport:
        return transport(body)
    req = urllib.request.Request(BASE + "/chat/completions", data=json.dumps(body).encode(), method="POST",
                                 headers={"authorization": f"Bearer {api_key()}", "content-type": "application/json",
                                          "user-agent": UA})
    for attempt in range(8):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:  # noqa: S310 - configured endpoint
                return json.loads(r.read())["choices"][0]["message"]["content"] or ""
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504) or attempt == 7:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == 7:
                raise
        time.sleep(min(60, 2 ** attempt))
    return ""


def label(hit, lang):
    article = hit["article"] or hit["art_id"]
    para = {"de": "Abs.", "fr": "al.", "it": "cpv."}.get(lang, "Abs.")
    return f"{hit['act']} {article} {para} {hit['para_index'] + 1}"


def body(text):
    """The paragraph without its leading number: "4 5 Prozent" is paragraph 4 saying 5 percent, and
    the model reads it as 4.5 percent if the number stays."""
    return re.sub(r"^\d+[a-z]*\s+", "", text)


def prompt(question, hits, lang):
    blocks = [f"P{i + 1} [{label(h, lang)}] {body(h['text'])}" for i, h in enumerate(hits)]
    return "\n\n".join(blocks) + "\n\n" + {"de": "Frage", "fr": "Question", "it": "Domanda"}.get(lang, "Frage") + f": {question}"


def parse(text, n):
    """(answer, source, quote) from the three-line reply. Smaller models sometimes drop the labels
    and reply "P1" / the quote / the answer on bare lines; those are read by position."""
    text = text or ""
    if re.search(r"NOT_FOUND", text):
        return None, None, None
    a = re.search(r"ANSWER\s*:\s*(.+)", text)
    s = re.search(r"SOURCE\s*:\s*\[?P\s*(\d+)", text)
    q = re.search(r"QUOTE\s*:\s*(.+)", text)
    answer = a.group(1).strip() if a else None
    source = int(s.group(1)) if s else None
    quote = q.group(1).strip() if q else None
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    bare = re.fullmatch(r"\[?P\s*(\d+)\]?[.:]?", lines[0]) if lines else None
    if source is None and bare:
        source = int(bare.group(1))
    if bare and len(lines) >= 3:
        rest = [re.sub(r"^(QUOTE|ANSWER)\s*:\s*", "", ln) for ln in lines[1:]]
        quote = quote or rest[0]
        answer = answer or rest[-1]
    if source is not None and not 1 <= source <= n:
        source = None
    return answer, source, (quote.strip('"«»“”') if quote else None)


def _plain(text):
    return re.sub(r"\W+", " ", unicodedata.normalize("NFKC", text or "").replace("’", "'").lower()).strip()


def verify(answer, quote, passage, lang):
    """(ok, reason). The quote must be copied from the cited paragraph, and every number in the answer
    must be stated in the quote: a number that is merely somewhere in the paragraph (the 3 months that
    apply from the tenth year) does not support an answer about the fifth."""
    if not quote or _plain(quote) not in _plain(body(passage)):
        return False, "quote not found in the cited paragraph"
    stated = numbers_in(answer, lang)
    if not stated:
        return True, "ok"
    quoted = numbers_in(quote, lang)
    # "50 %" and "die Hälfte" state the same share
    quoted |= {q * 100 for q in quoted if 0 < q < 1} | {q / 100 for q in quoted if q > 1}
    if all(any(abs(x - y) < 1e-3 for y in quoted) for x in stated):
        return True, "ok"
    return False, "a number in the answer is not in the quoted words"


ACT_CODES = "BV, ZGB, OR, BüG, AIG, BPR, AHVG, KVG, EOG, AVIG, ArG, SchKG, ZPO, VwVG, StGB, SVG"
REWRITE = {
    "de": "Welche Artikel des schweizerischen Bundesrechts regeln diese Frage? Antworte in zwei Zeilen:\n"
          "ARTICLES: bis zu drei Angaben wie 'OR 335c' (Gesetze: " + ACT_CODES + ")\nTERMS: Fachbegriffe, wie sie im Gesetzestext stehen",
    "fr": "Quels articles du droit fédéral suisse règlent cette question ? Réponds en deux lignes :\n"
          "ARTICLES: jusqu'à trois références comme 'OR 335c' (abréviations allemandes : " + ACT_CODES + ")\nTERMS: termes juridiques tels qu'ils figurent dans la loi",
    "it": "Quali articoli del diritto federale svizzero regolano questa domanda? Rispondi in due righe:\n"
          "ARTICLES: fino a tre riferimenti come 'OR 335c' (abbreviazioni tedesche: " + ACT_CODES + ")\nTERMS: termini giuridici come compaiono nella legge",
}
ACT_ALIASES = {"CO": "OR", "CC": "ZGB", "CP": "StGB", "CST": "BV", "COST": "BV", "LP": "SchKG", "LEF": "SchKG",
               "CPC": "ZPO", "LN": "BüG", "LCIT": "BüG", "LEI": "AIG", "LSTRI": "AIG", "LDP": "BPR", "LAVS": "AHVG",
               "LAMAL": "KVG", "LAPG": "EOG", "LIPG": "EOG", "LACI": "AVIG", "LADI": "AVIG", "LTR": "ArG", "LL": "ArG",
               "PA": "VwVG", "LCR": "SVG", "LCSTR": "SVG", "BUG": "BüG"}


def article_refs(text):
    """['OR', 'art_335_c'] pairs from "OR 335c, BV 139"; unknown acts are dropped."""
    known = {a.upper(): a for a in ("BV", "ZGB", "OR", "BüG", "AIG", "BPR", "AHVG", "KVG", "EOG", "AVIG", "ArG",
                                    "SchKG", "ZPO", "VwVG", "StGB", "SVG")}
    out = []
    for act, num, suffix in re.findall(r"\b([A-Za-zÜü]{2,6})\.?\s*(?:Art\.?|art\.?)?\s*(\d+)\s*([a-z]{0,6})\b", text or ""):
        code = act.upper().replace("Ü", "U")
        code = ACT_ALIASES.get(code, code)
        act_name = known.get(code.upper()) or known.get(act.upper())
        if act_name:
            out.append((act_name, f"art_{num}" + (f"_{suffix}" if suffix else "")))
    return out[:3]


def _attempt(question, hits, lang, transport):
    raw = chat([{"role": "system", "content": SYSTEM.get(lang, SYSTEM["de"])},
                {"role": "user", "content": prompt(question, hits, lang)}], transport=transport)
    answer, source, quote = parse(raw, len(hits))
    return raw, answer, source, quote


def ask(question, lang="de", k=K, transport=None):
    """{status: answered | withheld | not_found, answer, source{citation, text, url}, quote, retrieved, ms}."""
    started = time.perf_counter()
    hits = index(lang).search(question, k)
    out = {"question": question, "lang": lang, "model": MODEL, "answer": None, "status": "not_found",
           "source": None, "quote": None, "rewritten": None}
    raw, answer, source, quote = _attempt(question, hits, lang, transport) if hits else ("", None, None, None)
    if not (answer and source):
        # second pass: the question's words are not the statute's ("firme" vs "aventi diritto di voto")
        hint = chat([{"role": "system", "content": REWRITE.get(lang, REWRITE["de"])},
                     {"role": "user", "content": question}], max_tokens=60, transport=transport).strip()
        out["rewritten"] = hint
        seen = {h["id"] for h in hits}
        # the model's memory points to the article; the article's text supplies the answer
        named = [h for act, art in article_refs(hint) for h in index(lang).article(act, art) if h["id"] not in seen]
        terms = re.sub(r"(?i)articles?\s*:.*", "", hint)
        extra = named + [h for h in index(lang).search(question + " " + terms, k) if h["id"] not in seen
                         and h["id"] not in {n["id"] for n in named}]
        if extra:
            hits = hits[: k // 2] + extra[: k - k // 2]
            raw, answer, source, quote = _attempt(question, hits, lang, transport)
    out["retrieved"] = [h["id"] for h in hits]
    out["raw"] = raw
    if answer and source and quote:
        # the quote decides the source: a model that copies the right words but names the neighbouring
        # paragraph is cited where the words actually are
        holders = [i for i, h in enumerate(hits) if _plain(quote) and _plain(quote) in _plain(h["text"])]
        if holders and source - 1 not in holders:
            source = holders[0] + 1
    if answer and source:
        hit = hits[source - 1]
        cite = {"id": hit["id"], "citation": label(hit, lang), "act_name": hit["act_name"], "text": hit["text"],
                "url": hit["url"], "consolidation": hit["consolidation"]}
        ok, why = verify(answer, quote, hit["text"], lang)
        out.update(source=cite, quote=quote)
        if ok:
            out.update(answer=answer, status="answered")
        else:
            out.update(status="withheld", withheld_answer=answer, why=why)
    elif answer:
        out.update(status="withheld", withheld_answer=answer, why="no valid source")
    out["ms"] = round((time.perf_counter() - started) * 1000)
    return out
