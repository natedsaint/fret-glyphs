"""Fret-hand glyph engine: chord symbol -> 3x3 normalized shape code, with voice leading."""
from itertools import product

NAMES = ['C','Db','D','Eb','E','F','Gb','G','Ab','A','Bb','B']
PC = {n:i for i,n in enumerate(NAMES)}
PC.update({'C#':1,'D#':3,'F#':6,'G#':8,'A#':10,'Cb':11,'B#':0})

# open-string pitch classes, string 6 -> 1
OPEN = {6:PC['E'],5:PC['A'],4:PC['D'],3:PC['G'],2:PC['B'],1:PC['E']}
SETS = {'654':(6,5,4),'543':(5,4,3),'432':(4,3,2),'321':(3,2,1)}

# quality -> {interval: role}; roles: R root, 3 third, 7 seventh-ish, x color
QUAL = {
    '6'   : {0:'R',4:'3',7:'5',9:'7'},          # 6th functions as the 7th-slot guide tone
    'm7'  : {0:'R',3:'3',7:'5',10:'7'},
    'm9'  : {0:'R',3:'3',7:'5',10:'7',2:'x'},
    '7'   : {0:'R',4:'3',7:'5',10:'7',2:'x'},
    '13'  : {0:'R',4:'3',10:'7',2:'x',9:'x'},
    'o7'  : {0:'R',3:'3',6:'5',9:'7'},
    'm7b5': {0:'R',3:'3',6:'5',10:'7'},
    'maj7': {0:'R',4:'3',7:'5',11:'7'},
}

def parse(sym):
    sym = sym.strip()
    i = 2 if len(sym) > 1 and sym[1] in 'b#' else 1
    root, rest = sym[:i], sym[i:]
    rest = rest.replace('\u00b0','o').replace('dim','o')
    for q in ('maj7','m7b5','m9','m7','13','o7','7','6'):
        if rest.startswith(q):
            return PC[root], q
    return PC[root], '6' if rest == '' else 'm7'

def voicings(root, qual, strings, fmin=1, fmax=15):
    """All 3-note, one-note-per-string, <=3-fret-span shapes matching the chord."""
    tones = QUAL[qual]
    out = []
    for frets in product(range(fmin, fmax+1), repeat=3):
        if max(frets) - min(frets) > 2:
            continue
        roles = []
        for s, f in zip(strings, frets):
            iv = ((OPEN[s] + f) - root) % 12
            if iv not in tones:
                break
            roles.append(tones[iv])
        else:
            if '3' not in roles or '7' not in roles:   # guide tones mandatory
                continue
            if len(set(roles)) < 3:                    # no doubled roles
                continue
            out.append((frets, roles))
    return out

def code(frets_hi_to_lo):
    b = min(frets_hi_to_lo)
    return ''.join(str(f-b) for f in frets_hi_to_lo), b

def shape_of(frets, strings):
    """Return (code, base_fret) reading HIGHEST string first."""
    pairs = sorted(zip(strings, frets))          # string 1 = highest pitch
    hi_to_lo = [f for _, f in pairs]
    return code(hi_to_lo)

def cost(prev, cur, root_penalty=3.0, home=None):
    c = 0.0
    if prev is not None:
        c += sum(abs(a-b) for a, b in zip(prev, cur)) * 2.0   # voice movement
    if home is not None:
        c += abs(sum(cur)/3 - home) * 0.6                     # stay in region
    return c

def lead(chart, strings, home=7):
    """Greedy-with-lookahead path through the changes."""
    prev, out = None, []
    for sym in chart:
        r, q = parse(sym)
        cands = voicings(r, q, strings)
        if not cands:
            out.append((sym, None, None, None)); continue
        scored = []
        for frets, roles in cands:
            pen = 3.0 if 'R' in roles else 0.0        # prefer rootless
            scored.append((cost(prev, frets, home=home) + pen, frets, roles))
        scored.sort(key=lambda t: t[0])
        _, frets, roles = scored[0]
        cd, base = shape_of(frets, strings)
        out.append((sym, cd, base, roles))
        prev = frets
    return out

def lead_dp(chart, strings, home=7, start=None):
    """Viterbi: globally minimal voice movement across the whole form."""
    layers = []
    for sym in chart:
        r, q = parse(sym)
        cands = voicings(r, q, strings)
        cands = [(f, ro) for f, ro in cands if abs(sum(f)/3 - home) <= 3.5]
        layers.append((sym, cands))
    INF = float('inf')
    best = [{} for _ in layers]
    for i, (sym, cands) in enumerate(layers):
        for j, (frets, roles) in enumerate(cands):
            pen = 2.5 if 'R' in roles else 0.0
            pen += abs(sum(frets)/3 - home) * 0.35
            if i == 0:
                c = pen if start is None else pen + sum(abs(a-b) for a,b in zip(start,frets))*2
                best[i][j] = (c, None)
            else:
                bc, bp = INF, None
                for k, (pf, _) in enumerate(layers[i-1][1]):
                    if k not in best[i-1]: continue
                    c = best[i-1][k][0] + sum(abs(a-b) for a,b in zip(pf,frets))*2.0
                    if c < bc: bc, bp = c, k
                best[i][j] = (bc + pen, bp)
    # backtrack
    out, k = [], min(best[-1], key=lambda x: best[-1][x][0])
    for i in range(len(layers)-1, -1, -1):
        sym, cands = layers[i]
        frets, roles = cands[k]
        cd, base = shape_of(frets, strings)
        out.append((sym, cd, base, roles, frets))
        k = best[i][k][1]
    return out[::-1]

from itertools import combinations
ALL_SETS = [tuple(sorted(c, reverse=True)) for c in combinations([6,5,4,3,2,1],3)]

def lead_free(chart, home=7.5, span=3.5, switch_pen=1.2, prefer=None, skip_pen=0.25):
    """DP over (string set, fretting). State includes the string set, so the hand
    may move to a skipped set when that keeps the position still."""
    layers=[]
    for sym in chart:
        r,q = parse(sym)
        cands=[]
        for st in ALL_SETS:
            if prefer and st not in prefer: continue
            for frets,roles in voicings(r,q,st):
                if abs(sum(frets)/3 - home) <= span:
                    cands.append((st,frets,roles))
        layers.append((sym,cands))
    INF=float('inf'); best=[{} for _ in layers]
    for i,(sym,cands) in enumerate(layers):
        for j,(st,frets,roles) in enumerate(cands):
            pen = 2.5 if 'R' in roles else 0.0
            pen += abs(sum(frets)/3 - home)*0.35
            pen += (st[0]-st[2]-2)*skip_pen      # cost (or reward) for wide skips
            if i==0:
                best[i][j]=(pen,None)
            else:
                bc,bp=INF,None
                for k,(pst,pf,_) in enumerate(layers[i-1][1]):
                    if k not in best[i-1]: continue
                    move = abs(min(pf)-min(frets))*2.5           # hand position shift
                    move += 0 if pst==st else switch_pen
                    c=best[i-1][k][0]+move
                    if c<bc: bc,bp=c,k
                best[i][j]=(bc+pen,bp)
    out,k=[],min(best[-1],key=lambda x:best[-1][x][0])
    for i in range(len(layers)-1,-1,-1):
        sym,cands=layers[i]; st,frets,roles=cands[k]
        cd,base=shape_of(frets,st)
        out.append((sym,cd,base,roles,frets,st)); k=best[i][k][1]
    return out[::-1]
