# Where speech recognition goes wrong in an interesting way

Five kinds of failure, found the same way in every data set (Supreme Court, EdAcc,
CORAAL, Earnings-22). The first four are mistakes a listener could make, in this order of
importance; the fifth is the engine not working at all for a while:

1. **Meaning changes** (`meaning/`) - the engine writes something fluent that says
   something different: a dropped "not", "can" for "can't", a different number, a
   different content word. Nothing on the page shows a reader it is wrong.
2. **Invented words** (`invented/`) - words written over silence.
3. **The engine edits the speaker** (`edits/`) - it rewrites how the person spoke:
   African American English grammar turned into standard English on CORAAL
   ("he be working" written "he's working"), false starts and restarts cleaned up.
4. **Silent skips** (`skips/`) - a stretch of clear speech left out, with no mark
   where it was.
5. **Breakdowns** (`breakdown/`, added 25 October 2026) - the engine or our pipeline
   broke: 30 seconds or more with nothing written (an empty chunk, Parakeet's stall), a
   word or passage written over and over (a loop), or text that is not speech (another
   alphabet, a broken character, a model tag). Its `per-recording.csv` gives the share
   of each recording affected, so broken output can be told apart from mishearing.

Not here on purpose: names spelled differently, speaker labels, capitals and
punctuation, "uh" and "um", number formatting ("10" for "ten"). They count in the
error rates but say little about how the engines fail.

## How each finder works

Every finder starts from `tools/lineup.py`: the recordings of each data set, the run
holding each engine's transcript, and each engine lined up against the reference
word by word (`lineup.load(job)`, cached in `cache/`, ignored by git). Parakeet's
transcripts are from its `-reread` runs since 23 October 2026 (`../parakeet-stall/`). The finders
read the runs and the corpora and write only here.

## Files, the same for every kind

`<kind>/candidates.csv` - every case the rules find. The first columns are shared:

| column | what |
|---|---|
| corpus | `scotus`, `edacc`, `coraal` or `earnings22` |
| part | Supreme Court term (`OT2017`), EdAcc split (`test`, `dev`), CORAAL component (`ROC`, `PRV`, `DCB`, `ATL`, `DCA`, `DTA`, `LES`, `VLD`) or Earnings-22 region (`Asian`) |
| recording | docket or recording id, as the runs name it |
| engine | `Qwen3`, `Whisper`, `Parakeet`, and on EdAcc also `Canary`, `Granite` |
| kind | `meaning`, `invented`, `edits`, `skips` or `breakdown` |
| subkind | the finder's own label, e.g. `negation`, `number`, `habitual-be`, `restart` |
| start, end | seconds in the recording where it happens (engine's word times) |
| record | what the reference has there |
| engine_wrote | what the engine wrote there |
| record_context | a few reference words either side, the stretch in [brackets] |
| engine_context | the same from the engine |
| others_right | the other engines that wrote what the reference has, space-separated |
| evidence | one short line: why the rules picked it (speech share, level, feature) |

A finder may add columns after these.

`<kind>/shortlist.csv` - the clearest and most telling cases, read one by one: the
shared columns plus `interest` (1-5), `clarity` (1-5) and `explanation` (one plain
sentence a reader with no background understands). Spread over data sets and
engines. Nothing in it has been checked by ear unless `heard` says so.

`<kind>/counts.csv` - per corpus, part and engine: hours of audio, candidates, and
candidates per hour, so engines and data sets can be compared.

`<kind>/README.md` - the rules, thresholds, what they miss, and the counts.
