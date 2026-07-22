# Fret-Hand Glyphs

A shorthand for writing guitar voicings as **shapes** rather than chord names, and a
tool that picks voicings for a set of changes by minimising hand movement.

Write your changes in a plain text file, run one command, get an SVG chart where every
chord carries a small glyph showing exactly how to finger it.

No dependencies. Python 3.8+, standard library only.

---

## Quick start

```bash
python3 sheet.py mack.pro
```

Writes `mack-tick.svg` next to the source. Open it in any browser.

```bash
python3 sheet.py mack.pro --both          # tick and stretch versions
python3 sheet.py mack.pro -m stretch -o chart.svg
python3 sheet.py mack.pro --home 5 --skip-pen -1.2   # open voicings, 5th position
```

---

## The notation

Every voicing is three notes, one per string, spanning at most three frets. That box
has exactly **19 possible shapes** after you slide it so the leftmost note sits at
column 0 — and 19 is the entire alphabet, permanently.

A written voicing is four things:

| part | what it says | example |
|---|---|---|
| **glyph** | the finger contour, drawn top string → bottom | `╲` |
| **numeral** | which string the top note is on | `2` |
| **tick / height** | which strings are skipped, if any | one red tick |
| **fret number** | where the shape starts | `8` (red) |

The glyph is drawn as a single pen stroke through the three notes, highest string
first. That is also its name: read the fret offsets top to bottom and you get a
three-digit **code** (`012`, `110`, `202`…). The code and the picture are the same
object, which is why nothing here needs a lookup table.

Because the code only describes fret offsets, it does not care *which* three strings
you use. All 20 string sets share the same 19 shapes.

### Two ways to draw a skipped string

- **tick** — glyph height is fixed; a red tick crosses the stroke wherever a string is
  skipped. Compact, uniform line height, fast to write by hand.
- **stretch** — the stroke spans the real strings, so the picture shows the reach
  directly and needs no extra marks. Unambiguous, but row height becomes variable.

Use `-m tick` or `-m stretch`. Same underlying data; only the drawing differs. For
close voicings stretch is often *shorter* than tick, since an adjacent set is only two
string-gaps tall.

See `reference/` for the full alphabet, the handwriting forms, and both string-set
styles.

---

## The changes file

```
{title: Mack the Knife}
{subtitle: arr. Tony Guerrero}
{key: Bb}
{tempo: 160}

{section: B - head}
|: Bb6 | % | Cm7 | % |
| F7 | % | Bb6 | % |
| Dm7 | Dbo7 | Cm7 | F7 |
| Cm7 | F7 | Bb6 | % :|
```

| syntax | meaning |
|---|---|
| `\| chord \|` | one bar |
| `\| Cm7 F7 \|` | two chords in a bar, split evenly |
| `%` | repeat the previous bar |
| `\|:` … `:\|` | repeat marks |
| `{section: name}` | starts a labelled section |
| `#` | comment |

Repeats are **not** expanded before voicing. Each written bar is voiced once, so a
repeated section is fingered identically both times through.

Chord symbols understood: `6`, `m7`, `m9`, `7`, `13`, `o7` (or `dim`), `m7b5`, `maj7`,
with `b`/`#` roots.

---

## How voicings get chosen

`voice.py` enumerates every legal three-note shape for each chord across all 20 string
sets, keeps only those containing both guide tones (3rd and 7th), then runs a Viterbi
pass over the whole tune to find the path with the least hand movement.

Four knobs:

| flag | default | effect |
|---|---|---|
| `--home` | 8.5 | preferred neck position, in frets |
| `--span` | 5.0 | how far a voicing may stray from home |
| `--switch-pen` | 3.0 | cost of changing string set — raise it for fewer crossings |
| `--skip-pen` | 0.25 | cost of skipping strings. `0` mixes; **negative prefers open voicings** |

`--skip-pen -1.2` is the interesting one: it turns close comping into spread
chord-melody voicings without moving the hand.

Rootless voicings are preferred automatically. A chord symbol printed in red on the
sheet means that voicing does contain its root.

---

## Files

| file | role |
|---|---|
| `sheet.py` | CLI and sheet layout |
| `voice.py` | fretboard model, shape enumeration, voice-leading search |
| `chartparse.py` | changes-file parser; preserves bars, sections, repeats |
| `render.py` | glyph drawing; the tick/stretch toggle lives here |
| `mack.pro` | worked example |
| `reference/` | the alphabet and notation plates |

Import it directly if you'd rather script it:

```python
from voice import lead_free
for sym, code, fret, roles, frets, strings in lead_free(['Dm7','G7','C6'], home=7):
    print(sym, code, fret, strings)
```

---

## Known limits

- **Three notes per voicing.** Four-note shapes would need a 4×3 box and a larger
  alphabet.
- **Standard tuning only** — change `OPEN` in `voice.py` for anything else.
- **No PDF or MusicXML import.** Changes are typed by hand. Reading engraved charts
  automatically is an OMR problem, well outside this tool.
- **The example file is a reconstruction.** The bar rhythm in `mack.pro` was inferred
  from a printed chart, including the assumption that the opening `Bb6` is a four-bar
  vamp before the sixteen-bar form. Correct it and re-run; voicings recompute.
