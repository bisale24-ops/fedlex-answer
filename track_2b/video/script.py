"""Demo video for Fedlex Answer (Hack Apertus 2026, Track 2B). Under two minutes, no presenter.

    ~/.venvs/video/bin/python ~/Desktop/KHLab/hack-nation/kit/video/render.py video/script.py --length-only
    ~/.venvs/video/bin/python ~/Desktop/KHLab/hack-nation/kit/video/render.py video/script.py --out video/demo.mp4 --max-seconds 118

Clips under video/clips/ are real recordings of the running app (video/record.py).
"""

VOICE = "en-US-AndrewNeural"

SCENES = [
    ("card:problem",
     "Ask Apertus seventy B what Swiss federal law says, and it gets forty one percent of statute "
     "questions right, and fifty two percent confidently wrong. On rules amended since twenty twenty one, "
     "it states the old value more often than the current one."),
    ("card:how",
     "Fedlex Answer makes it read the law first. It retrieves paragraphs from sixteen federal acts in force. "
     "Apertus names its source and copies the words that decide the case. Then code checks the quote is "
     "really in the paragraph, and every number in the answer is in the quote. If not, no answer."),
    ("clip:q1",
     "German. The notice period in the fifth year of service. Two months, from the Code of Obligations, "
     "with the deciding words highlighted and a link to Fedlex."),
    ("clip:q2",
     "French. The deadline to object to a payment order. Ten days from notification, quoted from the "
     "federal act on debt enforcement and bankruptcy."),
    ("clip:q3",
     "Italian. How long a tenant has to contest a lease termination. Thirty days from receipt, "
     "cited to the paragraph of the Code of Obligations."),
    ("clip:q4",
     "And the tax rate of the city of Zurich, which no federal act states. It says so, "
     "instead of inventing a number."),
    ("card:results",
     "On all sixteen hundred and eleven questions of our Swiss Statute Q A dataset, Apertus seventy B goes "
     "from forty one percent correct to eighty three, and from fifty two percent wrong to six. "
     "The eight B model, small enough for one G P U, goes from nineteen percent to seventy six. "
     "On out of scope questions, it declined forty of forty five."),
    ("card:deploy",
     "It is one standard library Python container that talks to one Apertus endpoint. Run it on premise, "
     "or air gapped next to v L L M. Every number re-checks with make eval, offline."),
]

CARDS = {
    "problem": """<h1>Apertus alone, on Swiss federal law</h1>
    <p class=sub>Swiss Statute QA · 1,611 questions from 16 acts · de / fr / it</p>
    <table>
      <tr><th>Apertus 1.5 70B, closed book</th><th></th></tr>
      <tr><td>Correct</td><td class=big>41%</td></tr>
      <tr><td>Confidently wrong</td><td class="big no">52%</td></tr>
      <tr><td>Amended rules: states the old value / the current one</td><td class=big>39 / 15</td></tr>
    </table>""",
    "how": """<h1>Read, quote, verify</h1>
    <p class=sub>Apertus answers only from the statute, and code checks that it did.</p>
    <table>
      <tr><td><b>1 Retrieve</b></td><td>BM25 over every paragraph of 16 federal acts in force (Fedlex)</td></tr>
      <tr><td><b>2 Answer</b></td><td>Apertus writes SOURCE, then a verbatim QUOTE, then the ANSWER — or NOT_FOUND</td></tr>
      <tr><td><b>3 Verify</b></td><td>Quote must be in the cited paragraph; every number in the answer must be in the quote</td></tr>
      <tr><td><b>4 Second pass</b></td><td>Nothing found? Apertus names the article; that article is read and verified</td></tr>
    </table>""",
    "results": """<h1>Same questions, same model</h1>
    <p class=sub>1,611 prompts, graded by the Apertus 70B judge of Swiss Statute QA</p>
    <table>
      <tr><th>Apertus 1.5</th><th>Correct</th><th>Wrong</th><th>Not answered</th></tr>
      <tr><td>70B closed book</td><td>41.0%</td><td class=no>52.3%</td><td>6.8%</td></tr>
      <tr><td><b>70B + Fedlex Answer</b></td><td class=ok>83.5%</td><td class=ok>6.3%</td><td>10.2%</td></tr>
      <tr><td>8B closed book</td><td>18.7%</td><td class=no>26.0%</td><td>55.3%</td></tr>
      <tr><td><b>8B + Fedlex Answer</b></td><td class=ok>75.6%</td><td class=ok>8.8%</td><td>15.6%</td></tr>
    </table>
    <p class=foot>70B on 45 out-of-scope prompts (cantonal law, ordinances): closed book gave a figure 27 / 45 times;
    Fedlex Answer declined 40 / 45. Median latency 1.5 s.</p>""",
    "deploy": """<h1>On-premise or air-gapped</h1>
    <p class=sub>Python standard library · corpus and index inside the image · one OpenAI-compatible endpoint</p>
    <pre>make run      # app on :8080, any Apertus endpoint (LLM_BASE_URL)
make airgap   # app + vLLM with local Apertus weights, internal network only
make eval     # re-check every published number, no network, no key</pre>
    <p class=foot>github.com/bisale24-ops/fedlex-answer · KHLab · Hack Apertus 2026, Track 2B</p>""",
}

CLIPS = {
    "q1": ("clips/q1.webm", 2.5),
    "q2": ("clips/q2.webm", 2.5),
    "q3": ("clips/q3.webm", 3.5),
    "q4": ("clips/q4.webm", 3.5),
}
