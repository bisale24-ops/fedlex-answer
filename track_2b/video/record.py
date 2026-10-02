"""Record the demo clips: the real page, real questions, real answers from the running server.

    PORT=8091 ~/.venvs/video/bin/python video/record.py     # writes video/clips/q*.webm

The server must be running (make run, or PYTHONPATH=src python3 -m fa.web). Each clip types one
question at reading speed, waits for the answer, and holds it on screen.
"""
import os
import pathlib
import shutil

from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).parent
OUT = HERE / "clips"
URL = f"http://127.0.0.1:{os.environ.get('PORT', '8091')}/"
QUESTIONS = [
    ("q1", "Welche Kündigungsfrist gilt im fünften Dienstjahr, wenn nichts anderes vereinbart ist?", "de"),
    ("q2", "Dans quel délai faut-il former opposition à un commandement de payer?", "fr"),
    ("q3", "Entro quanti giorni si può impugnare una disdetta del contratto di locazione?", "it"),
    ("q4", "Wie hoch ist der Steuerfuss der Stadt Zürich?", "de"),
]


def main():
    OUT.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for name, question, lang in QUESTIONS:
            tmp = OUT / f"_{name}"
            shutil.rmtree(tmp, ignore_errors=True)
            ctx = browser.new_context(viewport={"width": 1280, "height": 720}, device_scale_factor=1,
                                      record_video_dir=str(tmp), record_video_size={"width": 1280, "height": 720},
                                      color_scheme="light")
            page = ctx.new_page()
            page.goto(URL, wait_until="networkidle")
            page.wait_for_timeout(800)
            page.select_option("#lang", lang)
            page.click("#q")
            page.type("#q", question, delay=28)
            page.wait_for_timeout(400)
            page.click("#go")
            page.wait_for_selector("article.card", timeout=90000)
            page.wait_for_timeout(600)
            page.evaluate("document.querySelector('article.card').scrollIntoView({block:'center', behavior:'smooth'})")
            page.wait_for_timeout(5200)
            video = page.video
            ctx.close()
            src = pathlib.Path(video.path())
            dst = OUT / f"{name}.webm"
            src.replace(dst)
            shutil.rmtree(tmp, ignore_errors=True)
            print(name, dst.stat().st_size, flush=True)
        browser.close()


if __name__ == "__main__":
    main()
