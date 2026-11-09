# Reading list for the literature review

17 October 2026. For the midterm draft (due 28 October), which needs a 2–3 page review.

**How to order it.** Start with how ASR accuracy is measured: WER, the text normalisation
behind leaderboards, and why a verbatim record is a different target (section 1). Then which
words are hard and why, and the evidence that human transcribers, court reporters included,
stumble on the same kinds of speech (sections 2 and 3). That sets up the shared-errors result
and the ROVER literature, followed by the two ways of fixing output, LLM post-correction and
fine-tuning (sections 3, 5 and 6). Close with fairness and the court setting as the stakes, and
put diarization in as a known gap (sections 4, 6 and 7).

Every entry below was checked with a web search on 17 October 2026, and every link worked then.
**[core]** marks the eight to read first. 25 entries.

---

## 1. Measuring accuracy: WER, normalisation and verbatim records

**[core]** Radford, A., Kim, J. W., Xu, T., Brockman, G., McLeavey, C., & Sutskever, I. (2023).
Robust speech recognition via large-scale weak supervision. *Proceedings of the 40th
International Conference on Machine Learning*, PMLR 202, 28492–28518.
https://proceedings.mlr.press/v202/radford23a.html
The Whisper paper. It says plain WER "penalizes all differences" including "minor formatting
differences", so the authors built an extensive text normaliser (Appendix C) that strips them
before scoring. That normaliser is the benchmark scoring this project compares against in
finding 1.

**[core]** Srivastav, V., Zheng, S., Bezzam, E., Le Bihan, E., Koluguri, N. R., Żelasko, P.,
Majumdar, S., Moumen, A., Gandhi, S., et al. (2025). Open ASR Leaderboard: Towards reproducible
and transparent multilingual and long-form speech recognition evaluation. arXiv:2510.06961.
https://arxiv.org/abs/2510.06961
The paper behind the Hugging Face leaderboard. It scores 60+ systems after an English normaliser
"closely following that of Whisper" that removes punctuation, casing and fillers. This is the
ranking that finding 1 says points to the wrong model for legal-record work.

**[core]** Gandhi, S., von Platen, P., & Rush, A. M. (2022). ESB: A benchmark for multi-domain
end-to-end speech recognition. arXiv:2210.13352. https://arxiv.org/abs/2210.13352
Argues that punctuation and casing are hard for ASR systems and should be kept in evaluation,
not normalised away. It is the closest published support for scoring the verbatim record
(finding 1).

Meister, A., Novikov, M., Karpov, N., Bakhturina, E., Lavrukhin, V., & Ginsburg, B. (2023).
LibriSpeech-PC: Benchmark for evaluation of punctuation and capitalization capabilities of
end-to-end ASR models. arXiv:2310.02943. https://arxiv.org/abs/2310.02943
Proposes a Punctuation Error Rate and a punctuated test set, noting that punctuation prediction
is poorly evaluated. A ready-made comparison for how this project scores punctuation and the
reporter's dash (finding 1).

Kim, S., Arora, A., Le, D., Yeh, C.-F., Fuegen, C., Kalinli, O., & Seltzer, M. L. (2021).
Semantic distance: A new metric for ASR performance analysis towards spoken language
understanding. *Proc. Interspeech 2021*.
https://www.isca-archive.org/interspeech_2021/kim21e_interspeech.html
Shows WER predicts downstream understanding poorly and proposes a meaning-based metric. It
frames the opposite direction from this project: they go looser than WER, a legal record needs
stricter.

Apple Machine Learning Research. (2024, March 7). Humanizing word error rate for ASR transcript
readability and accessibility. https://machinelearning.apple.com/research/humanizing-wer
Introduces HEWER, which counts only errors that hurt readability (proper nouns, capitalisation,
some punctuation) and ignores fillers. On podcasts, WER of 9.2% became HEWER of 1.4%. Useful
contrast for finding 1, because it treats fillers as harmless when a verbatim record must keep
them. Note: a company research post, not a peer-reviewed paper.

Bucholtz, M. (2000). The politics of transcription. *Journal of Pragmatics, 32*(10), 1439–1465.
https://doi.org/10.1016/S0378-2166(99)00094-6
A linguist's argument that every transcript involves choices about what to write down and how,
and that those choices have consequences (one example is a police interrogation transcript).
Frames verbatim versus clean transcription as a real decision, not a formatting detail.

## 2. Which words are hard, and why

**[core]** Goldwater, S., Jurafsky, D., & Manning, C. (2010). Which words are hard to recognize?
Prosodic, lexical, and disfluency factors that increase speech recognition error rates.
*Speech Communication, 52*(3), 181–200. https://nlp.stanford.edu/~manning/papers/goldwater10.pdf
Uses a regression on individual words to find what predicts errors: turn-initial words,
discourse markers, words next to disfluencies, and rare words. This is the direct precedent for
the word-level logistic regression in finding 2.

Del Rio, M., Delworth, N., Westerman, R., Huang, M., Bhandari, N., Palakapilly, J., McNamara, Q.,
Dong, J., Żelasko, P., & Jetté, M. (2021). Earnings-21: A practical benchmark for ASR in the
wild. *Proc. Interspeech 2021*.
https://www.isca-archive.org/interspeech_2021/delrio21_interspeech.html
A corpus of earnings calls with punctuated, entity-tagged transcripts. It found that accuracy on
some kinds of named entities is poor. Supports finding 2 on proper names and specialist terms.

Shriberg, E., Stolcke, A., & Baron, D. (2001). Observations on overlap: Findings and implications
for automatic processing of multi-party conversation. *Proc. Eurospeech 2001*, 1359–1362.
https://www.isca-archive.org/eurospeech_2001/shriberg01_eurospeech.html
In meetings, recognition was fine outside overlaps but dropped a lot inside them, and
interruptions tend to come at backchannels, discourse markers and disfluencies. Supports the
crosstalk-near-the-dash part of finding 2.

Koenecke, A., Choi, A. S. G., Mei, K. X., Schellmann, H., & Sloane, M. (2024). Careless Whisper:
Speech-to-text hallucination harms. *Proceedings of the 2024 ACM Conference on Fairness,
Accountability, and Transparency (FAccT '24)*, 1672–1681. https://arxiv.org/abs/2402.08021
About 1% of Whisper transcriptions contained invented phrases, more often in speech with long
pauses or disfluencies, and the authors name courtroom use as a risk. Relevant to finding 2
(disfluent stretches) and to why a record needs checking.

## 3. Humans and machines: shared mistakes and combining systems

**[core]** Stolcke, A., & Droppo, J. (2017). Comparing human and machine errors in
conversational speech transcription. *Proc. Interspeech 2017*. https://arxiv.org/abs/1708.08615
Compared a top recogniser with a professional transcription vendor on the same test set: their
most common errors overlapped heavily, except that the machine confused "uh" and "uh-huh" far
more. The closest published version of this project's title claim.

Xiong, W., Droppo, J., Huang, X., Seide, F., Seltzer, M., Stolcke, A., Yu, D., & Zweig, G.
(2016). Achieving human parity in conversational speech recognition. arXiv:1610.05256.
https://arxiv.org/abs/1610.05256
Measured professional transcribers at 5.9% WER on Switchboard and 11.3% on CallHome, and noted
that the often-quoted 4% human figure had no real source. A model for setting the human
baseline (finding 5).

**[core]** Jones, T., Kalbfeld, J., Hancock, R., & Clark, R. (2019). Testifying while black:
An experimental study of court reporter accuracy in transcription of African American English.
*Language, 95*(2), e216–e252. https://doi.org/10.1353/lan.2019.0042
Certified Philadelphia court reporters fell well short of the 95% certification standard on
everyday African American English, and many errors changed who did what. Press coverage reports
about 83% word accuracy; check that figure in the paper before quoting it. The only peer-reviewed
measure of court reporter accuracy found (findings 5 and 6).

**[core]** Fiscus, J. G. (1997). A post-processing system to yield reduced word error rates:
Recognizer output voting error reduction (ROVER). *1997 IEEE Workshop on Automatic Speech
Recognition and Understanding Proceedings*, 347–354. https://doi.org/10.1109/ASRU.1997.659110
The standard method for aligning several recognisers' outputs and voting word by word. It only
helps when the systems make different mistakes, which is why finding 3 (shared mistakes, vote of
seven not beating the best model) is a fair test of it.

## 4. Fairness and speaker variety

**[core]** Koenecke, A., Nam, A., Lake, E., Nudell, J., Quartey, M., Mengesha, Z., Toups, C.,
Rickford, J. R., Jurafsky, D., & Goel, S. (2020). Racial disparities in automated speech
recognition. *Proceedings of the National Academy of Sciences, 117*(14), 7684–7689.
https://doi.org/10.1073/pnas.1915768117
Five commercial systems had roughly twice the error rate for Black speakers as for white
speakers, using CORAAL interviews. The main reason to add CORAAL (finding 6).

Sanabria, R., Bogoychev, N., Markl, N., Carmantini, A., Klejch, O., & Bell, P. (2023). The
Edinburgh International Accents of English Corpus: Towards the democratization of English ASR.
*ICASSP 2023*. https://arxiv.org/abs/2303.18110
The EdAcc paper. The best model averaged 19.7% WER across accents against 2.7% on clean US read
speech. One of this project's datasets (finding 6).

Kendall, T., & Farrington, C. (2023). *The Corpus of Regional African American Language*
(Version 2023.06). The Online Resources for African American Language Project.
https://doi.org/10.7264/1ad5-6t35
The corpus itself, with the citation its maintainers ask for. Needed when CORAAL is added.

## 5. Fixing the output with a language model

Chen, C., Hu, Y., Yang, C.-H. H., Siniscalchi, S. M., Chen, P.-Y., & Chng, E. S. (2023).
HyPoradise: An open baseline for generative speech recognition with large language models.
*Advances in Neural Information Processing Systems 36* (Datasets and Benchmarks Track).
https://proceedings.neurips.cc/paper_files/paper/2023/hash/6492267465a7ac507be1f9fd1174e78d-Abstract.html
An open benchmark for letting an LLM rewrite ASR output from its top guesses, with sizeable WER
gains. Frames finding 4, with one difference: this project only lets the LLM change formatting,
not words.

Ma, R., Qian, M., Manakul, P., Gales, M., & Knill, K. (2023). Can generative large language
models perform ASR error correction? arXiv:2307.04172. https://arxiv.org/abs/2307.04172
Tests ChatGPT as a zero- and one-shot ASR corrector and finds gains. Close to this project's
setup of a general LLM with no training on ASR errors (finding 4).

## 6. ASR in court and legal settings, and fine-tuning

Conference of State Court Administrators. (2010). *Digital recording: Changing times for making
the record* [Policy paper]. National Center for State Courts.
https://cosca.ncsc.org/resources-courts/digital-recording-changing-times-making-record
State court administrators recommending digital recording as the main way to make the record,
mostly on cost and access. A policy position rather than an accuracy study, which is itself
worth pointing out in the review.

Garneau, N., & Bolduc, O. (2024). The state of commercial automatic French legal speech
recognition systems and their impact on court reporters et al. arXiv:2408.11940.
https://arxiv.org/abs/2408.11940
Benchmarks three ASR systems on French legal speech and discusses what they mean for court
reporters. The best system still had about 15% WER, so human review was still needed. The
nearest study to this one, in another language.

Saadany, H., Orăsan, C., Breslin, C., Barczentewicz, M., & Walker, S. (2025). Employing AI for
better access to justice: An automatic text-to-video linking tool for UK Supreme Court hearings.
*Applied Sciences, 15*(16), 9205. https://doi.org/10.3390/app15169205
Fine-tuned ASR on 139 hours of edited UK Supreme Court hearing transcripts and reports 9% better
accuracy than generic models. The only in-domain court fine-tuning result found. Gives an
expectation for the Qwen3-ASR fine-tuning test (theme 8).

## 7. Who is speaking: diarization

Tumminia, J., Kuznecov, A., Tsilerides, S., Weinstein, I., McFee, B., Picheny, M., & Kaufman,
A. R. (2021). Diarization of legal proceedings: Identifying and transcribing judicial speech
from recorded court audio. arXiv:2104.01304. https://arxiv.org/abs/2104.01304
Identifies which Justice is speaking in US Supreme Court oral arguments (Oyez audio), reaching
13.8% diarization error for Justices in their reference library. Same audio source as this
project; a starting point for the speaker-identification gap the proposal flags.

Watanabe, S., Mandel, M., Barker, J., Vincent, E., et al. (2020). CHiME-6 Challenge: Tackling
multispeaker speech recognition for unsegmented recordings. arXiv:2004.09249.
https://arxiv.org/abs/2004.09249
Defines cpWER, a WER that also checks words are given to the right speaker. The obvious metric
if this project ever scores speaker labels along with words.

---

## Verified but cut for length

Checked and real, left out to stay near 25:

- Saon, G., et al. (2017). English conversational telephone speech recognition by humans and
  machines. *Interspeech 2017*. https://arxiv.org/abs/1703.02136 (human accuracy may be better
  than Xiong et al. measured)
- Morris, A. C., Maier, V., & Green, P. (2004). From WER and RIL to MER and WIL. *Interspeech
  2004*. https://www.isca-archive.org/interspeech_2004/morris04_interspeech.html
- Manohar, K., Pillai, L. G., & Sherly, E. (2024). What is lost in normalization? *EMNLP 2024*.
  https://arxiv.org/abs/2409.02449 (Whisper-style normalisers hide errors, shown for Indic
  scripts)
- Smith, G. D., Yee, D., Chen, J. K., & Findlater, L. (2025). Prompting Whisper for improved
  verbatim transcription and end-to-end miscue detection. *Interspeech 2025*.
  https://arxiv.org/abs/2505.23627
- Çetin, Ö., & Shriberg, E. (2006). Analysis of overlaps in meetings by dialog factors, hot
  spots, speakers, and collection site. *Interspeech 2006*.
  https://www.isca-archive.org/interspeech_2006/cetin06_interspeech.html
- Tatman, R. (2017). Gender and dialect bias in YouTube's automatic captions. *First ACL Workshop
  on Ethics in NLP*. https://aclanthology.org/W17-1606/
- Mangu, L., Brill, E., & Stolcke, A. (2000). Finding consensus in speech recognition. *Computer
  Speech & Language, 14*(4), 373–400. https://arxiv.org/abs/cs/0010012
- Park, T. J., et al. (2022). A review of speaker diarization: Recent advances with deep learning.
  *Computer Speech & Language, 72*, 101317. https://arxiv.org/abs/2101.09624
- Yuan, J., & Liberman, M. (2008). Speaker identification on the SCOTUS corpus. *J. Acoust. Soc.
  Am., 123*(5 Suppl.), 3878. https://doi.org/10.1121/1.2935783
- Hwang, H., et al. (2026). Towards a clinical adaptation of the Whisper model for French.
  *ICNLSP 2026*, 350–358. https://aclanthology.org/2026.icnlsp-1.32/ (fine-tuning on about 48
  hours roughly halved WER, from secondary summary; not read in full)

## Searched for but found little

- **US court ASR studies.** No peer-reviewed accuracy study of ASR on US court audio in English
  turned up. The nearest are the French (Garneau & Bolduc) and UK (Saadany et al.) papers, plus
  preprints on the Supreme Court of India (arXiv:2309.10088) and an Ethiopian court system, which
  were not checked closely.
- **Court reporter accuracy beyond Jones et al.** No other published measure, and nothing on
  agreement between two reporters transcribing the same audio. That makes the human baseline in
  finding 5 new.
- **Digital recording versus stenography.** Only policy papers. An NCSC report, *Making the
  Record Utilizing Digital Electronic Recording* (Suskin, McMillan & Hall, September 2013), exists
  but its PDF would not open, so it is not listed above.
- **Shared errors across modern models.** Nothing measures how often today's open models miss
  the same words. The nearest is a 2000 ICSI diagnostic study of eight Switchboard systems
  (Greenberg and colleagues), which could not be opened to confirm authors and venue.
- **The reporter's interruption dash.** Nothing on scoring "--" or interruption marks in ASR
  output.
- **Fine-tuning on legal English.** Nothing beyond Saadany et al.
- **HEWER in peer review.** Only Apple's blog post.
