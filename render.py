"""Shared glyph renderer. mode='tick' (fixed height, skips marked), 'stretch'
(height = true string span), or 'anchored' (tick geometry, endpoints drawn as
open/half/solid nodes + a diamond middle marking any two-fret stretch). All three
consume the same triple: code, strings, base fret — nothing is looked up."""
import math

INK="#171A16"; STROKE="#1B4DB3"; MUTE="#8A9184"; RULE="#D6DBCF"; ACC="#B0401F"
BG ="#EEF0EA"   # page colour; the open anchor knocks out against it

U    = 15.0   # px per string gap        (stretch mode)
TH   = 20.0   # half-height of a glyph   (tick mode)
CW   = 13.0   # px per fret column

# Anchored register. One outer radius AR specs every node, so open/half/solid/diamond
# share a silhouette and thus equal circle area. ARN is the ring's path radius (its
# stroke's outer edge lands on AR); ARd sizes the diamond to the same area.
AR=5.0; ASW=2.4; ARN=AR-ASW/2; ARd=AR*1.253

def _anc_ring(cx,cy,color,bg):
    return (f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{ARN:.2f}" '
            f'fill="{bg}" stroke="{color}" stroke-width="{ASW}"/>')
def _anc_solid(cx,cy,color,bg):
    return f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{AR:.2f}" fill="{color}"/>'
def _anc_half(cx,cy,color,bg):     # ring + filled lower semicircle to the outer edge
    return (_anc_ring(cx,cy,color,bg)
            + f'<path d="M {cx-AR:.1f} {cy:.1f} A {AR:.1f} {AR:.1f} 0 0 0 '
              f'{cx+AR:.1f} {cy:.1f} Z" fill="{color}"/>')
def _anc_diamond(cx,cy,color,bg):  # half-filled diamond: the two-fret-stretch middle
    return (f'<polygon points="{cx:.1f},{cy-ARd:.1f} {cx+ARd:.1f},{cy:.1f} '
            f'{cx:.1f},{cy+ARd:.1f} {cx-ARd:.1f},{cy:.1f}" '
            f'fill="{bg}" stroke="{color}" stroke-width="{ASW}" stroke-linejoin="miter"/>'
            f'<polygon points="{cx-ARd:.1f},{cy:.1f} {cx:.1f},{cy+ARd:.1f} '
            f'{cx+ARd:.1f},{cy:.1f}" fill="{color}"/>')

def glyph_height(strings, mode):
    return (max(strings)-min(strings))*U if mode=='stretch' else 2*TH

def glyph_width():
    return 2*CW

def draw_glyph(cx, ytop, code, strings, mode='tick', sw=4.2,
               color=STROKE, num=True, staff=None, bg=None):
    """ytop = y of the highest-pitch string. Returns SVG fragment."""
    if bg is None: bg = BG
    hi2lo = sorted(strings)                # string 1 = highest pitch
    top   = hi2lo[0]
    if mode=='stretch':
        ys = [ytop + (s-top)*U for s in hi2lo]
    else:
        ys = [ytop, ytop+TH, ytop+2*TH]
    xs = [cx + (int(code[i])-1)*CW for i in range(3)]
    s=[]
    if staff is None: staff = (mode=='stretch')
    if staff:
        for yy in [ytop + k*U for k in range(int((max(hi2lo)-top))+1)]:
            s.append(f'<line x1="{cx-CW-9}" y1="{yy:.1f}" x2="{cx+CW+9}" y2="{yy:.1f}" '
                     f'stroke="{RULE}" stroke-width="0.8"/>')
    d = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x,y in zip(xs,ys))
    s.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{sw}" '
             f'stroke-linecap="round" stroke-linejoin="round"/>')
    if mode in ('tick','anchored'):        # red slashes mark skipped strings
        for i in range(2):
            gap = hi2lo[i+1]-hi2lo[i]-1
            if gap<=0: continue
            (x1,y1),(x2,y2) = (xs[i],ys[i]),(xs[i+1],ys[i+1])
            mx,my = (x1+x2)/2,(y1+y2)/2
            dx,dy = x2-x1, y2-y1; n = math.hypot(dx,dy) or 1
            px,py = -dy/n, dx/n; L = 7.5
            for k in range(gap):
                off = (k-(gap-1)/2)*4.5
                ox,oy = mx+dx/n*off, my+dy/n*off
                s.append(f'<line x1="{ox-px*L:.1f}" y1="{oy-py*L:.1f}" '
                         f'x2="{ox+px*L:.1f}" y2="{oy+py*L:.1f}" '
                         f'stroke="{ACC}" stroke-width="2.4" stroke-linecap="round"/>')
    if mode=='anchored':                   # nodes: open=top, half=middle, solid=bottom
        dg = [int(code[i]) for i in range(3)]
        wide = abs(dg[0]-dg[1])>=2 or abs(dg[1]-dg[2])>=2     # a two-fret leg
        s.append(_anc_ring(xs[0], ys[0], color, bg))
        s.append((_anc_diamond if wide else _anc_half)(xs[1], ys[1], color, bg))
        s.append(_anc_solid(xs[2], ys[2], color, bg))
    if num:
        s.append(f'<text x="{cx-CW-15}" y="{ytop+4:.1f}" text-anchor="middle" '
                 f'font-family="ui-monospace,Menlo,monospace" font-size="12" '
                 f'font-weight="700" fill="{INK}">{top}</text>')
    return "\n".join(s)
