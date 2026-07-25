"""Regenerate reference/05-anchored.svg straight from the engine — every glyph
comes out of render.draw_glyph in 'anchored' mode, so the plate can never drift
from what the sheet draws. Run from the repo root: python scripts/alphabet_plate.py"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from render import draw_glyph, BG, INK, STROKE, MUTE, TH, CW

def family(c):
    a,b,d=int(c[0]),int(c[1]),int(c[2])
    if a==b==d: return 'stem'
    if a==d and b!=a: return 'chevron'
    if a==b or b==d: return 'flick'
    if (a<b<d) or (a>b>d): return 'slant'
    return 'zigzag'

ORDER=['000','010','101','020','202','012','210','001','110','100',
       '011','200','022','002','220','021','201','102','120']
FAMS=[('stem','STEM'),('chevron','CHEVRON'),('flick','FLICK'),
      ('slant','SLANT'),('zigzag','ZIGZAG')]
groups={}
for c in ORDER: groups.setdefault(family(c),[]).append(c)

WIDTH=760; MARGIN=56; PITCH=78; GH=2*TH        # glyph height (anchored == tick)
body=[]; y=140
for key,label in FAMS:
    body.append(f'<text x="{MARGIN}" y="{y}" font-family="ui-monospace,Menlo,monospace" '
                f'font-size="12" letter-spacing="3" fill="{STROKE}">{label}</text>')
    y+=22; rowtop=y; x=MARGIN+8+CW              # +CW: draw_glyph centres on cx
    for c in groups[key]:
        body.append(draw_glyph(x, rowtop, c, (1,2,3), mode='anchored',
                               sw=3.4, num=False))
        body.append(f'<text x="{x:.0f}" y="{rowtop+GH+22:.0f}" text-anchor="middle" '
                    f'font-family="ui-monospace,Menlo,monospace" font-size="12.5" '
                    f'letter-spacing="2" fill="{INK}">{c}</text>')
        x+=PITCH
    y=rowtop+GH+34+14
H=int(y+20)

head=[f'<rect width="{WIDTH}" height="{H}" fill="{BG}"/>',
      f'<text x="{MARGIN}" y="66" font-family="Helvetica Neue,Arial,sans-serif" '
      f'font-size="30" font-weight="700" letter-spacing="1" fill="{INK}">THE HAND</text>',
      f'<text x="{MARGIN}" y="90" font-family="ui-monospace,Menlo,monospace" font-size="12.5" '
      f'letter-spacing="1" fill="{MUTE}">anchored register · open=top string · '
      f'half=middle · solid=bottom · diamond=two-fret stretch</text>',
      f'<line x1="{MARGIN}" y1="108" x2="{WIDTH-MARGIN}" y2="108" stroke="{INK}" stroke-width="1.4"/>']

svg=(f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{H}" '
     f'viewBox="0 0 {WIDTH} {H}">\n'+"\n".join(head+body)+"\n</svg>\n")
out=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 'reference','05-anchored.svg')
open(out,'w',encoding='utf-8').write(svg)
print('wrote', out, H)
