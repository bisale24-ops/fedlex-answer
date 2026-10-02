"""The assistant over HTTP: one page and one endpoint, standard library only (runs air-gapped).

    PYTHONPATH=src python3 -m fa.web          # http://127.0.0.1:8080

POST /api/ask {"question": "...", "lang": "de|fr|it"} -> the result of fa.answer.ask.
GET /healthz -> {"ok": true, "model": ..., "endpoint": ...}; the corpus is loaded at start-up.
"""
import http.server
import json
import os
import pathlib
import re
import sys

from . import answer

PAGE = pathlib.Path(__file__).with_name("static") / "index.html"
FR = re.compile(r"\b(le|la|les|du|des|quel|quelle|délai|combien|est|une)\b", re.I)
IT = re.compile(r"\b(il|lo|gli|della|quale|quanti|quanto|termine|entro|è|una|per)\b", re.I)


def guess_lang(text):
    fr, it = len(FR.findall(text)), len(IT.findall(text))
    if max(fr, it) < 2:
        return "de"
    return "fr" if fr >= it else "it"


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "fedlex-answer/0.1"

    def _send(self, status, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("content-type", ctype)
        self.send_header("content-length", str(len(data)))
        self.send_header("cache-control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
        elif path == "/healthz":
            self._send(200, {"ok": True, "model": answer.MODEL, "endpoint": answer.BASE,
                             "paragraphs": {lang: len(answer.index(lang).docs) for lang in ("de", "fr", "it")}})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):  # noqa: N802
        if self.path != "/api/ask":
            self._send(404, {"error": "not found"})
            return
        try:
            n = min(int(self.headers.get("content-length") or 0), 4096)
            body = json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            self._send(400, {"error": "send JSON: {\"question\": ...}"})
            return
        question = str(body.get("question", "")).strip()[:400]
        if not question:
            self._send(400, {"error": "Ask a question."})
            return
        lang = body.get("lang") if body.get("lang") in ("de", "fr", "it") else guess_lang(question)
        try:
            result = answer.ask(question, lang)
        except Exception as error:  # noqa: BLE001 - the model endpoint is the usual culprit
            self._send(502, {"error": f"The language model did not answer ({type(error).__name__})."})
            return
        result.pop("raw", None)
        self._send(200, result)

    def log_message(self, fmt, *args):
        sys.stdout.write("%s %s\n" % (self.address_string(), fmt % args))


def main():
    host, port = os.environ.get("HOST", "127.0.0.1"), int(os.environ.get("PORT", "8080"))
    for lang in ("de", "fr", "it"):
        answer.index(lang)
    print(f"http://{host}:{port}/  model={answer.MODEL} endpoint={answer.BASE}", flush=True)
    http.server.ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    main()
