"""Core-model tests: the chart parser and the chord grammar.
Run from the repo root:  python -m unittest discover tests"""
import os, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from chartparse import parse, flatten
from voice import parse as parse_chord, shape_of, code, TRIADS


class ChartParse(unittest.TestCase):
    def test_metadata(self):
        meta, _ = parse('{title: Blue}\n{key: Bb}\n{tempo: 160}\n| Bb |')
        self.assertEqual(meta['title'], 'Blue')
        self.assertEqual(meta['key'], 'Bb')
        self.assertEqual(meta['tempo'], '160')

    def test_percent_repeats_previous_bar(self):
        _, secs = parse('| Bb6 | % | Cm7 | % |')
        chords = [b['chords'] for b in secs[0]['bars']]
        self.assertEqual(chords, [['Bb6'], ['Bb6'], ['Cm7'], ['Cm7']])

    def test_multiple_chords_in_a_bar(self):
        _, secs = parse('| Dm7 G7 |')
        self.assertEqual(secs[0]['bars'][0]['chords'], ['Dm7', 'G7'])

    def test_repeat_marks_on_line_edges(self):
        _, secs = parse('|: Bb6 | Cm7 :|')
        bars = secs[0]['bars']
        self.assertTrue(bars[0]['rs'])
        self.assertTrue(bars[-1]['re'])
        self.assertFalse(bars[0]['re'])

    def test_sections_kept_in_order(self):
        _, secs = parse('{section: A}\n| Bb |\n{section: B}\n| Cm7 |')
        self.assertEqual([s['label'] for s in secs], ['A', 'B'])

    def test_flatten_indices(self):
        _, secs = parse('| Dm7 G7 | Cm7 |')
        self.assertEqual(flatten(secs),
                         [(0, 0, 0, 'Dm7'), (0, 0, 1, 'G7'), (0, 1, 0, 'Cm7')])


class ChordGrammar(unittest.TestCase):
    def test_qualities(self):
        cases = {'Bb': 'maj', 'Bbm': 'min', 'Cm7': 'm7', 'F7': '7',
                 'Bb6': '6', 'Bbmaj7': 'maj7', 'Bbo7': 'o7', 'Cm7b5': 'm7b5',
                 'Dm9': 'm9', 'G13': '13'}
        for sym, qual in cases.items():
            self.assertEqual(parse_chord(sym)[1], qual, sym)

    def test_bare_root_is_major_triad_not_sixth(self):
        pc, qual = parse_chord('Bb')
        self.assertEqual(qual, 'maj')
        self.assertIn(qual, TRIADS)

    def test_root_pitch_classes(self):
        self.assertEqual(parse_chord('C')[0], 0)
        self.assertEqual(parse_chord('Bb6')[0], 10)
        self.assertEqual(parse_chord('F#7')[0], 6)

    def test_markers_are_stripped_before_parsing(self):
        self.assertEqual(parse_chord('Bb6!'), parse_chord('Bb6'))
        self.assertEqual(parse_chord('Cm7~'), parse_chord('Cm7'))


class ShapeCode(unittest.TestCase):
    def test_code_normalises_to_leftmost_zero(self):
        self.assertEqual(code([8, 7, 6]), ('210', 6))    # highest string first
        self.assertEqual(code([6, 7, 8]), ('012', 6))

    def test_shape_of_reads_highest_string_first(self):
        # strings 4,3,2 at frets 8,7,6 -> read hi(2)->lo(4): 6,7,8 -> '012'
        cd, base = shape_of((8, 7, 6), (4, 3, 2))
        self.assertEqual((cd, base), ('012', 6))


if __name__ == '__main__':
    unittest.main()
