"""Frozen family generators from BOUNDARY100 (21638f008f8)."""
import benchmark as b

def generate(rng, f, i):
    n=[48,64,80,96,120,144,168,192,240,300][i]
    if f=='random3':
        return n,b.random3(rng,list(range(1,n+1)),round(n*4.26))
    if f=='random4':
        return n,[tuple(v*rng.choice([-1,1]) for v in rng.sample(range(1,n+1),4)) for _ in range(round(n*9.75))]
    if f=='mixed-planted':
        bits={v:bool(rng.getrandbits(1)) for v in range(1,n+1)}
        cs=[]
        while len(cs)<5*n:
            k=rng.choice([2,3,3,4,5])
            c=tuple(v*rng.choice([-1,1]) for v in rng.sample(range(1,n+1),k))
            if any(bits[abs(l)]==(l>0) for l in c):cs.append(c)
        return n,cs
    if f=='nae3':
        cs=[]
        for _ in range(round(n*2.1)):
            c=tuple(v*rng.choice([-1,1]) for v in rng.sample(range(1,n+1),3))
            cs.extend([c,tuple(-l for l in c)])
        return n,cs
    if f=='tseitin':
        # Cubic graph: cycle plus random nonadjacent perfect matching.
        vcount=max(12,n//3*2)
        edges=[(j,(j+1)%vcount) for j in range(vcount)]
        while True:
            perm=list(range(vcount));rng.shuffle(perm)
            pairs=list(zip(perm[::2],perm[1::2]))
            if all((a-b)%vcount not in (1,vcount-1) for a,b in pairs):break
        edges+=pairs
        inc=[[] for _ in range(vcount)]
        for k,(a,c) in enumerate(edges,1):inc[a].append(k);inc[c].append(k)
        rhs=[rng.randrange(2) for _ in range(vcount)]
        rhs[-1]=(sum(rhs[:-1])+i%2)%2
        cs=[]
        for vs,r in zip(inc,rhs):
            cs+=b.gate(vs,lambda *bits,r=r:sum(bits)%2==r)
        return len(edges),cs
    if f=='guarded-blocks':
        # Two random formula blocks selected by a hidden Boolean gate.
        k=n//2; cs=[]
        for sign,vs in [(1,list(range(2,k+2))),(-1,list(range(k+2,2*k+2)))]:
            for c in b.random3(rng,vs,round(4.26*k)):
                cs.append((sign,)+c)
        return 2*k+1,cs
    if f=='mixed-unplanted':
        cs=[]
        for _ in range(round(n*5.2)):
            k=rng.choice([2,3,4,4,5])
            cs.append(tuple(v*rng.choice([-1,1]) for v in rng.sample(range(1,n+1),k)))
        return n,cs
    if f=='overlap-blocks':
        k=n//2;overlap=max(3,k//4)
        left=list(range(1,k+1));right=list(range(k-overlap+1,n+1))
        cs=b.random3(rng,left,round(4.26*len(left)))+b.random3(rng,right,round(4.26*len(right)))
        return n,cs
    if f=='xor-mixed':
        cs=[]
        bits={v:bool(rng.getrandbits(1)) for v in range(1,n+1)}
        for _ in range(n//2):
            vs=rng.sample(range(1,n+1),3)
            parity=sum(bits[v] for v in vs)%2
            cs+=b.gate(vs,lambda *x,r=parity:sum(x)%2==r)
        cs+=b.random3(rng,list(range(1,n+1)),2*n,bits if i%2==0 else None)
        return n,cs
    if f=='modular-bridge':
        cs=[];k=n//4
        for j in range(4):
            vs=list(range(j*k+1,(j+1)*k+1))
            cs+=b.random3(rng,vs,round(3.8*k))
        for _ in range(n//2):
            vs=[rng.randrange(j*k+1,(j+1)*k+1) for j in rng.sample(range(4),3)]
            cs.append(tuple(v*rng.choice([-1,1]) for v in vs))
        return 4*k,cs
    raise ValueError(f)
FAMILIES=['random3','random4','mixed-planted','nae3','tseitin','guarded-blocks','mixed-unplanted','overlap-blocks','xor-mixed','modular-bridge']
