"""Fetch consolidated Swiss federal acts from Fedlex and split them into articles and paragraphs.

Fedlex publishes every consolidated version of every act as HTML in its filestore, one file per
language. We ask the public SPARQL endpoint which version was in force on a given date, download
that file, and keep the paragraph structure, because every answer in the dataset is cited down
to the paragraph (e.g. OR Art. 335c para. 1).

    python -m fa.fedlex data/corpus 2026-10-01          # all acts in ACTS, de/fr/it (+rm if published)
    python -m fa.fedlex data/corpus_first first         # the first HTML version of each act (early 2021)
"""
import html
import json
import pathlib
import re
import sys
import time
import urllib.parse
import urllib.request

SPARQL = "https://fedlex.data.admin.ch/sparqlendpoint"
UA = {"user-agent": "fedlex-answer/0.1 (+https://github.com/bisale24-ops/fedlex-answer)"}
LANGS = {"de": "DEU", "fr": "FRA", "it": "ITA", "rm": "ROH"}

# SR number -> short name. Federal acts a resident or a front-desk official meets in everyday life.
ACTS = {
    "101": "BV",        # Federal Constitution
    "210": "ZGB",       # Civil Code
    "220": "OR",        # Code of Obligations (employment, tenancy, sale)
    "141.0": "BüG",     # Swiss Citizenship Act
    "142.20": "AIG",    # Foreign Nationals and Integration Act
    "161.1": "BPR",     # Federal Act on Political Rights
    "831.10": "AHVG",   # Old-Age and Survivors' Insurance Act
    "832.10": "KVG",    # Health Insurance Act
    "834.1": "EOG",     # Loss of Earnings Compensation Act (maternity, paternity)
    "837.0": "AVIG",    # Unemployment Insurance Act
    "822.11": "ArG",    # Labour Act
    "281.1": "SchKG",   # Debt Enforcement and Bankruptcy Act
    "272": "ZPO",       # Civil Procedure Code
    "172.021": "VwVG",  # Administrative Procedure Act
    "311.0": "StGB",    # Criminal Code
    "741.01": "SVG",    # Road Traffic Act
}

ART = re.compile(r'<article id="(art_[0-9a-z_]+)">(.*?)</article>', re.S)
HEAD = re.compile(r"<h6[^>]*>(.*?)</h6>", re.S)
PARA = re.compile(r'<p class="absatz[^"]*">(.*?)</p>|<dl[^>]*>(.*?)</dl>', re.S)
SUP = re.compile(r"<sup>(\d+[a-z]*)</sup>")
FOOTNOTE = re.compile(r'<sup><a [^>]*href="#fn[^"]*"[^>]*>.*?</a></sup>', re.S)


def sparql(query):
    data = urllib.parse.urlencode({"query": query}).encode()
    req = urllib.request.Request(SPARQL, data=data, headers={**UA, "accept": "application/sparql-results+json"})
    with urllib.request.urlopen(req, timeout=90) as r:  # noqa: S310 - fixed public endpoint
        return [{k: v["value"] for k, v in b.items()} for b in json.load(r)["results"]["bindings"]]


def version(sr, lang, on):
    """ELI work, consolidation date and HTML URL of act `sr` in force on date `on`, or None.

    on="first" picks the baseline for "what admin.ch showed when the statutes moved to Fedlex": the
    consolidation in force on 2021-01-01, or, when Fedlex has no HTML for that one, the first HTML
    consolidation after it. (Fedlex also holds HTML for a few much older consolidations, e.g. ZGB
    2011, which must not serve as the baseline just because they are the newest HTML before 2021.)"""
    rows = sparql(f"""
PREFIX jolux: <http://data.legilux.public.lu/resource/ontology/jolux#>
SELECT ?work ?date ?url WHERE {{
  ?work jolux:historicalLegalId "{sr}" .
  FILTER(STRSTARTS(STR(?work), "https://fedlex.data.admin.ch/eli/cc/"))
  ?cons jolux:isMemberOf ?work ; jolux:dateApplicability ?date ; jolux:isRealizedBy ?expr .
  ?expr jolux:language <http://publications.europa.eu/resource/authority/language/{LANGS[lang]}> ; jolux:isEmbodiedBy ?m .
  ?m jolux:isExemplifiedBy ?url .
}}""")
    if not rows:
        return None
    html = sorted((r for r in rows if "/html/" in r["url"]), key=lambda r: r["date"])
    if on == "first":
        in_force = max((r["date"] for r in rows if r["date"] <= "2021-01-01"), default="2021-01-01")
        after = [r for r in html if r["date"] >= in_force]
        return after[0] if after else None
    before = [r for r in html if r["date"] <= on]
    return before[-1] if before else None


def clean(fragment):
    fragment = FOOTNOTE.sub("", fragment)
    fragment = SUP.sub(r"\1 ", fragment)
    fragment = re.sub(r"<(dt)[^>]*>", " ", fragment)
    fragment = re.sub(r"<[^>]+>", "", fragment)
    return re.sub(r"\s+", " ", html.unescape(fragment).replace("\xa0", " ")).strip()


def parse(raw):
    """{article id: {"heading": str, "paragraphs": [str]}} from one Fedlex HTML file."""
    out = {}
    for art_id, body in ART.findall(raw):
        # nested articles do not occur, but transitional provisions reuse ids: keep the first
        if art_id in out:
            continue
        head = HEAD.search(body)
        paras = [clean(p or dl) for p, dl in PARA.findall(body)]
        paras = [p for p in paras if p]
        if paras:
            out[art_id] = {"heading": clean(head.group(1)) if head else "", "paragraphs": paras}
    return out


def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r:  # noqa: S310
        return r.read().decode("utf-8", errors="replace")


def main(dst, on):
    dst = pathlib.Path(dst)
    dst.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for sr, short in ACTS.items():
        entry = {"short": short, "sr": sr, "on": on, "languages": {}}
        for lang in LANGS:
            v = version(sr, lang, on)
            if not v:
                continue
            raw = fetch(v["url"])
            arts = parse(raw)
            (dst / f"{sr}.{lang}.json").write_text(json.dumps(arts, ensure_ascii=False, indent=0))
            entry["work"] = v["work"]
            entry["languages"][lang] = {"date": v["date"], "url": v["url"], "articles": len(arts)}
            print(f"{short:6} {lang} {v['date']} {len(arts):5} articles", flush=True)
            time.sleep(0.5)
        manifest[sr] = entry
    (dst / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "2026-10-01")
