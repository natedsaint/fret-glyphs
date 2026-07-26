"""MusicXML <-> .pro changes, both directions. The interchange format you get
out of iReal Pro, MuseScore, Finale, etc.

Unlike pdfimport.py this needs NO third-party dependency -- MusicXML is XML, so
the stdlib's xml.etree does the whole job and the core's stdlib-only promise
stays intact. sheet.py never imports this.

Import reads <harmony> off each <measure>. It maps the *standard* <kind> name
(major, dominant, minor-seventh, ...) to a chord symbol, NOT iReal's display
`text` attribute (which uses house shorthand like -7 / ^7 / h7 that the chord
grammar wouldn't parse). Structure that MusicXML actually carries is recovered:
repeat barlines, endings, rehearsal marks -> sections, and system breaks ->
one .pro line per system. Anything whose kind has no faithful symbol in this
tool's small vocabulary (m6, sus, 9, altered dominants, slash bass, added
degrees) is emitted but flagged `#?`, the same safety net pdfimport uses.

Export goes the other way: .pro -> score-partwise, one whole-rest measure per
bar with a <harmony>, repeats/endings/sections written back out.

Usage:
    python musicxml.py chart.musicxml            # import -> .pro on stdout
    python musicxml.py chart.musicxml -o out.pro
    python musicxml.py --export chart.pro        # export -> MusicXML on stdout
    python musicxml.py --export chart.pro -o out.musicxml
"""
import sys, os, argparse
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from chartparse import parse as parse_pro, flatten            # noqa: E402
from voice import parse as parse_chord, strip_root_marker     # noqa: E402

# --- chord vocabulary bridge -------------------------------------------------
# Only kinds with a FAITHFUL symbol in this tool's grammar (voice.QUAL) live
# here; the reconstructed symbol is guaranteed to parse to the right quality.
# Every other kind is flagged on import rather than silently approximated.
KIND_TO_SUFFIX = {
    'major': '', 'minor': 'm', 'augmented': '+', 'diminished': 'o',
    'dominant': '7', 'major-seventh': 'maj7', 'minor-seventh': 'm7',
    'diminished-seventh': 'o7', 'half-diminished': 'm7b5',
    'major-sixth': '6', 'minor-ninth': 'm9', 'dominant-13th': '13',
}
# Reverse, for export: tool quality -> (MusicXML kind name, display text).
QUAL_TO_KIND = {
    'maj': ('major', ''),        'min': ('minor', 'm'),
    'dim': ('diminished', 'o'),  'aug': ('augmented', '+'),
    '7':   ('dominant', '7'),    'maj7': ('major-seventh', 'maj7'),
    'm7':  ('minor-seventh', 'm7'), 'm9': ('minor-ninth', 'm9'),
    '13':  ('dominant-13th', '13'), 'o7': ('diminished-seventh', 'o7'),
    'm7b5':('half-diminished', 'm7b5'), '6': ('major-sixth', '6'),
}
# Circle-of-fifths <-> major-key tonic (mode ignored for the .pro {key:} label).
FIFTHS = {0:'C',1:'G',2:'D',3:'A',4:'E',5:'B',6:'F#',7:'C#',
          -1:'F',-2:'Bb',-3:'Eb',-4:'Ab',-5:'Db',-6:'Gb',-7:'Cb'}
KEY_TO_FIFTHS = {v: k for k, v in FIFTHS.items()}


# ============================ IMPORT (xml -> pro) ============================

def _accidental(alter_text):
    if not alter_text:
        return ''
    a = int(float(alter_text))
    return 'b' * -a if a < 0 else '#' * a

def _symbol(h):
    """A <harmony> element -> (symbol, ok). ok is False when the chord can't be
    represented faithfully and the line should be flagged."""
    step = h.findtext('root/root-step')
    if step is None:                       # functional/other harmony, no root
        return None, False
    root = step + _accidental(h.findtext('root/root-alter'))
    kind_el = h.find('kind')
    kind = (kind_el.text or '').strip() if kind_el is not None else ''
    text = kind_el.get('text') if kind_el is not None else None
    # Faithful only when the base kind maps AND there are no added/altered degrees.
    faithful = kind in KIND_TO_SUFFIX and h.find('degree') is None
    if faithful:
        suffix = KIND_TO_SUFFIX[kind]
    else:                                  # keep iReal's own label (e.g. 7b9, m6, sus)
        suffix = text or KIND_TO_SUFFIX.get(kind) or kind
    sym = root + suffix
    ok = faithful
    bass = h.findtext('bass/bass-step')
    if bass is not None:                   # slash chord: bass not modelled
        sym += '/' + bass + _accidental(h.findtext('bass/bass-alter'))
        ok = False
    return sym, ok

def _rehearsal(measure):
    for r in measure.iter('rehearsal'):
        if r.text and r.text.strip():
            return r.text.strip()
    return None

def _repeat_dirs(measure):
    """(forward, backward) repeat flags on this measure's barlines."""
    fwd = bwd = False
    for bl in measure.findall('barline'):
        rep = bl.find('repeat')
        if rep is not None:
            if rep.get('direction') == 'forward':  fwd = True
            if rep.get('direction') == 'backward': bwd = True
    return fwd, bwd

def import_xml(path):
    return import_score(ET.parse(path).getroot())

def import_score(root):
    """Return (meta, rows). A row is a dict per measure: cell (chord string,
    '%' for an empty bar), ok (False -> flag the line), new_sys, label, rs, re."""
    meta = {}
    if (t := root.findtext('work/work-title')):
        meta['title'] = t.strip()
    for c in root.findall('identification/creator'):
        if c.get('type') == 'composer' and c.text:
            meta['subtitle'] = c.text.strip()
    part = root.find('part')
    if part is None:
        raise SystemExit("no <part> in this file -- is it a valid MusicXML score?")
    measures = part.findall('measure')
    # key + tempo off the first measure that states them
    if (f := part.findtext('measure/attributes/key/fifths')) is not None:
        meta['key'] = FIFTHS.get(int(f), '')
    for snd in part.iter('sound'):
        if snd.get('tempo'):
            meta['tempo'] = str(int(float(snd.get('tempo')))); break

    rows = []                              # (label, cells, is_new_system)
    for m in measures:
        harms = m.findall('harmony')
        if harms:
            syms, oks = zip(*(_symbol(h) for h in harms))
            cell = ' '.join(s for s in syms if s)
            ok = all(oks)
        else:
            cell, ok = '%', True           # empty bar repeats previous
        new_sys = m.find('print[@new-system="yes"]') is not None or not rows
        label = _rehearsal(m)
        fwd, bwd = _repeat_dirs(m)
        rows.append({'cell': cell, 'ok': ok, 'new_sys': new_sys,
                     'label': label, 'rs': fwd, 're': bwd})
    return meta, rows

def to_pro(meta, rows):
    out = []
    for k in ('title', 'subtitle', 'key', 'tempo'):
        if meta.get(k):
            out.append(f'{{{k}: {meta[k]}}}')
    out.append('')
    out.append('# Imported from MusicXML by musicxml.py.')
    if any(not r['ok'] for r in rows):
        out.append("# Lines flagged '#?' hold a chord this tool can't voice "
                   "faithfully (e.g. m6, sus, slash bass) -- VERIFY.")
    out.append('')

    # chartparse only reads |: / :| at line edges, so a repeat span must own its
    # line: break before a repeat-start bar and after a repeat-end bar.
    cur_label = None
    line = None
    def flush():
        nonlocal line
        if line and line['cells']:
            pre = '#? ' if line['bad'] else ''
            lb = '|: ' if line['rs'] else '| '
            rb = ' :|' if line['re'] else ' |'
            out.append(pre + lb + ' | '.join(line['cells']) + rb)
        line = None
    for r in rows:
        if r['label'] and r['label'] != cur_label:
            flush(); out.append(''); out.append(f'{{section: {r["label"]}}}')
            cur_label = r['label']
        elif r['new_sys'] or r['rs']:
            flush()
        if line is None:
            line = {'cells': [], 'rs': r['rs'], 're': False, 'bad': False}
        line['cells'].append(r['cell'] if r['cell'] else ' ')
        line['bad'] = line['bad'] or not r['ok']
        if r['re']:
            line['re'] = True; flush()
    flush()
    return '\n'.join(out) + '\n'


# ============================ EXPORT (pro -> xml) ============================

DIVISIONS = 768
WHOLE = DIVISIONS * 4

def _root_of(sym):
    """Split a symbol into (root-letter, alter-int, rest)."""
    letter = sym[0]
    i, alter = 1, 0
    if len(sym) > 1 and sym[1] in 'b#':
        alter = -1 if sym[1] == 'b' else 1
        i = 2
    return letter, alter, sym[i:]

def _harmony_el(sym):
    sym, _ = strip_root_marker(sym)        # !/~ are tool-only, no MusicXML analogue
    letter, alter, rest = _root_of(sym)
    bass = None
    if '/' in rest:
        rest, bass = rest.split('/', 1)
    _, qual = parse_chord(sym)
    kind, text = QUAL_TO_KIND.get(qual, ('other', rest or 'maj'))

    h = ET.Element('harmony', {'print-frame': 'no'})
    r = ET.SubElement(h, 'root')
    ET.SubElement(r, 'root-step').text = letter
    if alter:
        ET.SubElement(r, 'root-alter').text = str(alter)
    ET.SubElement(h, 'kind', {'text': text}).text = kind
    if bass:
        bl, ba, _ = _root_of(bass)
        b = ET.SubElement(h, 'bass')
        ET.SubElement(b, 'bass-step').text = bl
        if ba:
            ET.SubElement(b, 'bass-alter').text = str(ba)
    return h

def _measure_el(n, bar, prev_chords, first):
    m = ET.Element('measure', {'number': str(n)})
    if first:
        at = ET.SubElement(m, 'attributes')
        ET.SubElement(at, 'divisions').text = str(DIVISIONS)
    chords = bar['chords']
    if chords == ['%'] or (not chords):
        chords = prev_chords                # expand repeat-bar for standalone XML
    if bar.get('rs'):
        bl = ET.SubElement(m, 'barline', {'location': 'left'})
        ET.SubElement(bl, 'bar-style').text = 'heavy-light'
        ET.SubElement(bl, 'repeat', {'direction': 'forward'})
    for sym in chords:
        m.append(_harmony_el(sym))
    note = ET.SubElement(m, 'note')
    ET.SubElement(note, 'rest')
    ET.SubElement(note, 'duration').text = str(WHOLE)
    ET.SubElement(note, 'type').text = 'whole'
    if bar.get('re'):
        bl = ET.SubElement(m, 'barline', {'location': 'right'})
        ET.SubElement(bl, 'bar-style').text = 'light-heavy'
        ET.SubElement(bl, 'repeat', {'direction': 'backward'})
    return m, chords

def _key_attributes(meta):
    at = ET.Element('attributes')
    ET.SubElement(at, 'divisions').text = str(DIVISIONS)
    if meta.get('key') in KEY_TO_FIFTHS:
        k = ET.SubElement(at, 'key')
        ET.SubElement(k, 'fifths').text = str(KEY_TO_FIFTHS[meta['key']])
        ET.SubElement(k, 'mode').text = 'major'
    t = ET.SubElement(at, 'time')
    ET.SubElement(t, 'beats').text = '4'
    ET.SubElement(t, 'beat-type').text = '4'
    c = ET.SubElement(at, 'clef')
    ET.SubElement(c, 'sign').text = 'G'
    ET.SubElement(c, 'line').text = '2'
    return at

def export_xml(pro_text):
    meta, sections = parse_pro(pro_text)
    score = ET.Element('score-partwise', {'version': '3.1'})
    work = ET.SubElement(score, 'work')
    ET.SubElement(work, 'work-title').text = meta.get('title', '')
    ident = ET.SubElement(score, 'identification')
    if meta.get('subtitle'):
        ET.SubElement(ident, 'creator', {'type': 'composer'}).text = meta['subtitle']
    enc = ET.SubElement(ident, 'encoding')
    ET.SubElement(enc, 'software').text = 'fret-glyphs'
    pl = ET.SubElement(score, 'part-list')
    sp = ET.SubElement(pl, 'score-part', {'id': 'P1'})
    ET.SubElement(sp, 'part-name').text = 'Lead sheet'
    part = ET.SubElement(score, 'part', {'id': 'P1'})

    n = 0
    prev = []
    for si, sec in enumerate(sections):
        for bi, bar in enumerate(sec['bars']):
            n += 1
            m, prev = _measure_el(n, bar, prev, first=(n == 1))
            if n == 1:
                m.insert(0, _key_attributes(meta))
                # remove the placeholder divisions-only attributes _measure_el added
                for at in m.findall('attributes')[1:]:
                    m.remove(at)
            if sec.get('label') and bi == 0:
                d = ET.Element('direction', {'placement': 'above'})
                dt = ET.SubElement(d, 'direction-type')
                ET.SubElement(dt, 'rehearsal').text = sec['label']
                m.insert(0, d)
            part.append(m)

    ET.indent(score, space='    ')
    body = ET.tostring(score, encoding='unicode')
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 3.1 '
            'Partwise//EN" "http://www.musicxml.org/dtds/partwise.dtd">\n'
            + body + '\n')


# ================================ CLI =======================================

def main():
    ap = argparse.ArgumentParser(
        prog='musicxml.py',
        description='Convert between MusicXML and .pro changes files. '
                    'Import maps <harmony> to chord symbols; export writes a '
                    'chord-only lead sheet. Stdlib only.')
    ap.add_argument('source', help='input .musicxml (import) or .pro (export)')
    ap.add_argument('-o', '--out', help='output file (default: stdout)')
    ap.add_argument('--export', action='store_true',
                    help='force export (.pro -> MusicXML); default is inferred '
                         'from the extension')
    a = ap.parse_args()

    src = open(a.source, encoding='utf-8').read() if a.export else a.source
    exporting = a.export or a.source.lower().endswith('.pro')

    if exporting:
        text = export_xml(open(a.source, encoding='utf-8').read())
        kind = 'MusicXML'
    else:
        meta, rows = import_xml(a.source)
        text = to_pro(meta, rows)
        kind = '.pro'

    if a.out:
        with open(a.out, 'w', encoding='utf-8') as f:
            f.write(text)
        print(f'wrote {a.out}  ({kind})')
    else:
        sys.stdout.write(text)


if __name__ == '__main__':
    main()
