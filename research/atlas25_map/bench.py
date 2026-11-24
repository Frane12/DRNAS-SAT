"""Generated category holdout controls; solver gets only shuffled signed DIMACS bytes."""
import random,itertools as I,json,time,sys,collections
from pathlib import Path
from engine import solve
from verify import verify
class CNF:
    def __init__(self):self.n=0;self.cs=[]
    def fresh(self,k=1):
        a=list(range(self.n+1,self.n+k+1));self.n+=k;return a
    def rel(self,vs,f):
        for b in I.product((0,1),repeat=len(vs)):
            if not f(b):self.cs.append([(-v if x else v) for v,x in zip(vs,b)])
    def unit(self,v,b):self.cs.append([v if b else -v])
    def raw(self,r):
        ids=self.fresh(0)+list(range(1,self.n+1));r.shuffle(ids);s=[r.choice((-1,1)) for _ in ids]
        cs=[[(1 if x>0 else -1)*s[abs(x)-1]*ids[abs(x)-1] for x in c] for c in self.cs]
        r.shuffle(cs)
        for c in cs:r.shuffle(c)
        return ('p cnf %d %d\n'%(self.n,len(cs))+''.join(' '.join(map(str,c))+' 0\n' for c in cs)).encode()
def parity(n,bad):
    c=CNF();x=c.fresh(n)
    for a,b in zip(x,x[1:]):c.rel([a,b],lambda t:t[0]==t[1])
    c.rel([x[-1],x[0]],lambda t:t[0]^t[1]==bad)
    return c
def xor3(n,bad):
    c=CNF();x=c.fresh(n+1);z=c.fresh(n)
    for i in range(n):c.rel([x[i],z[i],x[i+1]],lambda b:sum(b)%2==0)
    c.unit(x[0],0);c.unit(x[-1],bad)
    for v in z:c.unit(v,0)
    return c
def cardinal(n,bad):
    c=CNF()
    for _ in range(n):
        a=c.fresh(6);c.rel(a,lambda b:sum(b)==2)
        c.unit(a[0],1);c.unit(a[1],1);c.unit(a[2],bad)
    return c
def add(n,bad,compact=False):
    c=CNF();a=c.fresh(n);b=c.fresh(n);s=c.fresh(n);carry=c.fresh(n+1)
    c.unit(carry[0],0)
    for i in range(n):
        if compact:
            p,g,t=c.fresh(3)
            c.rel([a[i],b[i],p],lambda t:sum(t)%2==0)
            c.rel([p,carry[i],s[i]],lambda t:sum(t)%2==0)
            for x,y,z in ((a[i],b[i],g),(p,carry[i],t)):
                c.cs.extend([[-x,-y,z],[x,-z],[y,-z]])
            c.cs.extend([[g,t,-carry[i+1]],[-g,carry[i+1]],[-t,carry[i+1]]])
        else:c.rel([a[i],b[i],carry[i],s[i],carry[i+1]],lambda t:sum(t[:3])==t[3]+2*t[4])
    for i in range(n):c.unit(a[i],1);c.unit(b[i],int(i==0))
    for i in range(n):c.unit(s[i],int(bad and i==n-1))
    return c
def color(n,bad):
    c=CNF();x=[c.fresh(3) for _ in range(n)]
    for a in x:c.rel(a,lambda b:sum(b)==1)
    edges={(i,(i+1)%n) for i in range(n)}
    if bad:edges.update(I.combinations(range(4),2))
    for i,j in edges:
        for k in range(3):c.cs.append([-x[i][k],-x[j][k]])
    return c
def gate(n,bad):
    c=CNF();a=c.fresh(1)[0];c.unit(a,1)
    for _ in range(n):
        b,s,z=c.fresh(3);c.unit(b,1);c.unit(s,0)
        c.rel([a,b,s,z],lambda t:t[3]==(t[1] if t[2] else t[0]));a=z
    c.unit(a,1-bad);return c
def mixed(n,bad):
    c=CNF()
    for _ in range(n):
        x,y0,y1,z0,z1=c.fresh(5)
        c.rel([x,y0],lambda b:b[0]==b[1])
        c.rel([y0,y1,z0,z1],lambda b:(b[0]+2*b[1]+1)%4==b[2]+2*b[3])
        c.rel([x,z0],lambda b:sum(b)<=int(not bad))
    return c
def run(out,real=None):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    rng=random.Random(250124);rows=[]
    families={'GF2_EQUALITY':(parity,[8,16,32,64]),'GF2_XOR3':(xor3,[8,16,32,64]),
              'CAPACITY_EXACT':(cardinal,[1,4,8,16]),'ARITH_FULL':(add,[8,16,32,64]),
              'ARITH_COMPACT':(lambda n,b:add(n,b,True),[8,16,32,64]),
              'GRAPH_COLOR':(color,[4,6,8,12]),'MUX_NETWORK':(gate,[8,16,32,64]),
              'MIXED':(mixed,[1,4,8,16])}
    for fam,(gen,sizes) in families.items():
        for n in sizes:
            for bad in (0,1):
                for rep in range(2):
                    raw=gen(n,bad).raw(rng); t=time.perf_counter();r=solve(raw);dt=time.perf_counter()-t
                    audit=verify(raw,r)
                    expected='UNSAT' if bad else 'SAT'
                    assert r['status'] in (expected,'UNKNOWN'),(fam,n,bad,r['status'])
                    row={'family':fam,'size':n,'rep':rep,'expected':expected,'status':r['status'],'audit':audit,'seconds':round(dt,6),'variables':r['variables'],'clauses':r['clauses'],'work':r['work'],'map':r['map']}
                    rows.append(row)
        a=[x for x in rows if x['family']==fam]
        print('ATLAS25_FAMILY',fam,json.dumps(dict(collections.Counter(x['status'] for x in a))),flush=True)
    if real:
        for file in sorted(Path(real).rglob('*.cnf')):
            raw=file.read_bytes();t=time.perf_counter();r=solve(raw);dt=time.perf_counter()-t
            audit=verify(raw,r)
            row={'family':'CHACHA_DERIVED_RAW','file':file.name,'status':r['status'],'audit':audit,'seconds':round(dt,6),'variables':r['variables'],'clauses':r['clauses'],'work':r['work'],'map':r['map'],'reason':r.get('reason')}
            rows.append(row);print('ATLAS25_REAL',json.dumps(row),flush=True)
            (out/(file.stem+'_certificate.json')).write_text(json.dumps(r))
    (out/'rows.json').write_text(json.dumps(rows,indent=2))
    for fam in sorted(set(x['family'] for x in rows)):
        a=[x for x in rows if x['family']==fam]; cats=collections.Counter();links=collections.Counter()
        for x in a:cats.update(x['map']['local_categories']);links.update(x['map']['category_overlap_shared_variables'])
        print('ATLAS25_MAP',json.dumps({'family':fam,'cases':len(a),'status':dict(collections.Counter(x['status'] for x in a)),'labels':dict(cats),'overlaps':dict(links),'max_variables':max(x['variables'] for x in a)}),flush=True)
    print('ATLAS25_FINAL',json.dumps(dict(collections.Counter(x['status'] for x in rows))),flush=True)
if __name__=='__main__':run(sys.argv[1],sys.argv[2] if len(sys.argv)>2 else None)
