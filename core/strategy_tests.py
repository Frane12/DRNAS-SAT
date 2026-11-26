"""Prospective synthetic transfer: disjoint generators, frozen policy, audited outcomes."""
import itertools
import json
import pathlib
import random
import tempfile
from tests import write,truth,hide
from run import run as native
import strategy

def random_cnf(rng,n,m,width):
    return [tuple(rng.choice((-1,1))*v for v in rng.sample(range(1,n+1),width)) for _ in range(m)]

def train_cases():
    r=random.Random(2611202602)
    for i in range(48):
        n=8+i%5;w=2+i%3;m=(3 if i%2 else 5)*n
        yield 'train-random',*hide(r,n,random_cnf(r,n,m,w))

def holdout_cases():
    r=random.Random(2611202699)
    for i in range(24):
        n=8+i%5;w=2+i%3;m=(3 if i%2 else 5)*n
        yield 'fresh-random',*hide(r,n,random_cnf(r,n,m,w))
    for i in range(24):
        n=8+i%5
        # New generator: cyclic NAE constraints and optional random bridging clauses.
        cs=[]
        for v in range(1,n+1):
            a=(v, v%n+1,(v+1)%n+1)
            cs.extend((a,tuple(-x for x in a)))
        cs+=random_cnf(r,n,(1 if i%2 else 3)*n,3)
        yield 'unseen-nae-mix',*hide(r,n,cs)
    for i in range(12):
        n=9+i%4
        # New generator: planted signed implications and local OR relations.
        plant={v:r.choice((-1,1)) for v in range(1,n+1)}
        cs=[]
        for j in range(3*n):
            a,b,c=r.sample(range(1,n+1),3)
            cs.extend(((-plant[a]*a,plant[b]*b),(plant[a]*a,-plant[b]*b,plant[c]*c)))
        yield 'unseen-planted-relations',*hide(r,n,cs)

def checked(r,expected):
    assert r['status'] in (expected,'UNKNOWN','TIMEOUT','AUDIT_LIMIT'),r
    assert 'strategy_error' not in r,r
    return r['status']==expected

def main():
    with tempfile.TemporaryDirectory() as tmp:
        d=pathlib.Path(tmp);mem=d/'policy.json';ctx='small:mid:mixed'
        # Synthetic counter-only controls, not benchmark outcomes.
        fake=d/'test-policy.json'
        strategy.observe(fake,ctx,'narrow',False,.1)
        strategy.observe(fake,ctx,'wide',True,.1)
        strategy.observe(fake,ctx,'bridge',False,.1)
        assert strategy.choose(strategy.load(fake)[ctx],False)=='wide'
        assert strategy.choose({},False)=='narrow'
        assert strategy.choose({},True)=='narrow'
        train=0;hashes=set()
        import hashlib
        for i,(family,n,cs) in enumerate(train_cases()):
            src=d/f'train-{i}.cnf';write(src,n,cs)
            hashes.add(hashlib.sha256(src.read_bytes()).digest())
            expected='SAT' if truth(n,cs) else 'UNSAT'
            result=strategy.run(str(src),str(d/f'train-{i}.cert'),.75,5,mem)
            checked(result,expected);train+=1
            print('CORE_STRATEGY_TRAIN '+json.dumps(dict(id=i,family=family,expected=expected,**result)),flush=True)
        assert mem.exists()
        before=mem.read_bytes();data=strategy.load(mem)
        assert len({p for rows in data.values() for p in rows})==3,data
        paired={};totals={};transferred=0
        for i,(family,n,cs) in enumerate(holdout_cases()):
            src=d/f'test-{i}.cnf';write(src,n,cs)
            assert hashlib.sha256(src.read_bytes()).digest() not in hashes
            expected='SAT' if truth(n,cs) else 'UNSAT'
            arms=('cold','warm','default')
            arms=arms[i%3:]+arms[:i%3]
            out={}
            for arm in arms:
                ev=str(d/f'test-{i}-{arm}.cert')
                r=(strategy.run(str(src),ev,.75,5,mem,True) if arm=='warm' else
                   native(str(src),ev,.75,'freedom' if arm=='cold' else 'default',5))
                out[arm]=checked(r,expected)
                z=totals.setdefault(arm,dict(solved=0,solve_s=0.0))
                z['solved']+=int(out[arm]);z['solve_s']+=r.get('solve_s',0.0)
                if arm=='warm' and r['strategy']['context'] in data and r['strategy']['profile']!='narrow':transferred+=1
                print('CORE_STRATEGY_ROW '+json.dumps(dict(id=i,family=family,arm=arm,expected=expected,**r)),flush=True)
            key='both' if out['warm'] and out['cold'] else 'warm_only' if out['warm'] else 'cold_only' if out['cold'] else 'neither'
            row=paired.setdefault(family,{});row[key]=row.get(key,0)+1
        assert mem.read_bytes()==before,'holdout modified training memory'
        bad=d/'bad.json';bad.write_text('not json')
        src=d/'control.cnf';write(src,2,[(1,),(-2,)])
        r=strategy.run(str(src),str(d/'bad-control.cert'),.75,5,bad)
        assert r['status']=='SAT' and 'strategy_error' in r and bad.read_text()=='not json'
        print('CORE_STRATEGY_SUMMARY '+json.dumps(dict(train=train,holdout=60,totals=totals,paired=paired,nondefault_transfers=transferred,contexts=len(data))),flush=True)

if __name__=='__main__':main()
