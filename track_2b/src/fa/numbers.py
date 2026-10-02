"""Numbers in German, French, Italian and Romansh text, written as digits or as words.

Used to check that a number in a generated answer is actually stated in the paragraph it cites.
"""
import re
import unicodedata

NUMBER_WORDS = {
    "de": {"ein": 1, "eine": 1, "einem": 1, "einer": 1, "einen": 1, "eines": 1, "zwei": 2, "drei": 3, "vier": 4,
           "fünf": 5, "sechs": 6, "sieben": 7, "acht": 8, "neun": 9, "zehn": 10, "elf": 11, "zwölf": 12,
           "dreier": 3, "zweier": 2, "dreizehn": 13, "zweitausend": 2000, "vierzehn": 14, "fünfzehn": 15, "sechzehn": 16, "siebzehn": 17, "achtzehn": 18,
           "zwanzig": 20, "fünfundzwanzig": 25, "zehntausend": 10000, "tausend": 1000, "million": 1e6, "millionen": 1e6, "milliarden": 1e9, "achtzehnten": 18, "dreissig": 30, "vierzig": 40, "fünfzig": 50, "sechzig": 60,
           "hundert": 100, "halb": 0.5, "hälfte": 0.5, "fünftel": 0.2, "fünfteln": 0.2, "dritteln": 1 / 3, "vierteln": 0.25, "drittel": 1 / 3, "viertel": 0.25, "zweidrittel": 2 / 3},
    "fr": {"un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6, "sept": 7, "huit": 8,
           "neuf": 9, "dix": 10, "onze": 11, "douze": 12, "treize": 13, "quatorze": 14, "quinze": 15,
           "seize": 16, "mille": 1000, "million": 1e6, "millions": 1e6, "milliards": 1e9, "dix-huitième": 18, "vingt": 20, "trente": 30, "quarante": 40,
           "cinquante": 50, "soixante": 60, "cent": 100, "moitié": 0.5, "cinquièmes": 0.2, "tiers": 1 / 3, "quarts": 0.25, "quart": 0.25},
    "it": {"un": 1, "uno": 1, "una": 1, "due": 2, "tre": 3, "quattro": 4, "cinque": 5, "sei": 6, "sette": 7,
           "otto": 8, "nove": 9, "dieci": 10, "undici": 11, "dodici": 12, "tredici": 13, "quattordici": 14,
           "quindici": 15, "sedici": 16, "diciotto": 18, "diciott": 18, "venti": 20, "venticinque": 25,
           "trent": 30, "quarant": 40, "cinquant": 50, "mille": 1000, "diecimila": 10000, "trecento": 300, "duecento": 200, "milione": 1e6, "milioni": 1e6, "miliardi": 1e9, "diciottesimo": 18, "diciottesimi": 18, "duemila": 2000, "tremila": 3000,
           "trenta": 30, "quaranta": 40, "cinquanta": 50, "sessanta": 60, "cento": 100, "metà": 0.5, "quinti": 0.2, "quarti": 0.25,
           "terzo": 1 / 3, "terzi": 2 / 3, "quarto": 0.25},
    "rm": {"in": 1, "ina": 1, "dus": 2, "duas": 2, "trais": 3, "quatter": 4, "tschintg": 5, "sis": 6, "set": 7,
           "otg": 8, "nov": 9, "diesch": 10, "endesch": 11, "dudesch": 12, "quindesch": 15, "ventg": 20,
           "trenta": 30, "tschient": 100, "mesadad": 0.5, "terz": 1 / 3, "quart": 0.25},
}


# hyphenated French numerals, which the word tokenizer keeps whole
COMPOUND = {"fr": {"dix-huitième": 18, "dix-sept": 17, "dix-huit": 18, "dix-neuf": 19, "vingt-cinq": 25, "soixante-dix": 70,
                   "quatre-vingts": 80, "quatre-vingt-dix": 90}}
MULTIPLIERS = {"hundert", "tausend", "cent", "mille", "cento", "million", "millionen", "milliarden", "millions",
               "milliards", "milione", "milioni", "miliardi"}
FRACTIONS = {"fünftel": 0.2, "fünfteln": 0.2, "dritteln": 1 / 3, "vierteln": 0.25, "cinquièmes": 0.2, "quinti": 0.2, "drittel": 1 / 3, "viertel": 0.25, "tiers": 1 / 3, "quart": 0.25, "quarts": 0.25, "terzi": 1 / 3,
             "quarti": 0.25, "terz": 1 / 3}


def norm(text):
    """Lower case, unify apostrophes, spaces and thousands separators, drop accents' combining marks."""
    text = unicodedata.normalize("NFKC", str(text)).replace("’", "'").replace(" ", " ").replace("\xa0", " ")
    text = re.sub(r"(?<=\d)['’ .](?=\d{3}\b)", "", text)          # 100 000 / 100'000 / 100.000 -> 100000
    return re.sub(r"\s+", " ", text).strip().lower()


def numbers_in(text, lang):
    """Every number stated in `text`, as digits or as a number word of `lang`."""
    t = norm(text)
    found = {float(x.replace(",", ".")) for x in re.findall(r"\d+(?:[.,]\d+)?", t)}
    words = NUMBER_WORDS.get(lang, {})
    previous = None
    for token in re.findall(r"\d+(?:[.,]\d+)?|[a-zà-ÿ]+(?:-[a-zà-ÿ]+)*", t):
        value = None
        if token[0].isdigit():
            value = float(token.replace(",", "."))
        elif token in COMPOUND.get(lang, {}):
            value = float(COMPOUND[lang][token])
        elif token in words:
            value = float(words[token])
            # "zwei Drittel", "deux tiers", "due terzi": a count before a fraction word multiplies it
            if token in FRACTIONS and previous is not None and previous >= 1:
                found.add(previous * FRACTIONS[token])
            # "deux mille", "zwei tausend": a count before a multiplier word multiplies it
            if token in MULTIPLIERS and previous is not None and previous >= 1:
                found.add(previous * words[token])
        if value is not None:
            found.add(value)
        previous = value
    return found
