# Prompting local judge models: what the research says, and prompt 0.3

Written 23-24 October 2026, during the judge smoke test (`README.md` in this folder). The
judges are mid-sized open models run through Ollama on the 5090 laptop: Gemma 4 26B
(a mixture of experts, about 4B active), Gemma 4 31B (dense) and Qwen 3.8 27B (dense).
Most of what is written about prompting is about frontier models. This file collects
what applies to models of this size, what we saw ourselves, and what prompt 0.3 changes
because of it.

Three questions were looked into:

1. How long should a thinking model be allowed to think? (We had set 8,192 tokens.)
2. Is `[[ ]]` a good way to mark the spot to judge, for models of this size?
3. What works for prompting models in the 20-30B range in general, and for judging?

## 1. How long to let them think

- **Qwen 3.8 27B.** The model card's "Best Practices" say to allow up to **262,144
  tokens** for the reasoning and 131,072 for the final answer, and recommend
  temperature 1.0, top_p 0.95, top_k 20 when thinking. The model has three levels of
  thinking effort: `low`, `medium`, `xhigh` (the card calls `xhigh` the default; Ollama's
  build reports `medium` as its default, from `/api/show`).
  ([Qwen/Qwen3.8-27B](https://huggingface.co/Qwen/Qwen3.8-27B))
- **Gemma 4.** Thinking is only on or off; Google offers no budget. The only lever is a
  "think less" line in the system prompt, which Google says cuts thinking by about 20%.
  ([Gemma 4 prompt formatting](https://ai.google.dev/gemma/docs/core/prompt-formatting-gemma4?hl=en))
- **Ollama** takes `think` as true/false or as a level the model names; numbers are not
  supported. The page doesn't say whether thinking counts toward `num_predict`; in our
  runs it does. ([Ollama thinking](https://docs.ollama.com/capabilities/thinking))

**What we saw.** Gemma 4 26B with thinking, prompt 0.2, 133 answers: most requests
thought for 300-1,600 tokens, but the open-ended "list every difference" request ran
into the 8,192 limit in **15 of 18** cases. It went through the minute line by line
("Wait, one more: …") until the limit cut it off. The ranking request did so 3 times in
19. So the length of thinking depends on how open the question is more than on the
model.

**What we set.** Gemma: 16,384 tokens. Qwen: 32,768 at `medium`. The context window
grows to hold the prompt plus that budget (Qwen does full attention on only 1 layer in
4, so a 64k window costs about 2 GB). An answer that hits the limit is marked invalid
and can be asked again with `--redo-invalid`. Temperature stays 0 for every model, so
the only difference from the no-thinking run is the thinking. That is against both
makers' advice of 1.0, and is said here so it isn't forgotten.

## 2. Marking the spot: `[[ ]]` or tags?

Nothing published tests a model *reading* a marked span. The closest work asks models to
*write* marked spans:

- A 2026 comparison of span-marking strategies (Qwen3-8B, Mistral-Small-24B,
  Llama-3.3-70B, GPT-5-mini; no Gemma) found **XML-like tags** "the most universal, having
  consistent performance across tasks". Asking for character positions did worst ("below
  24% for open LLMs"). ([Strategies for Span Labeling with LLMs](https://arxiv.org/html/2601.16946v1))
- Numbered inline tags (`<v0>…</v0>`) for translation errors "only provide a massive boost
  to reasoning models" and slightly hurt a non-reasoning one.
  ([Tagged Span Annotation](https://lacuna.tiptreesystems.com/work/tagged-span-annotation-for-detecting-translation-errors))
- Translation-quality judging (GEMBA-MQM and later work) marks error spans and asks for
  JSON. ([GEMBA-MQM](https://arxiv.org/pdf/2310.13988), [LLMs as Span Annotators](https://arxiv.org/html/2504.08697v1))
- Generic prompting guides recommend XML-style tags or quotes to set data apart from
  instructions. ([Portkey](https://portkey.ai/blog/delimiters-in-prompt-engineering/))

**Our reasoning (not tested by anyone else).** `[[ ]]` already means something in these
models' training text: a link in Wikipedia's markup (`[[Supreme Court]]`). An empty
`[[]]` has no meaning there at all. HTML's `<mark>` tag means exactly "highlighted text",
and these models have read a great deal of HTML. In our own answers, Gemma read an empty
`[[]]` as a pause or a gap (s30), and described a missing comma that sat inside the
brackets (s38).

## 3. Prompting models of this size, and judging with them

Few studies test the 20-30B range directly; most test 7-8B or frontier models. What
they agree on:

1. **Fewer instructions per request.** Compliance falls as instructions are added; if
   each is followed with probability *p*, all *n* are followed with about *p*ⁿ. Seen in
   every model tested, Gemma 2 included.
   ([Curse of Instructions](https://maxpool.dev/research-papers/curse_of_instructions_report.html),
   [Many instructions at once](https://arxiv.org/pdf/2608.12426))
   Bundling several tasks into one prompt hurt some model families badly. Gemma 3 4B
   "exhibited severe collapses" on fine-grained judgments while Qwen3 4B held up.
   ([Multi-task prompting](https://www.mdpi.com/2079-9292/14/21/4349))
2. **Strict output formats can cost reasoning, and field order matters.** JSON and other
   strict formats lowered reasoning scores, the stricter the worse; the order of the
   fields changed results. Simple classification was not hurt.
   ([Let Me Speak Freely?, EMNLP 2024](https://themoonlight.io/review/let-me-speak-freely-a-study-on-the-impact-of-format-restrictions-on-performance-of-large-language-models))
3. **Reason before the score; give a reference answer and a rubric (marking scheme) that
   spells out every level.** Prometheus, a 13B open judge, matched human judges about as
   well as GPT-4 did (0.897 against 0.882) when given a reference answer and such a
   rubric, writing its feedback before the score.
   ([Prometheus](https://arxiv.org/html/2310.08491v2))
4. **Worked examples bring scores that run high or low back in line, but don't fix the
   order cases are put in.** A few labelled examples "recovers much of the agreement lost
   to score scaling" for compact judges, without changing how they order cases.
   Practitioner advice: 2-5 examples across the scale, borderline ones mattering most.
   ([Compact judges](https://neurips.cc/virtual/2026/160516),
   [Small LMs as judges](https://neurips.cc/virtual/2026/161275))
5. **Order sways small judges, including the order of answer options.** Qwen2.5-7B
   changed about 1 verdict in 5 when the order was swapped
   ([llm-judge-bias](https://github.com/Subhajit077/llm-judge-bias)). Judges favour certain
   positions in a rubric's option list, and a few shuffles reduce it
   ([Position bias in rubric judging](https://arxiv.org/html/2602.02219v2)). Weaker models
   are more sensitive ([Systematic study](https://aclanthology.org/2025.ijcnlp-long.18.pdf)).
6. **Put the question after a long document.** Models use the start and end of a long
   input better than the middle.
   ([Lost in the Middle](https://publish.obsidian.md/subhaditya/KB/AI/Machine+Learning/Models/Lost+in+the+Middle+How+Language+Models+Use+Long+Contexts))

## What prompt 0.2 got wrong, by our own measures

From Claude's review of Gemma 4 26B's 276 answers (`claude-review/`, `README.md`):

- "Would a reader notice?" was answered "yes" 32 times in 40. It was asked with the
  reference in view, so the model could not pretend not to have it.
- Severity ran high: above Claude's in 18 cases, below in 1.
- Rank was the weakest request; the model ranked on punctuation and words away from the
  spot, which the 12 words shown either side invited.
- The misses lists were padded: 75 of 195 items mattered; several left out the case itself.
- The blind pick followed position in about 16 of 40 cases.
- Shown the rule's verdict, the model repeated it over identical texts (fixed in 0.2).

## Prompt 0.3

| change | reason |
|---|---|
| The spot in `<mark>…</mark>`; an empty side written `<mark>(nothing)</mark>` | §2 |
| The labelled request split three ways: **meaning** (5 fields), **stakes**, **cold read** | §3.1 |
| **Reason first** in every answer | §3.2, §3.3 |
| Severity scale with a worked example at each level, plus a rule for left-out words | §3.4; severity ran high, skips all came out 3-4 |
| A note on which African American English features carry meaning (habitual "be", present tense without -s) and which don't (a dropped "is"/"are") | the two zero-copula cases came out "changed" at line and minute |
| "Would a reader notice" as a **cold read**: only the engine's minute, nothing marked, "point out up to 3 places that look wrong" | it can't be answered with the reference in view |
| A `reference_doubt` field: does the reference itself look wrong here? | the review found likely reference errors (s05, s21, s30, s34) |
| Rank shows 3 words either side, not 12, and says to ignore everything outside `<mark>` | rank was the weakest request |
| Misses: at most 5, meaning changes only, worst first, with the severity examples | padding; with thinking on, the open-ended version ran past 8k tokens in 15 of 18 |
| The rule's "N of N others right" explained | unexplained jargon |
| "The reference is usually right, but people make mistakes too" instead of "treat the reference as what was said" | let it see reference errors |

**Not adopted:**
- Shuffling the order of the answer options (§3.5). It needs several runs per question,
  so we left it for later. The blind request already swaps the order of the two versions.
- Worked examples taken from the sample itself. They would leak answers, so the severity
  examples are invented sentences.
- The makers' temperature of 1.0 (see §1).

## How 0.3 is tested against 0.2

The same model and settings (Gemma 4 26B, thinking off) answer the same 40 cases with each
prompt. Two kinds of scoring:

1. **Automatic** (`tools/judge_compare.py`):
   - the controls;
   - agreement with Claude's own answers, written from the text before Claude saw any
     model's answers;
   - how far its severity is from Claude's;
   - whether a blind pick survives swapping the order;
   - whether a misses list includes the case itself;
   - time per request.
2. **Claude as a blind judge.** For each case, a Claude agent sees the texts and both
   versions' answers, labelled X and Y at random, without knowing which prompt produced
   which. It marks each answer right, partly or wrong, and says which set is better
   overall (`ab-review/`).

If 0.3 is better, the thinking runs (Gemma 4 26B, Gemma 4 31B, Qwen 3.8 27B) use it.

## Results (24 October 2026)

Gemma 4 26B, thinking off, the same 40 cases, prompt 0.2 against 0.3. 0.3 gave 396
answers, all valid, in 35 minutes; 0.2 gave 316 in 22.

**The blind review by Claude is a split decision.** Four Claude agents judged the two
answer sets as X and Y without knowing which was which (`ab-review/`, totals from
`tools/judge_ab.py`). Over whole cases it came out even: 0.2 better on 16, 0.3 on 16,
8 ties. Part by part (share right, counting partly as half):

| part | 0.2 | 0.3 | cases won, 0.2 / 0.3 |
|---|---|---|---|
| meaning, line | 0.76 | **0.94** | 1 / 11 |
| meaning, minute | 0.82 | **0.92** | 1 / 8 |
| meaning, whole | 0.88 | **0.94** | 0 / 6 |
| rank | 0.62 | **0.81** | 5 / 18 |
| rule | 0.94 | 0.96 | 0 / 2 |
| stakes | 0.89 | 0.91 | 3 / 4 |
| blind | **0.74** | 0.68 | 9 / 5 |
| noticeable | **0.72** | 0.57 | 15 / 8 |

Misses lists, summed over the 40 minutes:

| | real and matter | trivial | not real | important ones left out |
|---|---|---|---|---|
| 0.2 | 80 | 108 | 7 | 6 |
| 0.3 | 62 | 55 | 7 | 23 |

**The automatic scores** (`tools/judge_compare.py`, 36 real cases) lean the same way:

| | 0.2 | 0.3 |
|---|---|---|
| meaning matches Claude's (minute) | 25 | 28 |
| severity above Claude's, on average | 0.58 | 0.42 |
| "noticeable" matches Claude's | 16 | 23 |
| blind answer the same in both orders (of 40) | 24 | 28 |
| caught engine ranked last | 28 | 32 |
| misses list includes the case itself | 27 | 23 |
| controls | 12/12 | 12/12 |

The reference-doubt field said "no" on all four cases where Claude suspects the reference.

**What worked:**
- The core question, the meaning verdict, got clearly better at every context size.
- Ranking improved most, once only the words at the spot were shown.
- Severity came down a little, closer to Claude's.

**What didn't:**
- **The misses list's cap of 5 cost recall.** Padding halved, but 23 real meaning changes
  were left off, against 6.
- **The cold read** finds the spot in only 15 of 36 minutes. A minute of speech
  recognition output has plenty of other oddities, and with room for only 3 places the
  spot often isn't among them. Read as yes/no, the blind reviewers scored it below 0.2's
  "noticeable", while the automatic comparison with Claude's own answers scored it
  above. That is a sign the measure itself is shaky either way.
- **Blind did a little worse**, within the noise of 40 cases. The reviewers saw picks
  flip with the order on both sides.
- **"Reference looks wrong" never fired**, even on "performer basis" for "pro forma".

Several reviewers noted that many differences look like run-to-run noise: the same fault
turns up in one set on one case and in the other set on the next.

**Decision:** the thinking runs (Gemma 4 26B, Gemma 4 31B, Qwen 3.8 27B) use 0.3:
- it wins the questions that matter most, meaning and severity, and rank;
- 0.2's open-ended misses request can't be used with thinking on, since it ran past the
  token limit in 15 of 18 cases.

**For a prompt 0.4:**
- raise the misses cap to about 10, keeping "meaning changes only";
- ask the cold read for every place that looks wrong, or score it by whether a reader
  would stop at the spot rather than whether it is in the top 3;
- try 0.2's blind wording with `<mark>` alone, to see which change hurt;
- give the reference-doubt question an example, so the model knows what a reference
  error looks like.
