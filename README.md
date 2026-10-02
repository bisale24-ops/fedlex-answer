# Fedlex Answer — Hack Apertus 2026, Track 2B

Ask what Swiss federal law says, in German, French or Italian, and get the answer with the paragraph it
comes from. Built on Apertus 1.5; runs on-premise or air-gapped.

Apertus alone answers 41% of 1,611 statute questions correctly and 52% confidently wrong
([Swiss Statute QA](https://huggingface.co/datasets/KHLab/swiss-statute-qa)). Fedlex Answer makes the model read
the law before it answers and checks that it did:

1. **Retrieve** the best paragraphs from the 16 federal acts in force (BM25, standard library, no embeddings service).
2. **Answer** from those paragraphs only: Apertus names the source paragraph, copies the words that decide the
   case, then answers, or says the acts do not contain it.
3. **Verify** in code: the quote must be verbatim in the cited paragraph and every number in the answer must be in
   the quote. Otherwise the answer is withheld and the user sees why.

| On Swiss Statute QA (1,611 prompts) | Correct | Wrong | Not answered |
|---|---|---|---|
| Apertus 70B, closed book | 41% | 52% | 7% |
| **Fedlex Answer with Apertus 70B** | **83%** | **6%** | 10% |
| Apertus 8B, closed book | 19% | 26% | 55% |
| **Fedlex Answer with Apertus 8B** | **76%** | **9%** | 16% |

- Demo video (1:47): https://youtu.be/CbTLmXqyZwQ
- Project root: [`track_2b/`](track_2b/) · report: [`track_2b/technical_report.md`](track_2b/technical_report.md)
- Run it: `cd track_2b && make run` → http://localhost:8080 (needs `LLM_API_KEY` for the Hack Apertus endpoint, or
  `LLM_BASE_URL` for your own Apertus server)
- Air-gapped: `make airgap` (vLLM serving Apertus 1.5 8B from `./weights`, internal network only)
- Re-check every published number without a model: `make eval`

Code: Apache-2.0. Statute text: Swiss federal enactments, not protected by copyright (Art. 5 URG).
