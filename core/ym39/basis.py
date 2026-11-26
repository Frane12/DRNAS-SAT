"""Train a two-loop detector on one chain and read it on the other."""
import json
from pathlib import Path
import numpy as np
from scipy.linalg import eigh
from fresh import ROOT, energy, ensemble, read_blocks


def matrices(n,b,stage=235):
    auto=ensemble(stage,n,b)
    chains=[]
    for idx,start in enumerate(('cold','hot')):
        f=ROOT/(f'extend_L16_{start}.csv' if stage=='extend' else f'cross_L{n}_{start}.csv')
        a=read_blocks(f.name)
        if stage=="extend":a=a[:,64:]
        x=a.reshape(-1,b//16,8).mean(axis=1)
        assert len(x)==len(auto[idx])
        chain=np.zeros((len(x),8,2,2))
        chain[:,:,0,0]=auto[idx,:,2:10]; chain[:,:,1,1]=auto[idx,:,11:19]
        chain[:,:,0,1]=chain[:,:,1,0]=x
        chains.append(chain)
    return np.array(chains)

def optimal(training):
    g=training.mean(axis=0)
    return eigh(g[1],g[0])[1][:,-1]

def diagnostic(train,test):
    v=optimal(train)
    mu=np.einsum('i,btij,j->bt',v,test,v)
    n=len(mu);m=mu.mean(axis=0);loo=(n*m-mu)/(n-1)
    err=loo.std(axis=0)*np.sqrt(n-1)
    e1,e2=energy(m,1),energy(m,2)
    j1,j2=energy(loo,1),energy(loo,2)
    diff=(j1-j2).std()*np.sqrt(n-1)
    ok=min(m[1:4]/err[1:4])>=3 and abs(e1-e2)<=2*diff
    def num(x):return float(x) if np.isfinite(x) else None
    return dict(coefficients=(v/np.max(np.abs(v))).tolist(),heldout_energy=num(e2),
                conditional_se=num(j2.std()*np.sqrt(n-1)),screen=bool(ok))
def run():
    # An exact positive control: the second operator makes a weak component
    # separable from a heavy one even when the first alone scarcely sees it.
    heavy=np.array([1.,1.]);light=np.array([.01,.15])
    def shape(e,t):return np.exp(-e*t)+np.exp(-e*(24-t))
    ex=np.array([shape(1.2,t)*np.outer(heavy,heavy)+shape(.3,t)*np.outer(light,light) for t in range(8)])
    v=optimal(ex[None,...])
    assert abs(v@heavy)<1e-10
    c=np.einsum('i,tij,j->t',v,ex,v)
    assert abs(energy(c,2)-.3)<1e-9
    report={}
    for n,stage in ((8,235),(16,235),(16,'extend')):
        result={}
        for b in (32,64):
            a,c=matrices(n,b,stage)
            result[b]=[diagnostic(a,c),diagnostic(c,a)]
        report[f"{n}_{stage}"]=result
    return report

if __name__=='__main__':
    print(json.dumps(run(),indent=2,allow_nan=False))
