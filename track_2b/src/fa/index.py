"""Paragraph search over the consolidated federal acts: BM25, per language, standard library only.

Every paragraph of every act in data/corpus becomes one document, prefixed with the act's name and
the article heading so that "Arbeitsvertrag Kündigungsfrist" finds OR Art. 335c. Tokens are words plus
their first five letters, a cheap stand-in for stemming that also matches the parts of German compounds
("Kündigungsfrist" ~ "Kündigung").

    from fa.index import Index
    hits = Index.load("de").search("Wie lange ist die Kündigungsfrist im ersten Dienstjahr?", k=6)
"""
import collections
import json
import math
import pathlib
import re
import unicodedata

from .fedlex import ACTS

ROOT = pathlib.Path(__file__).resolve().parents[2]
CORPUS = ROOT / "data" / "corpus"

NAMES = {
    "de": {"BV": "Bundesverfassung", "ZGB": "Zivilgesetzbuch", "OR": "Obligationenrecht", "BüG": "Bürgerrechtsgesetz",
           "AIG": "Ausländer- und Integrationsgesetz", "BPR": "Bundesgesetz über die politischen Rechte",
           "AHVG": "Bundesgesetz über die Alters- und Hinterlassenenversicherung", "KVG": "Krankenversicherungsgesetz",
           "EOG": "Erwerbsersatzgesetz", "AVIG": "Arbeitslosenversicherungsgesetz", "ArG": "Arbeitsgesetz",
           "SchKG": "Bundesgesetz über Schuldbetreibung und Konkurs", "ZPO": "Zivilprozessordnung",
           "VwVG": "Verwaltungsverfahrensgesetz", "StGB": "Strafgesetzbuch", "SVG": "Strassenverkehrsgesetz"},
    "fr": {"BV": "Constitution fédérale (Cst.)", "ZGB": "Code civil (CC)", "OR": "Code des obligations (CO)",
           "BüG": "Loi sur la nationalité (LN)", "AIG": "Loi sur les étrangers et l'intégration (LEI)",
           "BPR": "Loi fédérale sur les droits politiques (LDP)", "AHVG": "Loi sur l'assurance-vieillesse et survivants (LAVS)",
           "KVG": "Loi sur l'assurance-maladie (LAMal)", "EOG": "Loi sur les allocations pour perte de gain (LAPG)",
           "AVIG": "Loi sur l'assurance-chômage (LACI)", "ArG": "Loi sur le travail (LTr)",
           "SchKG": "Loi sur la poursuite pour dettes et la faillite (LP)", "ZPO": "Code de procédure civile (CPC)",
           "VwVG": "Loi sur la procédure administrative (PA)", "StGB": "Code pénal (CP)", "SVG": "Loi sur la circulation routière (LCR)"},
    "it": {"BV": "Costituzione federale (Cost.)", "ZGB": "Codice civile (CC)", "OR": "Codice delle obbligazioni (CO)",
           "BüG": "Legge sulla cittadinanza (LCit)", "AIG": "Legge federale sugli stranieri e la loro integrazione (LStrI)",
           "BPR": "Legge federale sui diritti politici (LDP)", "AHVG": "Legge sull'assicurazione per la vecchiaia e per i superstiti (LAVS)",
           "KVG": "Legge sull'assicurazione malattie (LAMal)", "EOG": "Legge sulle indennità di perdita di guadagno (LIPG)",
           "AVIG": "Legge sull'assicurazione contro la disoccupazione (LADI)", "ArG": "Legge sul lavoro (LL)",
           "SchKG": "Legge sulla esecuzione e sul fallimento (LEF)", "ZPO": "Codice di diritto processuale civile (CPC)",
           "VwVG": "Legge sulla procedura amministrativa (PA)", "StGB": "Codice penale (CP)", "SVG": "Legge sulla circolazione stradale (LCStr)"},
}
STOP = {
    "de": set("der die das den dem des ein eine einer einem eines und oder zu im in ist sind wie wird werden nach mit von bei auf für als an am wenn nicht man es sie er wer was welche welcher welches wann wo muss kann darf noch nur auch so des".split()),
    "fr": set("le la les l un une des de du d et ou à au aux en dans est sont qui que quoi quel quelle quels quelles combien pour par sur ce cette il elle on doit peut se sa son ses ne pas".split()),
    "it": set("il lo la i gli le l un uno una dei degli delle di del della e o a al ai in nel nella è sono che chi quale quali quanto quanti quanta per con su questo questa si deve può non".split()),
}
K1, B = 1.4, 0.75


def fold(text):
    text = unicodedata.normalize("NFKC", text).replace("’", "'").lower()
    return re.sub(r"(?<=\d)['’ .](?=\d{3}\b)", "", text)


def tokens(text, lang):
    out = []
    for w in re.findall(r"[a-zà-ÿß]+|\d+", fold(text)):
        if w in STOP.get(lang, ()) or (len(w) < 2 and not w.isdigit()):
            continue
        out.append(w)
        if len(w) > 6 and not w.isdigit():
            out.append(w[:5] + "~")
    return out


class Index:
    def __init__(self, lang, docs):
        self.lang, self.docs = lang, docs
        self.tf = [collections.Counter(tokens(d["search_text"], lang)) for d in docs]
        self.len = [sum(c.values()) for c in self.tf]
        self.avg = sum(self.len) / max(1, len(self.len))
        df = collections.Counter(t for c in self.tf for t in c)
        n = len(docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}
        self.post = collections.defaultdict(list)
        for i, c in enumerate(self.tf):
            for t in c:
                self.post[t].append(i)

    @classmethod
    def load(cls, lang, corpus=CORPUS):
        manifest = json.loads((corpus / "manifest.json").read_text())
        docs = []
        for sr, short in ACTS.items():
            path = corpus / f"{sr}.{lang}.json"
            if not path.exists():
                continue
            info = manifest.get(sr, {}).get("languages", {}).get(lang, {})
            for art_id, art in json.loads(path.read_text()).items():
                for i, para in enumerate(art["paragraphs"]):
                    name = NAMES.get(lang, NAMES["de"])[short]
                    docs.append({"id": f"{short}:{art_id}:{i}", "act": short, "sr": sr, "art_id": art_id,
                                 "article": art["heading"], "para_index": i, "text": para,
                                 "act_name": name, "url": info.get("url"), "consolidation": info.get("date"),
                                 "search_text": f"{name} {art['heading']} {para}"})
        return cls(lang, docs)

    def search(self, query, k=6):
        q = collections.Counter(tokens(query, self.lang))
        scores = collections.defaultdict(float)
        for t, qf in q.items():
            idf = self.idf.get(t)
            if idf is None:
                continue
            for i in self.post[t]:
                f = self.tf[i][t]
                scores[i] += idf * f * (K1 + 1) / (f + K1 * (1 - B + B * self.len[i] / self.avg))
        best = sorted(scores, key=scores.get, reverse=True)[:k]
        return [dict(self.docs[i], score=round(scores[i], 3)) for i in best]

    def article(self, act, art_id):
        """All paragraphs of one article, in order (empty when the act or article is unknown)."""
        return [dict(d, score=None) for d in self.docs if d["act"] == act and d["art_id"] == art_id]
