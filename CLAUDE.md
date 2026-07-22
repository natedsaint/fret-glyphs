# Project context

Design notes for anyone (human or Claude) picking this up. The README covers *what*
the tool does; this covers *why*, and what's still open.

## The core idea

The glyph is a **picture of the fret hand**, not a code for a chord quality. Nathan
chose this early over the alternative (shape = chord family, direction = alteration)
because a picture needs no decoding step when sight-reading. Everything follows from
that: the system says nothing about harmony, only about where fingers go.

Consequence worth remembering: the glyph cannot tell you which chord symbol it
satisfies. That link lives in the chart, next to the glyph.

## Why the 3x3 box

Nathan's insight, and it's what makes the system finite. Three strings, three frets,
one note per string (a horizontal line is impossible — a string can't sound two frets).
That's 27 raw, and 19 after normalising so the leftmost note sits at column 0.

19 is the whole alphabet, permanently. Under left-right mirroring the vertical line
maps to itself and the other 18 form 9 pairs, so it's really 10 things plus a flip
rule.

The code (three digits, fret offsets read highest string to lowest) *is* the shape.
There is deliberately no lookup table anywhere in this codebase — the SVG path is
generated from the digits.

## Decisions already made, and rejected alternatives

- **Nut left, neck running right.** Fixed. Everything breaks if this flips.
- **Fret span is not encoded in glyph geometry.** Considered and dropped: it forced the
  shape to carry three variables at once. (Also: a games patent covers a wave whose
  height encodes fret position, so it isn't free to use, and it's the weaker design.)
- **No B-string compensation flag.** Once the glyph is literally the fingering, a
  crossed shape just *looks* different — no flag needed. Cost is more shapes; that
  trade was accepted deliberately.
- **String set is not a 3-digit tag.** Top-string numeral plus tick (or stretch height)
  determines the set completely and is faster to write.
- **Two registers, one alphabet.** Typeset dot-contour for print, single-stroke cursive
  for handwriting — same code underneath, like block print vs cursive.
- **Repeats are not expanded before voicing.** Each written bar is voiced once so a
  repeated section is fingered identically. Don't "simplify" this away.

## Prior art (checked)

Nothing matching exists. Chord boxes are the standard and are the opposite design — a
full picture per chord, no compression. The closest relative in spirit is **Parsons
code** (1975), which throws away absolute pitch and keeps only melodic contour; this
does the same for a vertical voicing shape. Confirmed no ready-made glyph set to adopt.

## Findings from the worked example

- Mack the Knife uses only **5 of the 19 shapes**. The alphabet is over-provisioned,
  which is the right direction.
- The shout section (up a whole step) produces the **identical glyph sequence** with
  every anchor +2. This is the property the whole design bets on — if a change ever
  breaks it, the change is wrong.
- The chromatic m9 run is **one shape** with a walking anchor.
- Allowing all 20 string sets took hand travel from 10 frets to 0. Cost: 7 of 11
  chords become full three-fret stretches.
- Dm7 has **no voicing on strings 4-3-2 near 8th position** containing both guide
  tones. It's fine on 6-4-2. Not a bug — a real fact about that string set that the
  notation made visible.

## Open threads

- **Four-note voicings.** Would need a 4x3 box and a bigger alphabet. Not attempted.
- **The 8 stretch shapes have no handwriting forms yet.** They should fall out of the
  existing grammar as angular-belly-plus-flick or double-flick; unverified.
- **Chart import.** Everything is typed by hand. MusicXML would be the sane route;
  PDF means OMR and is out of scope.
- **`mack.pro` bar rhythm is a reconstruction**, not a transcription — inferred from a
  printed chart, including the assumption that the opening Bb6 is a four-bar vamp
  ahead of the sixteen-bar form. Verify against the real part before trusting it.
- **Alternate tunings** — change `OPEN` in `voice.py`.

## Code map

`voice.py` is the engine: fretboard model, shape enumeration, and a Viterbi pass
(`lead_free`) over every legal shape on all 20 string sets. `render.py` owns all glyph
drawing and the tick/stretch toggle — if a plate and the sheet ever disagree visually,
the cause is something bypassing `draw_glyph`. `chartparse.py` preserves structure.
`sheet.py` is layout plus CLI.

Layout gotcha, hit repeatedly: **derive SVG canvas height from content**, never
hardcode it. Row height depends on glyph mode, so a fixed height silently clips.
