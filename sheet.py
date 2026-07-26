import sys, os, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from chartparse import parse, flatten
from voice import lead_free, strip_root_marker
from render import draw_glyph, glyph_height, CW, INK, STROKE, MUTE, RULE, ACC

BG="#EEF0EA"; W=820; L=52; R=W-52
PER=4                                    # bars per system

def repeat_dots(x, ytop, ybot, facing):
    dx = 7 if facing=='right' else -7
    ym=(ytop+ybot)/2
    return "".join(f'<circle cx="{x+dx:.1f}" cy="{ym+o:.1f}" r="2.6" fill="{INK}"/>'
                   for o in (-8,8))

def build(src, mode='tick', home=8.5, span=5.0, switch_pen=3.0, skip_pen=0.25):
    meta, secs = parse(src)
    flat = flatten(secs)
    res  = lead_free([f[3] for f in flat], home=home, span=span,
                     switch_pen=switch_pen, skip_pen=skip_pen)
    vox  = {(si,bi,ci): v for (si,bi,ci,_), v in zip(flat, res)}

    p=["__SVG__","__RECT__"]
    p.append(f'<text x="{L}" y="62" font-family="Helvetica Neue,Arial,sans-serif" font-size="30" '
             f'font-weight="700" fill="{INK}">{meta.get("title","")}</text>')
    bits=[meta.get("subtitle",""),
          f'key {meta["key"]}' if "key" in meta else "",
          f'q={meta["tempo"]}' if "tempo" in meta else "",
          f'{mode} mode']
    p.append(f'<text x="{L}" y="84" font-family="ui-monospace,Menlo,monospace" font-size="11.5" '
             f'letter-spacing="1" fill="{MUTE}">{"  \u00b7  ".join(b for b in bits if b)}</text>')
    p.append(f'<line x1="{L}" y1="100" x2="{R}" y2="100" stroke="{INK}" stroke-width="1.4"/>')

    y=134
    bw=(R-L)/PER
    for si,sec in enumerate(secs):
        p.append(f'<text x="{L}" y="{y:.0f}" font-family="ui-monospace,Menlo,monospace" '
                 f'font-size="11.5" letter-spacing="3" fill="{STROKE}">'
                 f'{sec["label"].upper()}</text>')
        y+=30
        bars=sec['bars']
        for i in range(0, len(bars), PER):
            chunk=bars[i:i+PER]
            hs=[]
            for j,bar in enumerate(chunk):
                for ci in range(len(bar['chords'])):
                    v=vox.get((si,i+j,ci))
                    if v: hs.append(glyph_height(v[5], mode))
            rh=max(hs) if hs else 40
            gtop=y+26                                   # glyph top baseline
            bot=gtop+rh+30
            # staff-ish frame
            for j in range(len(chunk)+1):
                x=L+j*bw
                p.append(f'<line x1="{x:.1f}" y1="{y+2:.0f}" x2="{x:.1f}" y2="{bot:.0f}" '
                         f'stroke="{RULE}" stroke-width="1.2"/>')
            for j,bar in enumerate(chunk):
                x0=L+j*bw
                if bar['rs']:
                    p.append(f'<line x1="{x0+2:.1f}" y1="{y+2:.0f}" x2="{x0+2:.1f}" y2="{bot:.0f}" '
                             f'stroke="{INK}" stroke-width="3.4"/>')
                    p.append(repeat_dots(x0+2, y+2, bot, 'right'))
                if bar['re']:
                    x1=x0+bw
                    p.append(f'<line x1="{x1-2:.1f}" y1="{y+2:.0f}" x2="{x1-2:.1f}" y2="{bot:.0f}" '
                             f'stroke="{INK}" stroke-width="3.4"/>')
                    p.append(repeat_dots(x1-2, y+2, bot, 'left'))
                n=len(bar['chords']) or 1
                for ci,sym in enumerate(bar['chords']):
                    cx=x0+bw*(ci+0.5)/n
                    v=vox.get((si,i+j,ci))
                    label,_=strip_root_marker(sym)          # hide any !/~ from the print
                    p.append(f'<text x="{cx:.1f}" y="{y+18:.0f}" text-anchor="middle" '
                             f'font-family="Helvetica Neue,Arial,sans-serif" font-size="13.5" '
                             f'font-weight="700" fill="{INK}">{label}</text>')
                    if not v: continue
                    _,cd,base,roles,fr,st=v
                    p.append(draw_glyph(cx, gtop, cd, st, mode=mode, sw=3.8))
                    p.append(f'<text x="{cx+CW+16:.1f}" y="{gtop+rh/2+5:.0f}" '
                             f'font-family="ui-monospace,Menlo,monospace" font-size="12" '
                             f'fill="{ACC}">{base}</text>')
                    p.append(f'<text x="{cx:.1f}" y="{bot-8:.0f}" text-anchor="middle" '
                             f'font-family="ui-monospace,Menlo,monospace" font-size="8.5" '
                             f'letter-spacing="0.5" fill="{MUTE}">'
                             f'{cd}\u00b7{"".join(map(str,sorted(st)))}</text>')
            y=bot+30
        y+=14

    b=[r[2] for r in res]
    trav=sum(abs(x-z) for x,z in zip(b,b[1:]))
    p.append(f'<line x1="{L}" y1="{y-12:.0f}" x2="{R}" y2="{y-12:.0f}" stroke="{INK}" stroke-width="1.2"/>')
    p.append(f'<text x="{L}" y="{y+12:.0f}" font-family="Helvetica Neue,Arial,sans-serif" '
             f'font-size="11" fill="{INK}">Glyph \u00b7 top-string numeral \u00b7 base fret (red). '
             f'Caption = code and string set. {len(res)} chords, {trav} frets of hand travel.</text>')
    p.append('</svg>')
    H=int(y+34)
    p[0]=f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
    p[1]=f'<rect width="{W}" height="{H}" fill="{BG}"/>'
    return "\n".join(p), H

def main():
    ap=argparse.ArgumentParser(
        prog='sheet.py',
        description='Render a changes file as a fret-hand glyph sheet (SVG).')
    ap.add_argument('source', help='input .pro changes file')
    ap.add_argument('-o','--out', help='output .svg (default: alongside source)')
    ap.add_argument('-m','--mode', choices=['tick','stretch','anchored'], default='tick',
                    help='glyph style (default: tick)')
    ap.add_argument('--both', action='store_true',
                    help='write both tick and stretch versions')
    ap.add_argument('--home', type=float, default=8.5,
                    help='preferred neck position, in frets (default: 8.5)')
    ap.add_argument('--span', type=float, default=5.0,
                    help='how far from home a voicing may stray (default: 5.0)')
    ap.add_argument('--switch-pen', type=float, default=3.0,
                    help='cost of changing string set (default: 3.0)')
    ap.add_argument('--skip-pen', type=float, default=0.25,
                    help='cost of skipping strings; negative prefers open '
                         'voicings (default: 0.25)')
    a=ap.parse_args()

    src=open(a.source, encoding='utf-8').read()
    stem=os.path.splitext(a.out or a.source)[0]
    modes=['tick','stretch'] if a.both else [a.mode]
    for mode in modes:
        svg,H=build(src, mode=mode, home=a.home, span=a.span,
                    switch_pen=a.switch_pen, skip_pen=a.skip_pen)
        path = a.out if (a.out and not a.both) else f'{stem}-{mode}.svg'
        # utf-8 explicitly: the SVG has non-ASCII (·), and the platform default
        # (cp1252 on Windows) writes bytes a browser can't parse as UTF-8.
        with open(path,'w',encoding='utf-8') as f: f.write(svg)
        print(f'wrote {path}  ({H}px tall)')

if __name__=='__main__':
    main()
