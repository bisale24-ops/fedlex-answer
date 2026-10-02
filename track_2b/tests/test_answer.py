"""Retrieval, parsing and the verifier, without a model: a fake transport plays the model."""
import unittest

from fa import answer, web
from fa.index import Index

DE = Index.load("de")
answer._INDEX["de"] = DE


def fake(reply, hint="ARTICLES: \nTERMS: "):
    calls = []

    def transport(body):
        calls.append(body)
        system = body["messages"][0]["content"]
        return hint if "ARTICLES" in system else reply
    transport.calls = calls
    return transport


class Retrieval(unittest.TestCase):
    def test_finds_notice_period_paragraph(self):
        ids = [h["id"] for h in DE.search("Kündigungsfrist im fünften Dienstjahr Arbeitsverhältnis", 6)]
        self.assertIn("OR:art_335_c:0", ids)

    def test_article_lookup(self):
        self.assertEqual([h["id"] for h in DE.article("BV", "art_139")][:1], ["BV:art_139:0"])
        self.assertEqual(DE.article("BV", "art_99999"), [])

    def test_article_refs(self):
        self.assertEqual(answer.article_refs("ARTICLES: BV 139, CO art. 271a"), [("BV", "art_139"), ("OR", "art_271_a")])
        self.assertEqual(answer.article_refs("ARTICLES: none"), [])


class Verifier(unittest.TestCase):
    PARA = ("1 Das Arbeitsverhältnis kann im ersten Dienstjahr mit einer Kündigungsfrist von einem Monat, im zweiten "
            "bis und mit dem neunten Dienstjahr mit einer Frist von zwei Monaten gekündigt werden.")

    def test_quote_must_be_copied(self):
        ok, why = answer.verify("zwei Monate", "mit einer Frist von drei Monaten", self.PARA, "de")
        self.assertFalse(ok)
        self.assertIn("quote", why)

    def test_number_must_be_in_quote(self):
        ok, _ = answer.verify("drei Monate", "mit einer Frist von zwei Monaten", self.PARA, "de")
        self.assertFalse(ok)

    def test_supported_answer_passes(self):
        self.assertTrue(answer.verify("zwei Monate", "mit einer Frist von zwei Monaten", self.PARA, "de")[0])

    def test_share_written_as_percent(self):
        self.assertTrue(answer.verify("50 %", "höchstens die Hälfte der Ausgaben", "4 Die Leistungen betragen höchstens die Hälfte der Ausgaben.", "de")[0])

    def test_paragraph_number_is_not_part_of_the_text(self):
        self.assertEqual(answer.body("4 5 Prozent des Ertrags"), "5 Prozent des Ertrags")


class Ask(unittest.TestCase):
    Q = "Welche Kündigungsfrist gilt im fünften Dienstjahr eines Arbeitsverhältnisses?"

    def test_answered_with_citation(self):
        hits = DE.search(self.Q, answer.K)
        n = [h["id"] for h in hits].index("OR:art_335_c:0") + 1
        r = answer.ask(self.Q, "de", transport=fake(f"SOURCE: P{n}\nQUOTE: mit einer Frist von zwei Monaten\nANSWER: zwei Monate"))
        self.assertEqual(r["status"], "answered")
        self.assertEqual(r["source"]["id"], "OR:art_335_c:0")

    def test_unsupported_number_is_withheld(self):
        hits = DE.search(self.Q, answer.K)
        n = [h["id"] for h in hits].index("OR:art_335_c:0") + 1
        r = answer.ask(self.Q, "de", transport=fake(f"SOURCE: P{n}\nQUOTE: mit einer Frist von zwei Monaten\nANSWER: vier Monate"))
        self.assertEqual(r["status"], "withheld")
        self.assertIsNone(r["answer"])

    def test_not_found_tries_a_second_pass_then_says_so(self):
        t = fake("NOT_FOUND", hint="ARTICLES: BV 128\nTERMS: Steuerfuss Gemeinde")
        r = answer.ask("Wie hoch ist der Steuerfuss der Stadt Zürich?", "de", transport=t)
        self.assertEqual(r["status"], "not_found")
        self.assertEqual(len(t.calls), 3)          # answer, hint, answer again over the hinted article
        self.assertIn("BV:art_128:0", r["retrieved"])

    def test_source_outside_retrieved_set_is_rejected(self):
        r = answer.ask(self.Q, "de", transport=fake("SOURCE: P99\nQUOTE: x\nANSWER: zwei Monate"))
        self.assertNotEqual(r["status"], "answered")


class Parse(unittest.TestCase):
    def test_labelled(self):
        self.assertEqual(answer.parse("SOURCE: P2\nQUOTE: entro 30 giorni\nANSWER: 30 giorni", 8),
                         ("30 giorni", 2, "entro 30 giorni"))

    def test_bare_lines_are_read_by_position(self):
        self.assertEqual(answer.parse('P3\n"almeno il 17 per cento"\n17 per cento', 8),
                         ("17 per cento", 3, "almeno il 17 per cento"))
        self.assertEqual(answer.parse("P1\nQUOTE: 8,5 per cento\nANSWER: 8,5 per cento", 8),
                         ("8,5 per cento", 1, "8,5 per cento"))

    def test_not_found_and_out_of_range(self):
        self.assertEqual(answer.parse("NOT_FOUND", 8), (None, None, None))
        self.assertIsNone(answer.parse("SOURCE: P9\nQUOTE: x\nANSWER: y", 8)[1])


class Language(unittest.TestCase):
    def test_guess(self):
        self.assertEqual(web.guess_lang("Dans quel délai faut-il former opposition?"), "fr")
        self.assertEqual(web.guess_lang("Entro quale termine si può ricorrere contro la decisione?"), "it")
        self.assertEqual(web.guess_lang("Wie lange dauert die Probezeit?"), "de")


if __name__ == "__main__":
    unittest.main()
