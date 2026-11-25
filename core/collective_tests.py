"""YM30 paired blinded sparse operators, scaling controls, native CORE cross-check."""
from pathlib import Path
from tempfile import TemporaryDirectory
from fractions import Fraction as Q
import random,json,sys
from atlas_collective import solve
from collective_verify import verify
from run import run

def matrix(n,edges,pins,target,seed):
    diag=[Q(pins.get(i,0)) for i in range(n)]
    rng=random.Random(seed);perm=list(range(n));rng.shuffle(perm)
    off=[]
    for i,j,w in edges:
        w=Q(w);diag[i]+=w;diag[j]+=w
        a,b=sorted((perm[i],perm[j]));off.append([a,b,str(-w)])
    d=[None]*n
    for i in range(n):d[perm[i]]=str(diag[i])
    return dict(n=n,diagonal=d,off_diagonal=sorted(off),target=str(target))

def main(atlas):
    cases=[]
    for n in (8,16,32,64,128,256):
        edges=[(i,i+1,1) for i in range(n-1)]
        cases.append((matrix(n,edges,{i:1 for i in range(0,n,2)},Q(1,5),n+1),'LOWER_PROVED','spread'))
        cases.append((matrix(n,edges,{i:1 for i in range(n//2)},Q(1,5),n+1),'UPPER_PROVED','clustered'))
    # Same pattern under rational rescaling, and a genuinely 2D grid.
    n=32;edges=[(i,i+1,Q(3,2)) for i in range(n-1)]
    cases.append((matrix(n,edges,{i:Q(3,2) for i in range(0,n,2)},Q(3,10),89),'LOWER_PROVED','weighted'))
    L=8;n=L*L;edges=[(i*L+j,i*L+j+1,1) for i in range(L) for j in range(L-1)]
    edges += [(i*L+j,(i+1)*L+j,1) for i in range(L-1) for j in range(L)]
    cases.append((matrix(n,edges,{i*L+j:1 for i in range(L) for j in range(L) if (i+j)%2==0},Q(1,9),91),'LOWER_PROVED','grid'))
    cases.append((matrix(8,[(i,i+1,1) for i in range(3)]+[(i,i+1,1) for i in range(4,7)],{0:1},Q(1,5),17),'UPPER_PROVED','zero_component'))
    random.Random(3030).shuffle(cases)
    with TemporaryDirectory() as tmp:
        root=Path(tmp)
        for i,(s,expected,label) in enumerate(cases):
            src=root/f'{i}.json';cert=root/f'{i}.cert';src.write_text(json.dumps(s,sort_keys=True))
            r=solve(src,cert,atlas,root/f'work{i}')
            assert r['status']==expected,(i,r)
            independent=verify(src,cert);assert independent['status']==expected
            old=cert.read_text();c=json.loads(old);c['bound']=str(Q(c['bound'])+1);cert.write_text(json.dumps(c))
            try:verify(src,cert)
            except ValueError:pass
            else:raise AssertionError('tampered bound')
            cert.write_text(old)
            # Cross-check small positive lower claims in existing C++ CORE
            # via exact PSD of A-target I (not via graph paths).
            if s['n']<=24 and expected=='LOWER_PROVED':
                n=s['n'];a=[[Q(0)]*n for _ in range(n)]
                for j,x in enumerate(s['diagonal']):a[j][j]=Q(x)-Q(s['target'])
                for j,k,x in s['off_diagonal']:a[j][k]=a[k][j]=Q(x)
                p=root/f'{i}.op';q=root/f'{i}.native'
                p.write_text(f'p op psd {n}\n'+'\n'.join(' '.join(map(str,row)) for row in a)+'\n')
                assert run(p,q,5,audit_seconds=15)['status']=='PROVED'
            print('YM30_ROW '+json.dumps(dict(id=i,family=label,**r)),flush=True)
    print('YM30_SUMMARY '+json.dumps(dict(cases=len(cases),lower=8,upper=7,continuum=False)),flush=True)
if __name__=='__main__':main(Path(sys.argv[1]).resolve())
