"""Conservative screens for seven fresh operators, two couplings and volumes."""
import json
from pathlib import Path
from zipfile import ZipFile
from scipy.stats import t as student
import numpy as np

ROOT=Path(__file__).resolve().parent
NAMES=['moving_square','moving_large_square','rest_square','rest_large_square',
       'moving_tensor_difference','rest_tensor_difference','winding_flux_rest']
T=24

def read_blocks(filename):
    local = ROOT / filename
    if local.exists():
        return np.loadtxt(local, delimiter=',')
    with ZipFile(ROOT / 'measurement_blocks.zip') as archive:
        with archive.open(filename) as stream:
            return np.loadtxt(stream, delimiter=',')


def ensemble(beta,n,b):
    rows=[]
    for start in ('cold','hot'):
        f=(ROOT/f'extend_L16_{start}.csv' if beta=='extend' else ROOT/f'b{beta}_L{n}_{start}.csv')
        a=read_blocks(f.name)
        if beta=='extend':
            assert a.shape==(192,72) and n==16
            a=a[:,:64]
        else:
            assert a.shape==(128 if n==8 else 64,64)
        rows.append(a.reshape(-1,b//16,64).mean(axis=1))
    return np.asarray(rows)

def corr(z,ch):
    a=z[...,1+ch*9:1+(ch+1)*9]
    c=a[...,1:].copy()
    if ch in (2,3):
        c-=a[...,:1]**2
    return c

def energy(c,t):
    ratio=c[...,t]/c[...,t+1]
    valid=(c[...,t+1]>0)&(ratio>1)
    lo=np.zeros_like(ratio);hi=lo+10
    for _ in range(50):
        m=(hi+lo)/2
        small=np.cosh((T/2-t)*m)/np.cosh((T/2-t-1)*m)<ratio
        lo=np.where(small,m,lo);hi=np.where(small,hi,m)
    return np.where(valid,(lo+hi)/2,np.nan)

def summarize(a,ch):
    k=len(a); mean=a.mean(axis=0)
    loo=(k*mean-a)/(k-1)
    c=corr(mean,ch); cl=corr(loo,ch)
    se=cl.std(axis=0)*np.sqrt(k-1)
    snr=c[1:4]/se[1:4]
    e=[energy(c,t) for t in (1,2)]
    el=[energy(cl,t) for t in (1,2)]
    ee=[arr.std()*np.sqrt(k-1) for arr in el]
    derr=(el[0]-el[1]).std()*np.sqrt(k-1)
    good=(min(snr)>=3 and np.isfinite(derr) and abs(e[0]-e[1])<=2*derr)
    def num(v):return float(v) if np.isfinite(v) else None
    # Separate nominal simultaneous upper limit for two pre-specified rest probes.
    upper=None
    if ch in (2,3):
        lag=np.arange(1,6)
        spec=(np.exp(-.1*lag)+np.exp(-.1*(24-lag)))/(1+np.exp(-2.4))
        rl=cl[:,1:6]/cl[:,:1]
        margins=student.ppf(1-.05/50,k-1)*rl.std(axis=0)*np.sqrt(k-1)
        upper=float(np.min((c[1:6]/c[0]+margins)/spec))
    return dict(rest_weight_le_point1_upper=upper,c=c.tolist(),se=se.tolist(),energy=[num(v) for v in e],
                error=[num(v) for v in ee],passed=bool(good))

def analyze(beta,n):
    tests={}
    for b in (32,64):
        rows=ensemble(beta,n,b)
        combined=rows.reshape(-1,64)
        tests[b]={}
        for i,name in enumerate(NAMES):
            res=summarize(combined,i)
            a,h=[summarize(chain,i) for chain in rows]
            dif=np.abs(np.array(a['c'][1:4])-h['c'][1:4])
            err=np.hypot(a['se'][1:4],h['se'][1:4])
            compatible=np.all(dif<=3*err)
            plaquettes=rows[:,:,0]
            diff=np.ptp(plaquettes.mean(axis=1))
            pe=np.sqrt(np.sum(plaquettes.var(axis=1,ddof=1))/len(rows[0]))
            res['starts_ok']=bool(compatible and diff<=3*pe)
            tests[b][name]=res
    return {name:{'status':'PROVISIONAL' if all(tests[b][name][i] for b in (32,64)
                       for i in ('passed','starts_ok')) else 'UNRESOLVED',
                  'block32':tests[32][name],'block64':tests[64][name]} for name in NAMES}

if __name__=='__main__':
    print(json.dumps({str(beta):{str(n):analyze(beta,n) for n in (8,16)}
                      for beta in (235,245)},indent=2,allow_nan=False))
