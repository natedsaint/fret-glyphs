"""Parse a changes file into sections -> bars, preserving structure.

Bar dict: {'chords':[sym,...], 'rs':bool repeat-start, 're':bool repeat-end, 'ending':int|None}
Repeats are NOT expanded: each written bar is voiced once, so a repeated
section is guaranteed to be fingered identically both times.
"""
import re

def parse(text):
    meta={}; sections=[]; cur=None; prev=None; ending=None
    for raw in text.splitlines():
        line=raw.strip()
        if not line or line.startswith('#'):
            continue
        m=re.match(r'\{(\w+)\s*:\s*(.*?)\}$', line)
        if m:
            k,v=m.group(1).lower(), m.group(2).strip()
            if k=='section':
                cur={'label':v,'bars':[]}; sections.append(cur); prev=None
            elif k=='ending':
                ending=int(v)
            else:
                meta[k]=v
            continue
        if cur is None:
            cur={'label':'','bars':[]}; sections.append(cur)
        body=line
        rs = body.startswith('|:')
        re_ = body.endswith(':|')
        body=body.strip('|').strip()
        if body.startswith(':'): body=body[1:]
        if body.endswith(':'): body=body[:-1]
        cells=[c.strip() for c in body.split('|')]
        for i,c in enumerate(cells):
            if not c: continue
            if c=='%':
                chords=list(prev) if prev else []
            else:
                chords=c.split()
            prev=chords
            cur['bars'].append({
                'chords':chords,
                'rs': rs and i==0,
                're': re_ and i==len(cells)-1,
                'ending':ending,
            })
            ending=None
    return meta, sections

def flatten(sections):
    """Ordered list of (section_idx, bar_idx, chord_idx, symbol)."""
    out=[]
    for si,sec in enumerate(sections):
        for bi,bar in enumerate(sec['bars']):
            for ci,sym in enumerate(bar['chords']):
                out.append((si,bi,ci,sym))
    return out
