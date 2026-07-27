"""Tests for the MusicXML <-> .pro bridge. Stdlib unittest -- no pytest.
Run from the repo root:  python -m unittest discover tests"""
import os, sys, unittest
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import musicxml
from chartparse import parse as parse_pro, flatten
from voice import parse as parse_chord

BLUES = os.path.join(ROOT, 'blues.musicxml')
MACK  = os.path.join(ROOT, 'mack.pro')


def _harmony(step, kind, text=None, alter=None, bass=None, degree=False):
    h = ET.Element('harmony')
    r = ET.SubElement(h, 'root')
    ET.SubElement(r, 'root-step').text = step
    if alter is not None:
        ET.SubElement(r, 'root-alter').text = str(alter)
    k = ET.SubElement(h, 'kind'); k.text = kind
    if text is not None:
        k.set('text', text)
    if degree:
        ET.SubElement(h, 'degree')
    if bass:
        b = ET.SubElement(h, 'bass')
        ET.SubElement(b, 'bass-step').text = bass
    return h


class ImportBlues(unittest.TestCase):
    """The real iReal Pro export -- a 12-bar blues in A, all dominant 7ths."""
    @classmethod
    def setUpClass(cls):
        cls.meta, cls.rows = musicxml.import_xml(BLUES)

    def test_meta(self):
        self.assertEqual(self.meta['title'], 'Blues - Simple')
        self.assertEqual(self.meta['subtitle'], 'Exercise')
        self.assertEqual(self.meta['key'], 'A')          # fifths=3 -> A major

    def test_chord_sequence(self):
        cells = [r['cell'] for r in self.rows]
        self.assertEqual(cells, ['A7', 'A7', 'A7', 'A7',
                                 'D7', 'D7', 'A7', 'A7',
                                 'E7', 'D7', 'A7', 'A7'])

    def test_nothing_flagged(self):
        self.assertTrue(all(r['ok'] for r in self.rows))

    def test_system_breaks(self):                        # bars 1,5,9 -> 4-bar rows
        self.assertEqual([i for i, r in enumerate(self.rows) if r['new_sys']],
                         [0, 4, 8])

    def test_to_pro_is_parseable(self):
        pro = musicxml.to_pro(self.meta, self.rows)
        _, secs = parse_pro(pro)
        syms = [s for *_, s in flatten(secs)]
        self.assertEqual(syms.count('A7'), 8)            # 4 + 2 + 2 across the form
        self.assertNotIn('#?', pro)                      # clean chart, no flags


class SymbolMapping(unittest.TestCase):
    def test_clean_kinds(self):
        self.assertEqual(musicxml._symbol(_harmony('C', 'minor-seventh')), ('Cm7', True))
        self.assertEqual(musicxml._symbol(_harmony('A', 'dominant')), ('A7', True))
        self.assertEqual(musicxml._symbol(_harmony('E', 'major-seventh')), ('Emaj7', True))

    def test_root_accidentals(self):
        self.assertEqual(musicxml._symbol(_harmony('B', 'dominant', alter=-1))[0], 'Bb7')
        self.assertEqual(musicxml._symbol(_harmony('F', 'minor-seventh', alter=1))[0], 'F#m7')

    def test_every_mapped_kind_parses_to_a_quality(self):
        # a reconstructed clean symbol must survive the chord grammar
        for kind, suffix in musicxml.KIND_TO_SUFFIX.items():
            sym, ok = musicxml._symbol(_harmony('C', kind))
            self.assertTrue(ok, kind)
            self.assertIsNotNone(parse_chord(sym)[1], sym)

    def test_unsupported_is_flagged_but_labelled(self):
        for h, expect in [
            (_harmony('D', 'minor-sixth', text='m6'), 'Dm6'),
            (_harmony('G', 'suspended-fourth', text='sus'), 'Gsus'),
            (_harmony('C', 'dominant', text='7', bass='E'), 'C7/E'),   # slash bass
            (_harmony('C', 'dominant', text='7b9', degree=True), 'C7b9'),
        ]:
            sym, ok = musicxml._symbol(h)
            self.assertEqual(sym, expect)
            self.assertFalse(ok, expect)


class RoundTrip(unittest.TestCase):
    def _reimport(self, xml_text):
        return musicxml.import_score(ET.fromstring(xml_text))

    def test_blues_content_stable(self):
        meta, rows = musicxml.import_xml(BLUES)
        xml = musicxml.export_xml(musicxml.to_pro(meta, rows))
        _, rows2 = self._reimport(xml)
        self.assertEqual([r['cell'] for r in rows2],
                         [r['cell'] for r in rows])

    def test_blues_system_breaks_survive(self):
        # export mirrors sheet.py's 4-bar rows, reproducing iReal's own breaks
        meta, rows = musicxml.import_xml(BLUES)
        xml = musicxml.export_xml(musicxml.to_pro(meta, rows))
        _, rows2 = self._reimport(xml)
        self.assertEqual([i for i, r in enumerate(rows2) if r['new_sys']], [0, 4, 8])

    def test_mack_repeats_and_sections_survive(self):
        with open(MACK, encoding='utf-8') as f:
            xml = musicxml.export_xml(f.read())
        meta2, rows2 = self._reimport(xml)
        self.assertTrue(any(r['rs'] for r in rows2), 'a repeat-start should survive')
        self.assertTrue(any(r['re'] for r in rows2), 'a repeat-end should survive')
        self.assertTrue(any(r['label'] for r in rows2), 'sections should survive')

    def test_export_is_well_formed_with_harmony(self):
        xml = musicxml.export_xml('{title: X}\n{key: Bb}\n| Bb6 | Cm7 |')
        root = ET.fromstring(xml)                         # raises if malformed
        kinds = [k.text for k in root.iter('kind')]
        self.assertEqual(kinds, ['major-sixth', 'minor-seventh'])
        self.assertEqual(root.findtext('work/work-title'), 'X')


class Endings(unittest.TestCase):
    PRO = ('|: A7 | D7 |\n'
           '{ending: 1}\n| A7 :|\n'
           '{ending: 2}\n| E7 |\n')

    def test_pro_model_carries_endings(self):
        _, secs = parse_pro(self.PRO)
        bars = secs[0]['bars']
        self.assertEqual(bars[2]['ending'], 1)
        self.assertTrue(bars[2]['re'])                   # 1st ending loops back
        self.assertEqual(bars[3]['ending'], 2)

    def test_export_writes_ending_brackets(self):
        root = ET.fromstring(musicxml.export_xml(self.PRO))
        starts = sorted({e.get('number') for e in root.iter('ending')
                         if e.get('type') == 'start'})
        self.assertEqual(starts, ['1', '2'])

    def test_roundtrip_preserves_endings(self):
        _, rows = musicxml.import_score(ET.fromstring(musicxml.export_xml(self.PRO)))
        self.assertEqual([r['ending'] for r in rows if r['ending']], [1, 2])
        self.assertTrue(next(r for r in rows if r['ending'] == 1)['re'])
        pro = musicxml.to_pro({}, rows)
        self.assertIn('{ending: 1}', pro)
        self.assertIn('{ending: 2}', pro)


if __name__ == '__main__':
    unittest.main()
