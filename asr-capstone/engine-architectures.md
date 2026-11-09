# How the seven engines turn speech into text

1 November 2026

## Why this note exists

My hypothesis for the midterm paper is about context. Some transcribers, human or
machine, use the words around an unclear stretch to settle what was said. Others stick
to the utterance as spoken, either because the speech is ambiguous or because they
follow a conservative, verbatim habit. I expect engines that lean on a large internal
language model to show more "semantic awareness", and engines without one to follow
the audio more literally. The early data partly fits. When Parakeet's word differs
from the reference, the LLM judge calls it "garbled" 31-49% of the time, against
9-22% for Qwen3. But Whisper keeps only about 6% of speakers' restarts and rewrites
African American English grammar most often, while Qwen3-ASR keeps about 70% of
restarts. So two things are probably mixed together: (1) how much the design leans
on a language model, and (2) what transcript style the engine learned from its
training data, verbatim or tidied. This note sets out what is documented about each
engine on both points, so the two can be kept apart.

Every fact below was checked against the model card, the official paper or report,
or the checkpoint files themselves, in October-November 2026. Where a maker does not
say something, the note says "not stated".

## The seven at a glance

"Text side" is the part of the model that writes words. Sizes marked * are my own
count from the checkpoint files this project downloaded (see "How the sizes were
counted" at the end).

| Engine | Maker | Size | Decoder type | Text side | Training transcript style | Prompt or context used here |
|---|---|---|---|---|---|---|
| Whisper large-v3 | OpenAI | 1.55B | Attention encoder-decoder | Own decoder, 32 layers, about 0.9B* (trained only on transcripts) | Mixed: human web transcripts kept "raw", machine-made ones filtered out; plus 4M hours of Whisper large-v2 pseudo-labels. Filler policy not stated | None. No initial prompt, `condition_on_previous_text` off |
| Canary-1b-v2 | NVIDIA | 0.98B | Attention encoder-decoder | Own decoder, 8 layers, 151M* | Mixed: mostly Whisper large-v3 pseudo-labels (Granary) plus human-labelled sets; all punctuated and cased. Filler policy not stated | Task tokens only: English, punctuation on |
| Parakeet TDT 0.6B v3 | NVIDIA | 0.6B | Transducer (TDT) | Prediction network: 2-layer LSTM, 640 wide, 12M* (joint network 5M*) | Same mix as Canary, then fine-tuned on 7,500 h of human transcripts. Filler policy not stated | None (no prompt feature) |
| Qwen3-ASR 1.7B | Alibaba | 2.0B* | Audio encoder + text LLM | Qwen3-1.7B (1.72B*) | Not stated. 40M hours of pseudo-labels, labelling model not named | None. Language only; a context prompt exists but was not used |
| Voxtral Mini 3B | Mistral | 4.7B | Audio encoder (from Whisper large-v3) + text LLM | Ministral 3B, 3.6B decoder | Not stated. Pseudo-labels from an unnamed ASR model where no transcript existed | "Transcribe mode" token and language only; no text prompt |
| Granite Speech 4.1 2B | IBM | 2.3B* | CTC-trained encoder + text LLM | granite-4.0-1b-base, about 1.6B, adapted with LoRA | Not stated. Sources mix audiobooks, phone conversations, meetings and earnings calls | IBM's prompt "transcribe the speech with proper punctuation and capitalization." plus IBM's system prompt; no keywords |
| Granite Speech 4.1 2B Plus | IBM | 2.1B* | Same as Granite base | Same LLM as base | Same data as base; output has no punctuation or capitals by design | IBM's timestamp prompt plus system prompt; no keywords, no previous text |

## The four kinds of decoder, in one paragraph each

**Attention encoder-decoder.** The encoder turns the audio into a sequence of
features. A separate text decoder then writes the transcript one token at a time.
At each step it looks back at the whole audio and at every word it has written so
far. Because it always predicts the next word from the previous words, it is a
language model conditioned on the audio. The Whisper paper says this directly: "our
decoder is an audio-conditional language model"
([Radford et al. 2022, §2.3](https://cdn.openai.com/papers/whisper.pdf)).

**Transducer (RNN-T, TDT).** A transducer walks through the audio frame by frame. At
each frame it either writes a token or writes "blank" and moves on. A small
"prediction network" remembers the tokens written so far, and a "joint network"
combines it with the audio at that frame. A TDT (token-and-duration transducer) also
predicts how many frames each token covers, so it can skip frames and run faster
([Xu et al. 2023](https://arxiv.org/abs/2304.06795)).

**CTC.** A CTC (connectionist temporal classification) model labels each audio frame
independently and then collapses the labels into text. It does not condition on the
words it has already written. None of the seven engines writes its final transcript
with CTC, but Granite's audio encoder is trained with it.

**Audio encoder + text LLM** (often called a speech LLM). An audio encoder turns the
sound into features, a small adapter squeezes them into the LLM's input space, and a
pretrained text LLM writes the transcript as if continuing a chat. The text side is
not learned from transcripts alone. It arrives already trained on a very large amount
of ordinary text.

## The engines

### Whisper large-v3 (OpenAI)

**Design.** A Transformer encoder-decoder ("sequence-to-sequence") model of 1.55B
parameters ([model card](https://huggingface.co/openai/whisper-large-v3)). "The
encoder and decoder have the same width and number of transformer blocks"
([Radford et al. 2022, §2.2](https://cdn.openai.com/papers/whisper.pdf)), 32 each for
the large model. OpenAI do not publish the decoder's size on its own. Voxtral reuses
Whisper large-v3's encoder and Mistral list it at 640M
([Voxtral paper, Table 1](https://arxiv.org/abs/2507.13264)). That leaves roughly
0.9B for Whisper's decoder. This is my subtraction, not a published figure.

The paper ties the decoder directly to my hypothesis. It is trained "to condition on
the history of text of the transcript in the hope that it will learn to use
longer-range text context to resolve ambiguous audio"
([§2.3](https://cdn.openai.com/papers/whisper.pdf)). The authors also "suspect that
Whisper's robustness is partially due to its strong decoder, which is an audio
conditional language model" (§6).

**Training data and style.** large-v3 was "trained on 1 million hours of weakly
labeled audio and 4 million hours of pseudo-labeled audio collected using Whisper
large-v2" ([model card](https://huggingface.co/openai/whisper-large-v3)). So most of
its training text was written by its own predecessor. The original data came from
audio "paired with transcripts on the Internet". OpenAI "train Whisper models to
predict the raw text of transcripts without any significant standardization"
([§2.1](https://cdn.openai.com/papers/whisper.pdf)). They removed transcripts that
looked machine-made, "to avoid learning 'transcript-ese'". An all-uppercase or
all-lowercase transcript "is very unlikely to be human generated" (§2.1). The paper
never says whether the human web transcripts kept fillers and restarts. My reading,
not OpenAI's claim: web captions are mostly written to be read, so they are likely
to be tidied.

**Disfluencies and hallucination.** When OpenAI score Whisper, their text normaliser
deletes "hmm, mm, mhm, mmm, uh, um" before comparing
([Appendix C](https://cdn.openai.com/papers/whisper.pdf)). So the benchmark gives no
reward for keeping fillers. OpenAI's prompting guide shows a transcript with no
fillers by default; a run prompted with a filler-heavy example came back with "Um"
and "uh" in it ([OpenAI cookbook](https://developers.openai.com/cookbook/examples/whisper_prompting_guide)).
The guide says Whisper "follows the style of the prompt, rather than any instructions
contained within". CrisperWhisper had to fine-tune Whisper "to produce more verbatim
speech transcriptions" ([Wagner et al. 2024](https://arxiv.org/abs/2408.16589)), which
implies the base model is not verbatim. On hallucination, the paper lists "getting
stuck in repeat loops, not transcribing the first or last few words of an audio
segment, or complete hallucination where the model will output a transcript entirely
unrelated to the actual audio" (§6). The model card warns that "the predictions may
include texts that are not actually spoken in the audio input (i.e. hallucination)".
Whisper was trained on audio with no speech and has a `<|nospeech|>` token (§2.1,
§2.3).

**Context features, and what we used.** Whisper can take a text prompt and the
previous segment's text (paper Figure 1; the cookbook above; only "the final 224
tokens" count). This project used neither: no initial prompt and
`condition_on_previous_text=False`, run through faster-whisper with beam size 5 and
voice-activity filtering off (`pipeline/config/default.yaml`). Whisper decodes in
30-second windows, so it sees the least surrounding audio of the seven.

### Canary-1b-v2 (NVIDIA)

**Design.** "A FastConformer Encoder and a Transformer Decoder", 32 encoder layers and
8 decoder layers, "totaling 978 million parameters"
([model card](https://huggingface.co/nvidia/canary-1b-v2)). By my count the decoder
holds 151M of those, about a sixth of Whisper's decoder. It is an attention
encoder-decoder like Whisper, but with a much smaller text side and a much bigger
encoder.

**Training data and style.** About 1.7M hours in total, of which 660,000 hours are
speech recognition ([model card](https://huggingface.co/nvidia/canary-1b-v2)). Most
of it is NVIDIA's Granary set plus 227,000 hours of "high-quality human-labeled data
from NeMo ASR Set 3.0" (AMI, FLEURS, Common Voice, Multilingual LibriSpeech and
others) ([Sekoyan et al. 2025, §3.1](https://arxiv.org/abs/2509.14128)). Labelling is
"Hybrid: Synthetic, Human", and "All transcripts include punctuation and
capitalization" (model card).

The important fact is where Granary's text came from. The Granary authors "selected
Whisper-large-v3 for pseudo-labeling", run through faster-whisper with beam size 5
and Silero voice-activity detection. Punctuation and capitals were then restored by
Qwen2.5-7B-Instruct. If the restored text differed from Whisper's by more than 5% of
characters, "the original pseudo-labels were retained"
([Koluguri et al. 2025, §3.1](https://arxiv.org/abs/2505.13404)). So a large share of
Canary's (and Parakeet's) training text was written by Whisper large-v3, the same
model in this study. Neither paper says anything about fillers, restarts or verbatim
style.

**Disfluencies and hallucination.** NVIDIA added "36,000 hours of non-speech audio"
paired "with empty string targets to teach the model when not to generate
transcriptions", aimed partly at errors "inherited from Whisper-based
pseudo-labeling" ([Sekoyan et al. 2025, §3.2](https://arxiv.org/html/2509.14128)).
Granary also dropped training samples showing Whisper's habitual hallucinated phrases,
such as "Thank you very much" ([Koluguri et al. 2025, §3.1.4](https://arxiv.org/abs/2505.13404)).
The card reports a hallucination figure of 134.7 characters per minute on 48 hours of
noise. It also says the model is "Not recommended for word-for-word/incomplete
sentences as accuracy varies based on the context of input text"
([model card](https://huggingface.co/nvidia/canary-1b-v2)). The same sentence appears
on Parakeet's card, so it may be boilerplate.

**Context features, and what we used.** No free-text prompt. The decoder takes task
tokens for source language, target language and punctuation. This project set
English and `punctuation=True`, in 40-second chunks (`canary_engine.py`).

### Parakeet TDT 0.6B v3 (NVIDIA)

**Design.** "FastConformer encoder architecture" with a TDT decoder, 600 million
parameters ([model card](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3)). The
encoder has 24 layers ([Sekoyan et al. 2025, §4.2](https://arxiv.org/html/2509.14128)).
The checkpoint's own configuration gives the prediction network as two layers, 640
wide ([config.json](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3)), and the
transformers code calls it an "LSTM-based prediction network". By my count the
prediction network is 12M parameters and the joint network 5M. Roughly 97% of the
model is encoder. This is the smallest text side in the study by far.

**Training data and style.** Stage 1 used 10,000 hours of human-transcribed NeMo ASR
Set 3.0 (including LibriSpeech, Fisher, VCTK, Europarl-ASR, Multilingual LibriSpeech,
Common Voice and AMI) and 660,000 hours of Granary pseudo-labels. Stage 2 fine-tuned
on "approximately 7,500 hours of high-quality, human-transcribed data"
([model card](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3)). "All
transcriptions preserve punctuation and capitalization." As with Canary, the bulk
of the text was Whisper large-v3's output (see Canary above). Whether fillers and
restarts were kept: not stated.

**Disfluencies and hallucination.** The card does not use the word "hallucination".
It says "Transcripts may be not 100% accurate" and repeats the "Not recommended for
word-for-word/incomplete sentences" line. This project's own finding is a different
failure: the decoder stops writing after a full stop and stays silent until reset
(`findings/parakeet-stall/`).

**Context features, and what we used.** No prompt or context input. 300-second
chunks with a re-read of every gap of 4 seconds or more (`parakeet.yaml`).

### Qwen3-ASR 1.7B (Alibaba)

**Design.** "Qwen3-ASR-1.7B is built with Qwen3-1.7B, a projector, and an AuT encoder
with 300M parameters" ([Qwen3-ASR Technical Report, §2.1](https://arxiv.org/abs/2601.21337)).
AuT is itself "an attention-encoder-decoder (AED) based ASR model", whose encoder is
kept. The models are initialised from Qwen3-Omni and "trained with 3 trillion tokens"
of audio, vision and text (§2.2). By my count the LLM part holds 1.72B parameters and
the whole checkpoint 2.0B.

**Training data and style.** The encoder was pretrained on "approximately 40 million
hours of pseudo-labeled ASR data, where the majority is in Chinese and English"
(§2.2). The report does not say which model made the pseudo-labels or what the
sources were. Fine-tuning used "a substantially smaller set of multilingual data that
is disjoint from the pretraining corpus", plus "non-speech data, streaming-enhancement
data and context biasing data". A last reinforcement-learning stage used about 50,000
utterances. The authors say it "plays an essential role in models' noise robustness,
transcription stability and ability to analyze difficult cases" (§2.2). Transcript
style (verbatim, fillers, punctuation rules): not stated.

**Disfluencies and hallucination.** The word "hallucination" does not appear in the
report. Its internal robustness tests include "nonfluent and tongue-twister-like
repetitive speech" (§4.1). That suggests Alibaba wanted repetitions transcribed, but
it is my inference, not a statement about training targets. The fine-tuning made it
"an ASR-only model that does not follow natural-language instructions in the prompt",
to avoid instruction-following failures (§2.2). It has a defined output for "no speech
detected" (§2.2).

**Context features, and what we used.** It "learns to utilize the context tokens
inside the system prompt as background knowledge" (§2.2). The transformers card shows
free-form context passed as a `prompt`, such as `"Vocabulary: Quilter, apostle,
gospel."` ([Qwen3-ASR-1.7B-hf card](https://huggingface.co/Qwen/Qwen3-ASR-1.7B-hf)).
This project passed only the language, no context, in 280-second chunks
(`qwen3_engine.py`).

### Voxtral Mini 3B 2507 (Mistral)

**Design.** "The audio encoder is based on Whisper large-v3" (640M), an adapter
downsamples the audio "by a factor of 4x" (25M), and "Voxtral Mini is built on top of
Ministral 3B", a 3.6B decoder, 4.7B in all
([Voxtral paper, §2, Table 1](https://arxiv.org/abs/2507.13264)). The card describes
it as "an enhancement of Ministral 3B"
([model card](https://huggingface.co/mistralai/Voxtral-Mini-3B-2507)). This is the
largest text side in the study, and it shares its ears with Whisper.

**Training data and style.** Audio with transcripts was cut into short segments. "If
transcripts are unavailable, we pseudo-label the audio with an ASR model"
([§3.1](https://arxiv.org/abs/2507.13264)), which is not named. Pretraining split
evenly between two patterns: "audio-to-text repetition", which "mimics speech
recognition", and "cross-modal continuation", where the model continues speech with
the text that follows (§3.1). Hours, sources and transcript style: not stated.

**Disfluencies and hallucination.** Not addressed for transcription. The paper only
says an online-DPO chat variant has "fewer hallucinations", from informal checks
(§5.4).

**Context features, and what we used.** Transcription uses "a dedicated 'transcribe
mode', signaled via a new special token", "eliminating the need for a text prompt"
([§3.2](https://arxiv.org/abs/2507.13264)). "System prompts are not yet supported"
([model card](https://huggingface.co/mistralai/Voxtral-Mini-3B-2507)). This project
used transcribe mode with the language set, in 280-second chunks (`voxtral_engine.py`).

### Granite Speech 4.1 2B (IBM)

**Design.** The speech encoder is "16 conformer blocks trained with Connectionist
Temporal Classification (CTC)". A "2-layer window query transformer (q-former)"
projects it into the LLM, an "intermediate checkpoint of granite-4.0-1b-base"
([model card](https://huggingface.co/ibm-granite/granite-speech-4.1-2b)). That base
model is a "decoder-only dense transformer", 1.6B parameters, "trained from scratch on
approximately 15 trillion tokens" ([granite-4.0-1b-base card](https://huggingface.co/ibm-granite/granite-4.0-1b-base)).
The projector and "LLM LoRA adapters" were trained jointly. LoRA trains small added
layers and leaves the LLM "largely intact", in the words of the earlier Granite
Speech paper ([Saon et al. 2025](https://arxiv.org/abs/2505.08699)).

**Training data and style.** "174,000 hours of audio from public corpora". English
sources include Multilingual LibriSpeech (48,000 h) and LibriHeavy (46,000 h) of
audiobooks, YODAS (10,000 h), 24,000 h of VoxPopuli from NVIDIA's Granary, Fisher
(2,000 h), Switchboard (260 h), CallHome (18 h), AMI (100 h) and **Earnings-22
(105 h)** ([model card](https://huggingface.co/ibm-granite/granite-speech-4.1-2b)).
So part of its text again descends from Whisper large-v3 (the Granary share). The
phone-call corpora are conversational and were originally transcribed with fillers,
but IBM do not say how they prepared the targets. Punctuation and capitals are
switched on by the prompt; how the punctuated targets were made is not stated.

**Disfluencies and hallucination.** The card warns that small models "may exhibit
increased susceptibility to hallucination in generation scenarios due to their
reduced sizes". Nothing on fillers or restarts.

**Context features, and what we used.** Keyword biasing through the prompt:
"transcribe the speech to text. Keywords: <kw1>, <kw2>, ..." (model card). This
project used IBM's punctuation prompt and IBM's system prompt, no keywords, in
60-second chunks (`granite_engine.py`).

### Granite Speech 4.1 2B Plus (IBM)

**Design.** It "shares the same architecture as the Granite-Speech-4.1-2B model" and
"was trained on the same datasets"
([model card](https://huggingface.co/ibm-granite/granite-speech-4.1-2b-plus)). It adds
speaker labels and word timings, each chosen by the wording of the prompt.

**Training data and style.** Timestamp training data came from LibriSpeech, MLS,
Common Voice and YODAS, aligned with the Montreal Forced Aligner and checked against
CTC alignments (model card). "Unlike the base mode, the plus model doesn't provide
punctuation and capitalization." Filler policy: not stated.

**Disfluencies and hallucination.** The card says repetition loops happen "mostly on
long audio" and recommends `repetition_penalty=2.0` (model card). This project did not
use a repetition penalty; it split looping chunks instead.

**A version warning.** IBM "updated the model weights and configuration" on 19 October
2026 (v2610), saying the new model "is more accurate, especially for keyword biasing
and for word-level timestamps on long samples" (model card). This project downloaded
the model on 24 September 2026, so every result here is from the original April
release (v2604).

**Context features, and what we used.** Keywords in the prompt, and a `prefix_text`
field to pass the previous transcription (model card). This project used IBM's
timestamp prompt and system prompt only, with no keywords and no previous text, in
120-second chunks (`granite_plus_engine.py`).

## What this predicts for our data

Two facts change how the hypothesis should be framed.

First, "has an LLM" and "has a big internal language model" are not the same thing.
The text sides range from 12M (Parakeet) through 151M (Canary) and about 0.9B
(Whisper) to 1.6-3.6B (the four speech LLMs). Whisper's decoder is half the size of
Qwen3's LLM. The real design split is between decoders that learned language only
from transcripts (Whisper, Canary, Parakeet) and LLMs that learned it from trillions
of tokens of ordinary text first (Qwen3, Voxtral, both Granites).

Second, the internal language model is where training style lives. Meng et al. put it
plainly: "an E2E model implicitly learns an internal LM that characterizes the
training data" ([Meng et al. 2021](https://arxiv.org/abs/2011.01991)). So a big
internal language model trained on tidied transcripts should tidy. A big one trained
on verbatim transcripts should keep the mess. Size says how strongly the model's
expectations can override the audio. Training style says which way they push.

A third, practical fact: the engines do not see the same amount of context. Whisper
decodes 30-second windows with no previous text. Canary sees 40 seconds, Granite 60,
Granite Plus 120, Qwen3 and Voxtral 280, Parakeet 300. An engine can only use
context it is given.

Because the makers do not state filler policy for any of the seven, "training style"
below is inferred from the data sources, not documented.

**(a) Garbled vs fluent differences.** *Design predicts:* Parakeet garbles most. Its
prediction network is tiny, and an earlier study found a transducer's prediction
network "does not function as the LM in classical ASR"; it mainly "helps the model
align to the input audio" ([Ghodsi et al. 2020](https://research.google/pubs/rnn-transducer-with-stateless-prediction-network/)).
Canary next, then Whisper, then the four speech LLMs, which should almost never be
garbled. *Training style:* little to say; tidy or verbatim, the text is still
well-formed words. *Agreement:* both point the same way, so this test speaks most
cleanly to design. The early data fits. Two cautions. Even CTC models "can still
implicitly learn a context-dependent internal language model" through a strong
encoder ([Yang et al. 2025](https://arxiv.org/abs/2506.06096)), so Parakeet is not
LM-free. And Granite Plus writes no punctuation, which may make a judge read its text
as garbled; compare it on stripped text.

**(b) Restarts and fillers kept.** *Design predicts:* the speech LLMs smooth restarts
away, because a fluent sentence is what an LLM expects. Parakeet keeps the most.
*Training style predicts:* engines trained on tidied text drop them, whatever their
size. Whisper learned from web captions and its own predecessor's output. Canary and
Parakeet learned largely from Whisper large-v3's output, so they should inherit some
of its tidying, softened by the human-labelled data (Fisher, AMI) in Parakeet's
fine-tuning. Granite's sources include phone-call corpora first transcribed with
fillers, but how IBM prepared them is unknown. For Qwen3 and Voxtral the style is
unknown. *Where they pull apart:* this is the clearest split. Qwen3 has a 1.7B LLM
and keeps about 70% of restarts; Whisper has a smaller, transcript-only decoder and
keeps about 6%. Design alone predicts the reverse. So restarts look like a style
effect. Alibaba testing on "nonfluent and tongue-twister-like repetitive speech"
([Qwen3-ASR report, §4.1](https://arxiv.org/abs/2601.21337)) fits that, but it is
indirect. A further check: Canary and Parakeet should keep restarts at a rate closer
to Whisper's than to Qwen3's, if inherited style is real.

*A first answer for Parakeet (1 November 2026).* Earnings-22's Subset 10 has a verbatim
and a cleaned-up human reference for the same ten calls
(`findings/earnings22/subset10-two-references.csv`). With fillers kept and punctuation
ignored, Whisper sits 7.1% from the clean reference and 13.0% from the verbatim one;
Parakeet the reverse, 9.8% from verbatim and 15.4% from clean; Qwen3 in between. So
Parakeet did not inherit Whisper's tidying. The 7,500 hours of human transcripts in
its fine-tuning, phone calls and meetings among them, are one possible reason; this
data cannot say. Canary was not run on Earnings-22.

**(c) African American English grammar kept or rewritten.** *Design predicts:* the
speech LLMs rewrite most. Their LLMs learned mostly from written text before they
heard any speech (my inference; the pretraining text was not checked for this note).
SHALLOW found that on CORAAL hallucination measures rose "with SpeechLLMs suffering
more than other models" ([Koudounas et al. 2025, §5](https://arxiv.org/abs/2510.16567)).
*Training style predicts:* engines trained on captions written to standard
conventions rewrite, and their descendants too: Whisper first, then Canary and
Parakeet. *Where they pull apart:* the early data (Whisper rewrites most) fits style
better than design. Voxtral is a useful middle case. It has Whisper's encoder and a
large LLM, but not Whisper's decoder. If Voxtral rewrites like Whisper, the habit may
partly sit in the shared encoder, and the test cannot separate the two cleanly.

**(d) Slips the reporter corrected: the slip or the correction?** *Design predicts:*
the engines with a strong language model write the intended word, because their
expectation can outvote the audio. That means the speech LLMs and, to a lesser degree,
Whisper. Parakeet writes the slip as spoken (or garbles it). Longer chunks give more
context to resolve the intended word, which favours Qwen3 and Voxtral (280 s) over
Whisper (30 s). *Training style predicts:* engines trained on verbatim targets write
the slip; engines trained on tidied targets write the correction, as a reporter does.
*Where they pull apart:* Qwen3 is the key case. If it writes the correction while
keeping restarts, its LLM is acting on word choice but not on disfluency structure.
That would separate the two forces inside one engine.

**(e) Fluent words invented into silence.** *Design predicts:* the autoregressive
decoders can do this, because they keep writing what plausibly comes next. That is
Whisper, Canary and the four speech LLMs. A transducer writes "blank" frame by frame
and has less pull to fill a gap; Parakeet's known failure is the opposite, going
silent over speech. Whisper's habit is documented: "complete hallucination" in its own
paper, and about 1% of transcripts in Careless Whisper "contained entire hallucinated
phrases or sentences", more often for speakers with "longer shares of non-vocal
durations" ([Koenecke et al. 2024](https://arxiv.org/abs/2402.08021)). *Training
style predicts:* engines trained on silence with empty targets should invent less.
Canary and Parakeet had 36,000 hours of it, Qwen3 has a "no speech" output, and
Whisper has a `<|nospeech|>` token. Voxtral and Granite: not stated. *Caution:* four
engines get their timings from the forced aligner, which this project measured as
roughly doubling apparent silence. An invented phrase in a quiet stretch could be
placed in the wrong place by the aligner. Only Whisper, Parakeet and Granite Plus
time their own words.

## Background

- **The internal language model.** End-to-end models "implicitly learn an internal LM
  that characterizes the training data", both attention encoder-decoder and RNN-T
  models. Internal language model estimation (ILME) estimates it by running the model
  with its acoustic input removed ([Meng et al. 2021](https://arxiv.org/abs/2011.01991)).
  The Hybrid Autoregressive Transducer (HAT) was built partly to "measure the quality
  of the internal language model" of a transducer ([Variani et al. 2020](https://arxiv.org/abs/2003.07705)).
  So the hypothesis has a name in the literature: engines differ in the strength of
  their internal LM.
- **Why transducers and CTC are thought to lean less on context.** CTC labels each
  frame without looking at its earlier output, the "conditional independence
  assumption" ([Nozaki and Komatsu 2021](https://arxiv.org/abs/2104.02724)). A
  transducer's prediction network was "believed to be analogous to the Language Model
  (LM)", but a stateless version that sees only the last token "performs virtually as
  well", which suggests it "does not function as the LM in classical ASR"
  ([Ghodsi et al. 2020](https://research.google/pubs/rnn-transducer-with-stateless-prediction-network/)).
  The counterpoint: a strong encoder can learn context anyway, even in CTC
  ([Yang et al. 2025](https://arxiv.org/abs/2506.06096)). So the difference is one of
  degree.
- **LLM-based against conventional ASR.** SHALLOW tested Whisper, Canary, Parakeet and
  six speech LLMs (including the older Granite-Speech 8B and Qwen2.5-Omni, not the
  versions here). It describes decoder-based speech LLMs as "prioritiz[ing] linguistic
  fluency over exact acoustic matching" and Parakeet's design as one that "emphasizes
  acoustic modeling" ([Koudounas et al. 2025](https://arxiv.org/abs/2510.16567); under
  review). Atwany et al. tested over 20 models and found that "encoder-only models are
  less prone to hallucinations relative to their overall errors", and that "low WERs
  may conceal dangerous hallucinations" ([Atwany et al. 2025](https://arxiv.org/abs/2502.12414)).
  Prompting Whisper with the expected text improved verbatim transcription over
  fine-tuning alone ([Smith et al. 2025](https://arxiv.org/abs/2505.23627)).

## Not found or unverified

- **Filler and restart policy in training transcripts: not stated for any of the
  seven.** No maker says whether fillers, restarts or false starts were kept. Every
  statement about "training style" in this note is inferred from the data sources.
- **Whisper:** the share of verbatim vs tidied web transcripts. The claim that base
  Whisper drops fillers rests on indirect evidence (CrisperWhisper's fine-tuning,
  OpenAI's prompting example), not on an OpenAI statement. The decoder's size (about
  0.9B) is my subtraction, not a published number.
- **Qwen3-ASR:** what made its 40 million hours of pseudo-labels, and from what
  sources. The Qwen announcement page (qwen.ai/blog?id=qwen3asr) did not load for me.
- **Voxtral:** training hours, sources, and the ASR model used for pseudo-labels.
- **Granite 4.1:** how the punctuated targets were produced, and whether the
  Switchboard/Fisher fillers were kept. Whether the LoRA adapter is merged into the
  released weights (the config says `has_lora_adapter: false`; the card does not say).
- **Data overlap with our test sets.** Granite 4.1 trained on 105 hours of Earnings-22,
  so its Earnings-22 scores here are on data it has seen. AMI and Fisher are in
  NVIDIA's and IBM's training sets. CORAAL and EdAcc are not listed for any engine,
  but Qwen3 and Voxtral do not list their sources, so overlap cannot be ruled out.
- **Canary and Parakeet's "not recommended for word-for-word" line:** I could not
  find what NVIDIA mean by it. It appears word for word on both cards and may be
  template text.
- **SHALLOW** is under review and tested older or different versions of most of these
  engines, so it supports the general pattern, not claims about these exact models.
- **Careless Whisper's venue** (FAccT 2024) is not on the arXiv page I opened; cite
  the arXiv version.

## How the sizes were counted

Sizes marked * were counted on 1 November 2026 from the tensor headers of the
safetensors files in this laptop's Hugging Face cache, grouped by component (no
model was loaded and no GPU used). Parakeet: encoder 608.9M, prediction network
12.2M, joint 5.3M. Canary: encoder 811.1M, decoder 151.2M. Qwen3-ASR: audio encoder
314.3M, LLM 1,720.6M, total 2,038M. Voxtral: audio encoder 637.0M, LLM 3,611.5M plus
a 402.7M output layer, total 4,676M. Granite base: encoder 440.2M, LLM 1,631.8M plus
a 205.5M output layer, total 2,313M. Granite Plus: total 2,112M, with no separate
output layer. Whisper is stored in faster-whisper's own format and was not counted.

## References

Model cards and configuration

- OpenAI. Whisper large-v3 model card. https://huggingface.co/openai/whisper-large-v3
- OpenAI. Whisper prompting guide (cookbook). https://developers.openai.com/cookbook/examples/whisper_prompting_guide
- NVIDIA. Canary-1b-v2 model card. https://huggingface.co/nvidia/canary-1b-v2
- NVIDIA. Parakeet-TDT-0.6B-v3 model card and config.json. https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3
- Qwen. Qwen3-ASR-1.7B model card. https://huggingface.co/Qwen/Qwen3-ASR-1.7B
- Qwen. Qwen3-ASR-1.7B-hf model card. https://huggingface.co/Qwen/Qwen3-ASR-1.7B-hf
- Mistral AI. Voxtral-Mini-3B-2507 model card. https://huggingface.co/mistralai/Voxtral-Mini-3B-2507
- IBM. granite-speech-4.1-2b model card. https://huggingface.co/ibm-granite/granite-speech-4.1-2b
- IBM. granite-speech-4.1-2b-plus model card (updated 19 Oct 2026). https://huggingface.co/ibm-granite/granite-speech-4.1-2b-plus
- IBM. granite-4.0-1b-base model card. https://huggingface.co/ibm-granite/granite-4.0-1b-base

Papers and reports on the engines

- Radford, A., Kim, J. W., Xu, T., Brockman, G., McLeavey, C., & Sutskever, I. (2022). Robust speech recognition via large-scale weak supervision. arXiv:2212.04356. https://cdn.openai.com/papers/whisper.pdf
- Sekoyan, M., Koluguri, N. R., Tadevosyan, N., Zelasko, P., Bartley, T., Karpov, N., Balam, J., & Ginsburg, B. (2025). Canary-1B-v2 & Parakeet-TDT-0.6B-v3: Efficient and high-performance models for multilingual ASR and AST. arXiv:2509.14128. https://arxiv.org/abs/2509.14128
- Koluguri, N. R., Sekoyan, M., Zelenfroynd, G., et al. (2025). Granary: Speech recognition and translation dataset in 25 European languages. arXiv:2505.13404. https://arxiv.org/abs/2505.13404
- Xu, H., Jia, F., Majumdar, S., Huang, H., Watanabe, S., & Ginsburg, B. (2023). Efficient sequence transduction by jointly predicting tokens and durations. arXiv:2304.06795. https://arxiv.org/abs/2304.06795
- Shi, X., Wang, X., Guo, Z., et al. (2026). Qwen3-ASR technical report. arXiv:2601.21337. https://arxiv.org/abs/2601.21337
- Liu, A. H., Ehrenberg, A., Lo, A., et al. (2025). Voxtral. arXiv:2507.13264. https://arxiv.org/abs/2507.13264
- Saon, G., et al. (2025). Granite-speech: Open-source speech-aware LLMs with strong English ASR capabilities. arXiv:2505.08699. https://arxiv.org/abs/2505.08699
- Wagner, L., Thallinger, B., & Zusag, M. (2024). CrisperWhisper: Accurate timestamps on verbatim speech transcriptions. Interspeech 2024. arXiv:2408.16589. https://arxiv.org/abs/2408.16589

Background

- Meng, Z., Parthasarathy, S., Sun, E., Gaur, Y., Kanda, N., Lu, L., Chen, X., Zhao, R., Li, J., & Gong, Y. (2021). Internal language model estimation for domain-adaptive end-to-end speech recognition. IEEE SLT 2021. arXiv:2011.01991. https://arxiv.org/abs/2011.01991
- Variani, E., Rybach, D., Allauzen, C., & Riley, M. (2020). Hybrid autoregressive transducer (HAT). arXiv:2003.07705. https://arxiv.org/abs/2003.07705
- Ghodsi, M., Liu, X., Apfel, J., Cabrera, R., & Weinstein, E. (2020). RNN-Transducer with stateless prediction network. ICASSP 2020, 7049-7053. https://research.google/pubs/rnn-transducer-with-stateless-prediction-network/
- Nozaki, J., & Komatsu, T. (2021). Relaxing the conditional independence assumption of CTC-based ASR by conditioning on intermediate predictions. Interspeech 2021. arXiv:2104.02724. https://arxiv.org/abs/2104.02724
- Yang, Z., Phan, M.-N., Schlüter, R., & Ney, H. (2025). Label-context-dependent internal language model estimation for CTC. Interspeech 2025. arXiv:2506.06096. https://arxiv.org/abs/2506.06096
- Koenecke, A., Choi, A. S. G., Mei, K. X., Schellmann, H., & Sloane, M. (2024). Careless Whisper: Speech-to-text hallucination harms. arXiv:2402.08021. https://arxiv.org/abs/2402.08021
- Smith, G. D., Yee, D., Chen, J. K., & Findlater, L. (2025). Prompting Whisper for improved verbatim transcription and end-to-end miscue detection. Interspeech 2025. arXiv:2505.23627. https://arxiv.org/abs/2505.23627
- Atwany, H., Waheed, A., Singh, R., Choudhury, M., & Raj, B. (2025). Lost in transcription, found in distribution shift: Demystifying hallucination in speech foundation models. arXiv:2502.12414. https://arxiv.org/abs/2502.12414
- Koudounas, A., La Quatra, M., Giollo, M., Siniscalchi, S. M., & Baralis, E. (2025). Hallucination benchmark for speech foundation models (SHALLOW). arXiv:2510.16567, under review. https://arxiv.org/abs/2510.16567
