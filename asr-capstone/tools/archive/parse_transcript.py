"""Turn a Supreme Court oral argument transcript PDF into speaker turns.

Only the numbered transcript lines (1-25 on each page) carry spoken words.
Everything else on the page - the running header, the page number, the cover
sheet and the appearance list - is discarded.
"""
import re, sys, json, subprocess, os

LABEL = re.compile(r'^((?:CHIEF JUSTICE|JUSTICE|QUESTION|THE COURT|MR|MS|MRS|GENERAL|DEAN|PROF)'
                   r'[A-Z .\'-]{0,28}?):\s*(.*)$')
NUMBERED = re.compile(r'^\s*(\d{1,2})\s+(.*)$')
HEADER = re.compile(r'Official - Subject to Final Review|Alderson Reporting|Heritage Reporting')
PAREN = re.compile(r'^\((Laughter|Pause|Recess)')
# The argument text ends here; everything after is the keyword index, whose
# lines also begin with digits and would otherwise be counted as speech.
END = re.compile(r'\(Whereupon|was submitted\.\)|ORAL ARGUMENT OF .* RECESS')

def lines_from_pdf(pdf):
    txt = pdf[:-4] + '.txt'
    if not os.path.exists(txt):
        subprocess.run(['pdftotext', '-layout', pdf, txt], check=True)
    return open(txt, encoding='utf8', errors='ignore').read().splitlines()

def parse(pdf):
    turns, cur, started = [], None, False
    for raw in lines_from_pdf(pdf):
        if END.search(raw):
            break
        if HEADER.search(raw):
            continue
        m = NUMBERED.match(raw.rstrip())
        if not m:
            continue
        text = m.group(2).strip()
        if not text:
            continue
        lab = LABEL.match(text)
        if lab:
            started = True
            if cur:
                turns.append(cur)
            cur = {'speaker': lab.group(1).strip(), 'text': lab.group(2).strip()}
        elif PAREN.match(text):
            continue                      # stage direction, not speech
        elif started and cur:
            cur['text'] += ' ' + text
    if cur:
        turns.append(cur)
    return [t for t in turns if t['text']]

if __name__ == '__main__':
    for pdf in sys.argv[1:]:
        t = parse(pdf)
        json.dump(t, open(os.path.dirname(pdf) + '/transcript_turns.json', 'w'), indent=1)
        print(pdf, len(t), 'turns', sum(len(x['text'].split()) for x in t), 'words')
