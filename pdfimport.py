"""Import chord symbols from an engraved PDF into a .pro changes file.

OPTIONAL tool, deliberately NOT part of the stdlib-only core (see README's
"no dependencies" promise): it needs PyMuPDF. Install with `pip install pymupdf`.
The render path (sheet.py) never imports this.

Why this is tractable at all (cf. CLAUDE.md "Chart import" open thread): in an
engraved chart the chord symbols live in their OWN font -- Finale's
RepriseChordsStd, Sibelius equivalents, etc. So we filter to just those spans
and throw every notehead, clef and staff line away without doing any note
reading (OMR). What's left is layout, not recognition:

  systems  <- cluster horizontal staff lines by y
  bars     <- vertical barline segments within each system
  chords   <- chord-font spans, bucketed into measures by x
  sections <- rehearsal marks ([A], [B], ...)

Every token is checked against a chord grammar; anything that fails (a two-chord
span, a stray font glyph) is emitted as a flagged `#?` comment rather than
silently trusted -- the same safety net the rest of the pipeline relies on.

Scanned / image-only PDFs are refused: that is OCR/OMR territory, out of scope.

Usage:
    python pdfimport.py "chart.pdf"            # -> stdout
    python pdfimport.py "chart.pdf" -o out.pro
"""
import sys, os, re, argparse

# Chord symbols use private-font glyphs for accidentals; map them back to ASCII.
# (Sharp already comes through as '#'/U+0023 in these fonts, so only flat needs it.)
GLYPH = {0x00a8: "b"}

CHORD_FONT     = "Chord"       # substring of the accidental-bearing chord font
REHEARSAL_FONT = "Rehearsal"   # substring of the rehearsal-mark font
TITLE_FONT     = "Title"

# Grammar just strict enough to catch garbage, loose enough for real jazz symbols.
CHORD_RE = re.compile(
    r'^[A-G](b|#)?'
    r'(m|maj|min|dim|o|\+|aug|sus|add|M)*'
    r'\d*'
    r'(\((?:#|b|add|sus|no)?\d+\))*'
    r'(/[A-G](b|#)?)?$'
)

PAD = 12.0   # a chord symbol printed this many px left of a barline still
             # belongs to the measure that barline opens.


def _decode(raw):
    return "".join(GLYPH.get(ord(c), c) for c in raw)


def _cluster(vals, tol):
    vals = sorted(vals)
    if not vals:
        return []
    groups = [[vals[0]]]
    for v in vals[1:]:
        if v - groups[-1][-1] <= tol:
            groups[-1].append(v)
        else:
            groups.append([v])
    return [sum(g) / len(g) for g in groups]


def _page_geometry(page):
    """Return (systems, vbars) for one page.

    systems: list of (y0, y1, x0, x1) staff-line bounding bands, top to bottom.
    vbars:   list of (x, y0, y1) vertical barline segments.
    """
    hlines = []   # (y, x0, x1)
    vbars  = []   # (x, y0, y1)
    for dr in page.get_drawings():
        for it in dr["items"]:
            if it[0] != "l":
                continue
            p1, p2 = it[1], it[2]
            if abs(p1.y - p2.y) < 1 and abs(p1.x - p2.x) > 50:
                hlines.append(((p1.y + p2.y) / 2, min(p1.x, p2.x), max(p1.x, p2.x)))
            elif abs(p1.x - p2.x) < 1 and abs(p1.y - p2.y) > 10:
                x = (p1.x + p2.x) / 2
                vbars.append((x, min(p1.y, p2.y), max(p1.y, p2.y)))
    hlines.sort()
    systems = []
    if hlines:
        cur = [hlines[0]]
        for h in hlines[1:]:
            if h[0] - cur[-1][0] <= 10:      # same 5-line system
                cur.append(h)
            else:
                ys = [c[0] for c in cur]
                systems.append((min(ys), max(ys), min(c[1] for c in cur), max(c[2] for c in cur)))
                cur = [h]
        ys = [c[0] for c in cur]
        systems.append((min(ys), max(ys), min(c[1] for c in cur), max(c[2] for c in cur)))
    return systems, vbars


def _spans(page, font_sub):
    out = []
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                if font_sub in s["font"]:
                    out.append((s["bbox"][0], s["bbox"][1], _decode(s["text"]).strip()))
    return out


def _chord_marks(page):
    """Chord symbols with a TRUE per-symbol x, taken from glyph positions.

    Finale packs several chords into one text run ("Dm9 Ebm9"); a span's start
    x then belongs only to its first chord. Splitting the run on whitespace and
    reading each fragment's first-glyph x keeps a chord that begins just past a
    barline from being dragged into the previous measure. Uses rawdict for the
    per-character boxes."""
    out = []
    for b in page.get_text("rawdict")["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                if CHORD_FONT not in s["font"]:
                    continue
                y = s["bbox"][1]
                cur, x0 = "", None
                for c in s["chars"]:
                    ch = _decode(c["c"])
                    if ch.isspace():
                        if cur:
                            out.append((x0, y, cur))
                        cur, x0 = "", None
                    else:
                        if not cur:
                            x0 = c["bbox"][0]
                        cur += ch
                if cur:
                    out.append((x0, y, cur))
    return out


def _band_for(y, systems):
    """A chord/mark sits ABOVE its staff: first system whose top is >= y."""
    for i, sys_ in enumerate(systems):
        if sys_[0] >= y - 4:
            return i
    return len(systems) - 1


def extract(path):
    """Return (meta, rows). rows: list of (section|None, [cells]).
    Each cell is a chord string, '%' for an empty measure, or ('BAD', raw)."""
    import fitz
    doc = fitz.open(path)

    # --- tier guard: chords must exist as real text ---------------------
    total_chords = sum(len(_chord_marks(p)) for p in doc)
    if total_chords == 0:
        raise SystemExit(
            "no chord-font text found. This looks like a scan or an image-only "
            "PDF; reading it needs OCR/OMR, which is out of scope. (If it IS a "
            "digital chart, the chord font name may differ -- check "
            "page.get_fonts() and adjust CHORD_FONT.)")

    meta = {}
    rows = []
    for page in doc:
        systems, vbars = _page_geometry(page)
        if not systems:
            continue
        chords    = _chord_marks(page)
        rehears   = _spans(page, REHEARSAL_FONT)
        if not meta.get("title"):
            for _, _, t in _spans(page, TITLE_FONT):
                if t:
                    meta["title"] = t
                    break
        for _, _, t in _spans(page, "Script") + _spans(page, "Text"):
            m = re.search(r'=\s*(\d{2,3})', t)          # tempo "q = 160"
            if m and "tempo" not in meta:
                meta["tempo"] = m.group(1)

        by_band = {i: [] for i in range(len(systems))}
        rh_band = {i: [] for i in range(len(systems))}
        for x, y, c in chords:
            if c:
                by_band[_band_for(y, systems)].append((x, c))
        for x, y, t in rehears:
            rh_band[_band_for(y, systems)].append(t.strip("[]"))

        for i, (y0, y1, sx0, sx1) in enumerate(systems):
            label = " ".join(t for t in rh_band[i] if t) or None
            # A real barline spans the whole staff (top line to bottom line);
            # rhythm-slash stems and sub-staff ticks do not, so require the
            # segment to reach from near y0 to near y1.
            bars = _cluster([x for (x, a, b) in vbars
                             if a <= y0 + 4 and b >= y1 - 4], 6)
            bounds = sorted({round(sx0)} | {round(b) for b in bars} | {round(sx1)})
            cs = sorted(by_band[i])
            cells = _assign(cs, bounds)
            rows.append((label, cells))
    return meta, rows


def _assign(chords, bounds):
    """Bucket (x, chord) pairs into measures delimited by `bounds` (x-cuts).
    Chords printed just left of a barline (within PAD) snap to the next measure."""
    if len(bounds) < 2:
        return [" ".join(c for _, c in chords)] if chords else []
    cells = []
    for i in range(len(bounds) - 1):
        lo, hi = bounds[i] - PAD, bounds[i + 1] - PAD
        inbar = [c for (x, c) in chords if lo <= x < hi]
        if inbar:
            cells.append(" ".join(inbar))
        else:
            cells.append("%" if cells else "")     # empty measure repeats prev
    return cells


def to_pro(meta, rows):
    out = []
    if meta.get("title"):
        out.append(f'{{title: {meta["title"]}}}')
    if meta.get("tempo"):
        out.append(f'{{tempo: {meta["tempo"]}}}')
    out.append("")
    out.append("# Imported by pdfimport.py -- VERIFY before trusting.")
    out.append("# Repeats/endings are NOT recovered; empty measures became '%'.")
    out.append("# Lines flagged '#?' had a token that failed the chord grammar.")
    out.append("")
    for label, cells in rows:
        if label:
            out.append("")
            out.append(f'{{section: {label}}}')
        if not cells:
            continue
        bad = False
        clean = []
        for cell in cells:
            toks = cell.split()
            for t in toks:
                if t and t != "%" and not CHORD_RE.match(t):
                    bad = True
            clean.append(cell if cell else " ")
        line = "| " + " | ".join(clean) + " |"
        out.append(("#? " + line) if bad else line)
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(
        prog="pdfimport.py",
        description="Import chord symbols from an engraved PDF into a .pro file. "
                    "Needs PyMuPDF (pip install pymupdf). Digital charts only; "
                    "scans are refused.")
    ap.add_argument("pdf", help="input engraved chord chart (.pdf)")
    ap.add_argument("-o", "--out", help="output .pro (default: stdout)")
    a = ap.parse_args()

    try:
        import fitz  # noqa: F401
    except ImportError:
        raise SystemExit("pdfimport needs PyMuPDF. Install it: pip install pymupdf")

    meta, rows = extract(a.pdf)
    text = to_pro(meta, rows)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text)
        n = sum(1 for _, cells in rows for c in cells if c and c != "%")
        print(f"wrote {a.out}  ({n} measures with chords across {len(rows)} systems)")
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
